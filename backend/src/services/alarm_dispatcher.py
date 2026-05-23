"""Alarm Dispatcher — async bridge between the inference thread and persistence/broadcast.

Architecture
------------
The ``AlarmEngine`` runs **synchronously** inside the per-stream inference
thread and appends ``AlarmEventDelta`` objects to an in-memory list.

The dispatcher is an asyncio background task that polls all active engines
every ~100 ms, drains their deltas and performs the I/O-bound work:

1. Persists ``AlarmEvent`` rows to the database.
2. Optionally encodes and saves a JPEG snapshot.
3. Broadcasts ``alarm.opened`` / ``alarm.closed`` messages to all WebSocket
   subscribers (global fan-out, not stream-scoped).

Separation of concerns: the engine is pure-logic (no I/O, no asyncio), the
dispatcher is the only component that writes to the DB and the filesystem.

Usage
-----
::

    # Application lifespan (main.py)
    asyncio.create_task(alarm_dispatcher.run())

    # WebSocket endpoint
    queue = asyncio.Queue(maxsize=100)
    alarm_dispatcher.add_ws_subscriber(queue)
    try:
        msg = await queue.get()
    finally:
        alarm_dispatcher.remove_ws_subscriber(queue)
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .alarm_engine import AlarmEventDelta

logger = logging.getLogger(__name__)

# Where snapshots are stored (relative to CWD or absolute via env var)
SNAPSHOT_DIR = os.environ.get("ALARM_SNAPSHOT_DIR", "/tmp/alarm_snapshots")


class AlarmDispatcher:
    """Global singleton that drains engine deltas and persists alarm events."""

    _POLL_INTERVAL = 0.1  # seconds between engine polls

    def __init__(self) -> None:
        self._ws_subscribers: set[asyncio.Queue] = set()
        self._webhook_tasks: set[asyncio.Task] = set()
        self._running = False
        self._open_event_ids: dict[int, int] = {}  # alarm_id → alarm_events.id

    # ------------------------------------------------------------------ #
    # WebSocket subscription
    # ------------------------------------------------------------------ #

    def add_ws_subscriber(self, queue: asyncio.Queue) -> None:
        self._ws_subscribers.add(queue)

    def remove_ws_subscriber(self, queue: asyncio.Queue) -> None:
        self._ws_subscribers.discard(queue)

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        """Background coroutine. Run once as an asyncio task during app lifespan."""
        self._running = True
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        logger.info("AlarmDispatcher started (snapshot_dir=%s)", SNAPSHOT_DIR)
        try:
            while self._running:
                await asyncio.sleep(self._POLL_INTERVAL)
                await self._poll_engines()
        except asyncio.CancelledError:
            logger.info("AlarmDispatcher stopped")
        finally:
            self._running = False

    def stop(self) -> None:
        self._running = False

    # ------------------------------------------------------------------ #
    # Engine polling
    # ------------------------------------------------------------------ #

    async def _poll_engines(self) -> None:
        from .inference_worker_manager import inference_worker_manager

        engines = inference_worker_manager.get_all_engines()
        if not engines:
            return

        for engine in engines:
            deltas = engine.drain_deltas()
            for delta in deltas:
                await self._handle_delta(delta)

    # ------------------------------------------------------------------ #
    # Delta handling
    # ------------------------------------------------------------------ #

    async def _handle_delta(self, delta: AlarmEventDelta) -> None:
        from ..db.session import SessionLocal
        from ..models.alarm import Alarm

        db = SessionLocal()
        try:
            alarm = db.query(Alarm).filter(Alarm.id == delta.alarm_id).first()
            if alarm is None:
                return

            if delta.event_type == "open":
                await self._handle_open(db, alarm, delta)
            elif delta.event_type == "close":
                await self._handle_close(db, alarm, delta)
        except Exception:
            logger.exception("AlarmDispatcher: error handling delta alarm_id=%d", delta.alarm_id)
            db.rollback()
        finally:
            db.close()

    async def _handle_open(self, db: Any, alarm: Any, delta: AlarmEventDelta) -> None:
        from ..models.alarm import AlarmEvent

        if not alarm.store_events:
            self._broadcast(delta, alarm)
            return

        snapshot_path: str | None = None
        if alarm.store_snapshot:
            snapshot_path = await asyncio.get_event_loop().run_in_executor(None, self._save_snapshot, delta)

        event = AlarmEvent(
            alarm_id=delta.alarm_id,
            stream_id=delta.stream_id,
            zone_id=delta.zone_id,
            state="open",
            started_at=datetime.utcfromtimestamp(delta.timestamp),
            peak_confidence=delta.peak_confidence or None,
            peak_count=delta.peak_count or None,
            matched_classes=delta.matched_classes or None,
            matched_track_ids=delta.matched_track_ids or None,
            rule_snapshot=delta.rule_snapshot,
            snapshot_path=snapshot_path,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        self._open_event_ids[delta.alarm_id] = event.id
        logger.info(
            "AlarmEvent opened: alarm=%d stream=%d event_id=%d classes=%s",
            delta.alarm_id,
            delta.stream_id,
            event.id,
            delta.matched_classes,
        )
        self._broadcast(delta, alarm, event_id=event.id)

    async def _handle_close(self, db: Any, alarm: Any, delta: AlarmEventDelta) -> None:
        from ..models.alarm import AlarmEvent

        event_id = self._open_event_ids.pop(delta.alarm_id, None)
        if event_id is None:
            return

        if not alarm.store_events:
            self._broadcast(delta, alarm, event_id=event_id)
            return

        event = db.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
        if event:
            event.state = "closed"
            event.ended_at = datetime.utcfromtimestamp(delta.timestamp)
            db.commit()
            logger.info(
                "AlarmEvent closed: alarm=%d stream=%d event_id=%d",
                delta.alarm_id,
                delta.stream_id,
                event_id,
            )
        self._broadcast(delta, alarm, event_id=event_id)

    # ------------------------------------------------------------------ #
    # Snapshot save (CPU-bound, runs in executor)
    # ------------------------------------------------------------------ #

    def _save_snapshot(self, delta: AlarmEventDelta) -> str | None:
        if delta.frame is None:
            logger.warning(
                "AlarmDispatcher: no frame for alarm %d event — snapshot skipped",
                delta.alarm_id,
            )
            return None
        try:
            import cv2

            os.makedirs(SNAPSHOT_DIR, exist_ok=True)
            filename = f"alarm_{delta.alarm_id}_{delta.stream_id}_{int(delta.timestamp)}.jpg"
            path = os.path.join(SNAPSHOT_DIR, filename)
            ok = cv2.imwrite(path, delta.frame)
            if not ok:
                logger.error(
                    "AlarmDispatcher: cv2.imwrite returned False for alarm %d (path=%s)",
                    delta.alarm_id,
                    path,
                )
                return None
            return path
        except Exception:
            logger.exception("AlarmDispatcher: failed to save snapshot for alarm %d", delta.alarm_id)
            return None

    # ------------------------------------------------------------------ #
    # WebSocket broadcast + webhook
    # ------------------------------------------------------------------ #

    def _broadcast(self, delta: AlarmEventDelta, alarm: Any, event_id: int | None = None) -> None:
        msg = {
            "type": f"alarm.{delta.event_type}d",  # alarm.opened / alarm.closed
            "alarm_id": delta.alarm_id,
            "stream_id": delta.stream_id,
            "zone_id": delta.zone_id,
            "event_id": event_id,
            "timestamp": delta.timestamp,
            "severity": alarm.severity,
            "alarm_name": alarm.name,
            "matched_classes": delta.matched_classes,
            "peak_confidence": delta.peak_confidence,
            "peak_count": delta.peak_count,
        }

        channels = alarm.notify_channels or ["ws"]
        if "ws" in channels and self._ws_subscribers:
            dead: set[asyncio.Queue] = set()
            for q in self._ws_subscribers:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    dead.add(q)
            self._ws_subscribers -= dead

        if "webhook" in channels and alarm.webhook_url:
            try:
                _task = asyncio.create_task(self._post_webhook(alarm.webhook_url, msg))
                self._webhook_tasks.add(_task)
                _task.add_done_callback(self._webhook_tasks.discard)
            except RuntimeError:
                # No running event loop (e.g. during tests) — skip
                logger.debug("AlarmDispatcher: no event loop for webhook POST")

    async def _post_webhook(self, url: str, payload: dict[str, Any]) -> None:
        """POST ``payload`` to ``url`` with simple exponential backoff retry."""
        try:
            import httpx
        except Exception:
            logger.warning("AlarmDispatcher: httpx not available, cannot post webhook")
            return

        delays = [0.5, 1.0, 2.0]
        last_err: Exception | None = None
        for attempt, delay in enumerate(delays, start=1):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json=payload)
                    if 200 <= resp.status_code < 300:
                        return
                    last_err = Exception(f"HTTP {resp.status_code}")
            except Exception as e:
                last_err = e
            if attempt < len(delays):
                await asyncio.sleep(delay)
        logger.warning(
            "AlarmDispatcher: webhook POST to %s failed after %d attempts: %s",
            url,
            len(delays),
            last_err,
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
alarm_dispatcher = AlarmDispatcher()
