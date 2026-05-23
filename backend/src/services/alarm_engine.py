"""Per-stream alarm rule evaluator.

Each ``AlarmEngine`` is attached to exactly one stream's ``InferenceWorker``.
On each ``DetectionEvent`` the engine evaluates every active alarm rule and
emits ``AlarmEventDelta`` objects for open / close transitions.

Hysteresis model per rule
--------------------------
*  ``min_on_seconds``  — the trigger condition must be *continuously* active
   for this many seconds before the alarm is opened.
*  ``min_off_seconds`` — the trigger condition must be *continuously* absent
   for this many seconds before an open alarm is closed.
*  ``cooldown_seconds`` — after an alarm closes, no new open can be issued
   for this long.

Trigger types
-------------
*  ``class_present``     — any detection in ``class_names`` above confidence.
*  ``class_count``       — number of matching detections satisfies
   ``count_op / count_threshold``.
*  ``class_absent_for``  — no detection of ``class_names`` above confidence
   has been seen for ``absent_seconds`` (tracks last-seen wall time).
*  ``zone_enter``        — a new ``track_id`` entered the alarm's zone.
*  ``dwell``             — a ``track_id`` has been continuously inside the
   alarm's zone for ``dwell_seconds``.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np

    from .inference_worker import DetectionEvent

import logging

logger = logging.getLogger(__name__)

# ── Alarm event delta ───────────────────────────────────────────────────


@dataclass
class AlarmEventDelta:
    """A single open or close transition for one alarm rule."""

    alarm_id: int
    stream_id: int
    zone_id: int | None
    event_type: str  # 'open' | 'close'
    timestamp: float  # wall-clock (time.time())
    matched_classes: dict[str, int]  # class_name → count
    peak_confidence: float
    peak_count: int
    matched_track_ids: list[int]
    rule_snapshot: dict[str, Any]
    frame: np.ndarray | None  # raw frame at transition time (for snapshot)


# ── Count-op helper ─────────────────────────────────────────────────────

_COUNT_OPS: dict[str, Any] = {
    ">=": operator.ge,
    ">": operator.gt,
    "==": operator.eq,
    "<=": operator.le,
    "<": operator.lt,
}


# ── Geometry helpers ────────────────────────────────────────────────────


def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test.

    ``polygon`` is a list of (x, y) vertices in the same coordinate space as
    ``(x, y)``. Returns True if the point lies inside the polygon.
    """
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        # Check if edge (xi,yi)-(xj,yj) crosses horizontal ray to the right of (x,y)
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _filter_detections_by_zone(
    detections: list[dict[str, Any]],
    zone_polygon_norm: list[tuple[float, float]] | None,
    frame_shape: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    """Filter detections so only those whose bbox CENTER lies inside the
    normalized polygon survive.

    ``zone_polygon_norm`` vertices are in [0..1] relative to (width, height).
    ``frame_shape`` is ``(height, width)``. If either is missing, no filter
    is applied.
    """
    if not zone_polygon_norm or frame_shape is None:
        return detections
    h, w = frame_shape[0], frame_shape[1]
    if w <= 0 or h <= 0:
        return detections
    # Denormalize polygon once
    poly_px: list[tuple[float, float]] = [(float(px) * w, float(py) * h) for px, py in zone_polygon_norm]
    out: list[dict[str, Any]] = []
    for det in detections:
        bbox = det.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        cx = (float(bbox[0]) + float(bbox[2])) / 2.0
        cy = (float(bbox[1]) + float(bbox[3])) / 2.0
        if _point_in_polygon(cx, cy, poly_px):
            out.append(det)
    return out


def _in_schedule(now_dt: datetime, schedule: list[dict[str, Any]] | None) -> bool:
    """Return True if ``now_dt`` falls inside one of the schedule windows
    (or if no schedule is configured)."""
    if not schedule:
        return True
    weekday = now_dt.weekday()  # Mon=0
    hour = now_dt.hour
    for win in schedule:
        wds = win.get("weekdays") or list(range(7))
        if weekday not in wds:
            continue
        start = int(win.get("start_hour", 0))
        end = int(win.get("end_hour", 24))
        if start <= hour < end:
            return True
    return False


# ── Per-rule state ──────────────────────────────────────────────────────


@dataclass
class _RuleState:
    """Mutable hysteresis state for one alarm rule."""

    alarm_id: int
    stream_id: int
    zone_id: int | None
    trigger_type: str
    trigger_config: dict[str, Any]
    min_on_seconds: float
    min_off_seconds: float
    cooldown_seconds: float
    rule_snapshot: dict[str, Any]

    zone_polygon: list[tuple[float, float]] | None = None
    schedule: list[dict[str, Any]] | None = None

    is_open: bool = False
    condition_true_since: float | None = None  # epoch when condition first became true
    condition_false_since: float | None = None  # epoch when condition first became false
    last_closed_at: float | None = None  # epoch of last alarm close (cooldown)
    last_seen_at: float | None = None  # epoch of last matching detection (absent_for)

    # zone_enter / dwell state
    tracks_in_zone: set[int] = field(default_factory=set)
    track_entry_times: dict[int, float] = field(default_factory=dict)
    # debug-once flag for missing frame in zone-based triggers
    _zone_warned_no_frame: bool = False


# ── Engine ──────────────────────────────────────────────────────────────


class AlarmEngine:
    """Evaluates all alarm rules for one stream on every inference event.

    Usage::

        engine = AlarmEngine(stream_id)
        engine.load_rules(alarm_orm_list, zones_by_id)
        worker.set_alarm_callback(engine.evaluate)

        # In the dispatcher:
        while True:
            delta = await engine.queue.get()
            # persist / broadcast
    """

    def __init__(self, stream_id: int) -> None:
        self._stream_id = stream_id
        self._rules: list[_RuleState] = []
        self._deltas: list[AlarmEventDelta] = []  # pending deltas, drained by dispatcher

    # ------------------------------------------------------------------ #
    # Rule loading
    # ------------------------------------------------------------------ #

    def load_rules(
        self,
        alarms: list[Any],
        zones_by_id: dict[int, list[tuple[float, float]]] | None = None,
    ) -> None:
        """Replace the active rule set from a list of ``Alarm`` ORM objects.

        ``zones_by_id`` maps zone_id to its polygon as a list of (x, y)
        floats in [0..1] (normalized). If a rule has ``zone_id`` set but
        the zone is missing from the dict, the rule's zone polygon is None
        (effectively no spatial filter, with a warning).
        """
        zones_by_id = zones_by_id or {}
        rules: list[_RuleState] = []
        for alarm in alarms:
            if not alarm.is_active:
                continue
            snapshot = {
                "id": alarm.id,
                "name": alarm.name,
                "trigger_type": alarm.trigger_type,
                "trigger_config": dict(alarm.trigger_config or {}),
                "severity": alarm.severity,
                "zone_id": alarm.zone_id,
            }
            zone_poly: list[tuple[float, float]] | None = None
            if alarm.zone_id is not None:
                raw = zones_by_id.get(alarm.zone_id)
                if raw is not None:
                    zone_poly = [(float(p[0]), float(p[1])) for p in raw]
                else:
                    logger.warning(
                        "AlarmEngine: alarm %d references zone %d but polygon not provided",
                        alarm.id,
                        alarm.zone_id,
                    )
            rules.append(
                _RuleState(
                    alarm_id=alarm.id,
                    stream_id=self._stream_id,
                    zone_id=alarm.zone_id,
                    trigger_type=alarm.trigger_type,
                    trigger_config=dict(alarm.trigger_config or {}),
                    min_on_seconds=float(alarm.min_on_seconds or 0),
                    min_off_seconds=float(alarm.min_off_seconds or 2),
                    cooldown_seconds=float(alarm.cooldown_seconds or 0),
                    rule_snapshot=snapshot,
                    zone_polygon=zone_poly,
                    schedule=list(alarm.schedule) if alarm.schedule else None,
                )
            )
        self._rules = rules
        logger.info("AlarmEngine stream %d: loaded %d active rules", self._stream_id, len(rules))

    def drain_deltas(self) -> list[AlarmEventDelta]:
        """Return and clear all pending deltas (thread-safe for single caller)."""
        if not self._deltas:
            return []
        deltas, self._deltas = self._deltas, []
        return deltas

    # ------------------------------------------------------------------ #
    # Evaluation — called synchronously from the inference worker thread
    # ------------------------------------------------------------------ #

    def evaluate(self, event: DetectionEvent, frame: np.ndarray | None = None) -> None:
        """Evaluate all rules against a detection event.

        Produces ``AlarmEventDelta`` objects in ``self._deltas`` for any
        open / close transitions. Designed to be extremely fast (pure
        in-memory, no I/O).
        """
        now = event.timestamp
        detections = event.detections

        # Determine frame shape (h, w) for zone filtering. Prefer the actual
        # frame array; fall back to event metadata.
        frame_shape: tuple[int, int] | None = None
        if frame is not None and hasattr(frame, "shape"):
            frame_shape = (int(frame.shape[0]), int(frame.shape[1]))
        else:
            fw = int(getattr(event, "frame_width", 0) or 0)
            fh = int(getattr(event, "frame_height", 0) or 0)
            if fw > 0 and fh > 0:
                frame_shape = (fh, fw)

        for rule in self._rules:
            try:
                self._evaluate_rule(rule, now, detections, frame, frame_shape)
            except Exception:
                logger.exception(
                    "AlarmEngine: error evaluating alarm %d on stream %d",
                    rule.alarm_id,
                    self._stream_id,
                )

    # ------------------------------------------------------------------ #
    # Rule-level evaluation
    # ------------------------------------------------------------------ #

    def _evaluate_rule(
        self,
        rule: _RuleState,
        now: float,
        detections: list[dict[str, Any]],
        frame: np.ndarray | None,
        frame_shape: tuple[int, int] | None,
    ) -> None:
        # Schedule gate — outside the configured window the condition is
        # forced to False, which lets an open alarm close via min_off.
        if rule.schedule and not _in_schedule(datetime.now(), rule.schedule):
            condition = False
            matched_classes: dict[str, int] = {}
            peak_confidence = 0.0
            peak_count = 0
            track_ids: list[int] = []
        else:
            # Spatial filter for zone-aware triggers
            effective_detections = detections
            if rule.zone_polygon is not None:
                if frame_shape is None:
                    if not rule._zone_warned_no_frame:
                        logger.debug(
                            "AlarmEngine: alarm %d has zone but no frame shape — skipping spatial filter",
                            rule.alarm_id,
                        )
                        rule._zone_warned_no_frame = True
                else:
                    effective_detections = _filter_detections_by_zone(detections, rule.zone_polygon, frame_shape)

            condition, matched_classes, peak_confidence, peak_count, track_ids = self._evaluate_condition(
                rule, now, effective_detections
            )

        if condition:
            rule.condition_false_since = None
            if rule.condition_true_since is None:
                rule.condition_true_since = now

            if not rule.is_open:
                if rule.last_closed_at is not None and rule.cooldown_seconds > 0:
                    if (now - rule.last_closed_at) < rule.cooldown_seconds:
                        return
                if (now - rule.condition_true_since) >= rule.min_on_seconds:
                    rule.is_open = True
                    self._emit(rule, "open", now, matched_classes, peak_confidence, peak_count, track_ids, frame)
        else:
            rule.condition_true_since = None
            if rule.is_open:
                if rule.condition_false_since is None:
                    rule.condition_false_since = now
                if (now - rule.condition_false_since) >= rule.min_off_seconds:
                    rule.is_open = False
                    rule.last_closed_at = now
                    rule.condition_false_since = None
                    self._emit(rule, "close", now, matched_classes, peak_confidence, peak_count, track_ids, frame)
            else:
                rule.condition_false_since = None

    def _evaluate_condition(
        self,
        rule: _RuleState,
        now: float,
        detections: list[dict[str, Any]],
    ) -> tuple[bool, dict[str, int], float, int, list[int]]:
        """Return (condition_met, matched_classes, peak_confidence, count, track_ids)."""
        cfg = rule.trigger_config
        ttype = rule.trigger_type

        class_names: set[str] = set(cfg.get("class_names") or [])
        min_conf: float = float(cfg.get("min_confidence", 0.5))

        matched: list[dict[str, Any]] = []
        for det in detections:
            if det.get("class_name") in class_names and float(det.get("confidence", 0)) >= min_conf:
                matched.append(det)

        peak_confidence = max((float(d["confidence"]) for d in matched), default=0.0)
        peak_count = len(matched)
        matched_class_counts: dict[str, int] = {}
        for d in matched:
            n = d.get("class_name", "")
            matched_class_counts[n] = matched_class_counts.get(n, 0) + 1
        track_ids = [int(d["track_id"]) for d in matched if d.get("track_id") is not None]

        if ttype == "class_present":
            return bool(matched), matched_class_counts, peak_confidence, peak_count, track_ids

        if ttype == "class_count":
            count_op = cfg.get("count_op", ">=")
            threshold = int(cfg.get("count_threshold", 1))
            op_fn = _COUNT_OPS.get(count_op, operator.ge)
            return op_fn(peak_count, threshold), matched_class_counts, peak_confidence, peak_count, track_ids

        if ttype == "class_absent_for":
            absent_seconds = float(cfg.get("absent_seconds", 30.0))
            if matched:
                rule.last_seen_at = now
            if rule.last_seen_at is None:
                rule.last_seen_at = now
            absent_duration = now - rule.last_seen_at
            return absent_duration >= absent_seconds, {}, 0.0, 0, []

        if ttype == "zone_enter":
            current_tracks = {int(d["track_id"]) for d in matched if d.get("track_id") is not None}
            new_tracks = current_tracks - rule.tracks_in_zone
            rule.tracks_in_zone = current_tracks
            new_ids = sorted(new_tracks)
            return bool(new_ids), matched_class_counts, peak_confidence, peak_count, new_ids

        if ttype == "dwell":
            dwell_seconds = float(cfg.get("dwell_seconds", 5.0))
            current_tracks = {int(d["track_id"]) for d in matched if d.get("track_id") is not None}
            # Drop tracks that left
            for tid in list(rule.track_entry_times):
                if tid not in current_tracks:
                    del rule.track_entry_times[tid]
            # Add entry time for new arrivals
            for tid in current_tracks:
                if tid not in rule.track_entry_times:
                    rule.track_entry_times[tid] = now
            rule.tracks_in_zone = current_tracks
            dwelled = [tid for tid, t0 in rule.track_entry_times.items() if (now - t0) >= dwell_seconds]
            dwelled_sorted = sorted(dwelled)
            return bool(dwelled_sorted), matched_class_counts, peak_confidence, peak_count, dwelled_sorted

        logger.warning("AlarmEngine: unknown trigger_type '%s' for alarm %d", ttype, rule.alarm_id)
        return False, {}, 0.0, 0, []

    # ------------------------------------------------------------------ #
    # Delta emit
    # ------------------------------------------------------------------ #

    def _emit(
        self,
        rule: _RuleState,
        event_type: str,
        now: float,
        matched_classes: dict[str, int],
        peak_confidence: float,
        peak_count: int,
        track_ids: list[int],
        frame: np.ndarray | None,
    ) -> None:
        frame_copy = frame.copy() if frame is not None else None
        delta = AlarmEventDelta(
            alarm_id=rule.alarm_id,
            stream_id=self._stream_id,
            zone_id=rule.zone_id,
            event_type=event_type,
            timestamp=now,
            matched_classes=matched_classes,
            peak_confidence=peak_confidence,
            peak_count=peak_count,
            matched_track_ids=track_ids,
            rule_snapshot=rule.rule_snapshot,
            frame=frame_copy,
        )
        self._deltas.append(delta)
        logger.debug(
            "AlarmEngine: alarm %d %s on stream %d (classes=%s)",
            rule.alarm_id,
            event_type,
            self._stream_id,
            matched_classes,
        )

    # ------------------------------------------------------------------ #
    # Stateless one-off evaluation (used by the /test endpoint)
    # ------------------------------------------------------------------ #

    @staticmethod
    def evaluate_once(
        alarm_orm: Any,
        zone_orm: Any | None,
        detections: list[dict[str, Any]],
        frame_shape: tuple[int, int] | None,
    ) -> dict[str, Any]:
        """Evaluate the alarm's condition once against a fixed set of
        detections, without touching any live engine state or I/O.

        Returns a dict with ``condition_met``, ``matched_classes``,
        ``peak_count``, ``peak_confidence``, ``matched_track_ids`` and
        ``in_schedule``.
        """
        now = datetime.now().timestamp()

        in_schedule = _in_schedule(datetime.now(), alarm_orm.schedule)

        zone_poly = None
        if zone_orm is not None and getattr(zone_orm, "polygon", None):
            zone_poly = [(float(p[0]), float(p[1])) for p in zone_orm.polygon]

        snapshot = {
            "id": alarm_orm.id,
            "name": alarm_orm.name,
            "trigger_type": alarm_orm.trigger_type,
            "trigger_config": dict(alarm_orm.trigger_config or {}),
            "severity": alarm_orm.severity,
            "zone_id": alarm_orm.zone_id,
        }
        rule = _RuleState(
            alarm_id=alarm_orm.id,
            stream_id=alarm_orm.stream_id,
            zone_id=alarm_orm.zone_id,
            trigger_type=alarm_orm.trigger_type,
            trigger_config=dict(alarm_orm.trigger_config or {}),
            min_on_seconds=float(alarm_orm.min_on_seconds or 0),
            min_off_seconds=float(alarm_orm.min_off_seconds or 0),
            cooldown_seconds=float(alarm_orm.cooldown_seconds or 0),
            rule_snapshot=snapshot,
            zone_polygon=zone_poly,
            schedule=list(alarm_orm.schedule) if alarm_orm.schedule else None,
        )

        if not in_schedule:
            return {
                "condition_met": False,
                "matched_classes": {},
                "peak_count": 0,
                "peak_confidence": 0.0,
                "matched_track_ids": [],
                "in_schedule": False,
            }

        effective = detections
        if zone_poly is not None and frame_shape is not None:
            effective = _filter_detections_by_zone(detections, zone_poly, frame_shape)

        condition, matched_classes, peak_conf, peak_count, track_ids = AlarmEngine._evaluate_condition_static(
            rule, now, effective
        )
        return {
            "condition_met": bool(condition),
            "matched_classes": matched_classes,
            "peak_count": peak_count,
            "peak_confidence": peak_conf,
            "matched_track_ids": track_ids,
            "in_schedule": True,
        }

    @staticmethod
    def _evaluate_condition_static(
        rule: _RuleState,
        now: float,
        detections: list[dict[str, Any]],
    ) -> tuple[bool, dict[str, int], float, int, list[int]]:
        """Static wrapper around the instance evaluator so ``evaluate_once``
        can reuse the same per-trigger logic without an engine instance."""
        # Create a throwaway engine just to dispatch — keeps logic in one place.
        engine = AlarmEngine(rule.stream_id)
        return engine._evaluate_condition(rule, now, detections)
