"""REST endpoints for the alarms subsystem (v2).

Resources:
  * ``/alarms``        — CRUD for alarm rules (stream-scoped).
  * ``/alarms/zones``  — CRUD for polygon zones on a stream.
  * ``/alarms/events`` — list/ack triggered alarm events.

Rule loading into the runtime engine is the responsibility of the
``inference_worker_manager``; this module only persists configuration and
notifies the manager via ``reload_alarms_for_stream`` when rules change.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ...db.session import get_db
from ...models.alarm import Alarm, AlarmEvent, AlarmZone
from ...models.stream import Stream
from ...schemas.alarm import (
    AlarmCreate,
    AlarmEventAck,
    AlarmEventResponse,
    AlarmResponse,
    AlarmUpdate,
    AlarmZoneCreate,
    AlarmZoneResponse,
    AlarmZoneUpdate,
)
from pydantic import BaseModel, Field

router = APIRouter()


class _TestDetection(BaseModel):
    class_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: list[float] = Field(..., min_length=4, max_length=4)
    track_id: int | None = None


class AlarmTestRequest(BaseModel):
    detections: list[_TestDetection]
    frame_width: int = Field(..., gt=0)
    frame_height: int = Field(..., gt=0)


class AlarmTestResponse(BaseModel):
    condition_met: bool
    matched_classes: dict[str, int]
    peak_count: int
    peak_confidence: float
    matched_track_ids: list[int]
    in_schedule: bool


# ── Helpers ─────────────────────────────────────────────────────────────


def _serialize_alarm(alarm: Alarm) -> dict[str, Any]:
    """Convert an ORM ``Alarm`` to the dict shape expected by
    ``AlarmResponse`` (merges ``trigger_type`` into ``trigger_config`` so the
    discriminated union validates)."""
    cfg = dict(alarm.trigger_config or {})
    cfg.setdefault("type", alarm.trigger_type)
    return {
        "id": alarm.id,
        "stream_id": alarm.stream_id,
        "name": alarm.name,
        "description": alarm.description,
        "is_active": alarm.is_active,
        "severity": alarm.severity,
        "trigger_type": alarm.trigger_type,
        "trigger_config": cfg,
        "zone_id": alarm.zone_id,
        "min_on_seconds": alarm.min_on_seconds,
        "min_off_seconds": alarm.min_off_seconds,
        "cooldown_seconds": alarm.cooldown_seconds,
        "schedule": alarm.schedule,
        "store_events": alarm.store_events,
        "store_snapshot": alarm.store_snapshot,
        "store_clip_seconds": alarm.store_clip_seconds,
        "notify_channels": alarm.notify_channels,
        "webhook_url": alarm.webhook_url,
        "created_at": alarm.created_at,
        "updated_at": alarm.updated_at,
    }


def _notify_engine_reload(stream_id: int) -> None:
    """Tell the inference worker manager to reload alarm rules for a stream.

    Imported lazily to avoid a circular import and to keep this module
    importable in environments without the worker manager (e.g. tests)."""
    try:
        from ...services.inference_worker_manager import inference_worker_manager
    except Exception:  # pragma: no cover - defensive
        return
    reload = getattr(inference_worker_manager, "reload_alarms_for_stream", None)
    if callable(reload):
        try:
            reload(stream_id)
        except Exception:  # pragma: no cover - never let API requests fail on engine reload
            pass


# ── Zones ───────────────────────────────────────────────────────────────


@router.get("/zones", response_model=list[AlarmZoneResponse])
def list_zones(
    stream_id: int | None = Query(None),
    db: Session = Depends(get_db),
) -> list[AlarmZone]:
    q = db.query(AlarmZone)
    if stream_id is not None:
        q = q.filter(AlarmZone.stream_id == stream_id)
    return q.order_by(AlarmZone.id).all()


@router.post("/zones", response_model=AlarmZoneResponse, status_code=201)
def create_zone(payload: AlarmZoneCreate, db: Session = Depends(get_db)) -> AlarmZone:
    if not db.query(Stream).filter(Stream.id == payload.stream_id).first():
        raise HTTPException(status_code=404, detail="Stream not found")
    zone = AlarmZone(**payload.model_dump())
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.put("/zones/{zone_id}", response_model=AlarmZoneResponse)
def update_zone(zone_id: int, payload: AlarmZoneUpdate, db: Session = Depends(get_db)) -> AlarmZone:
    zone = db.query(AlarmZone).filter(AlarmZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, key, value)
    db.commit()
    db.refresh(zone)
    _notify_engine_reload(zone.stream_id)
    return zone


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Session = Depends(get_db)) -> None:
    zone = db.query(AlarmZone).filter(AlarmZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    stream_id = zone.stream_id
    db.delete(zone)
    db.commit()
    _notify_engine_reload(stream_id)


# ── Alarms ──────────────────────────────────────────────────────────────


@router.get("", response_model=list[AlarmResponse])
@router.get("/", response_model=list[AlarmResponse], include_in_schema=False)
def list_alarms(
    stream_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    q = db.query(Alarm)
    if stream_id is not None:
        q = q.filter(Alarm.stream_id == stream_id)
    if is_active is not None:
        q = q.filter(Alarm.is_active == is_active)
    rows = q.order_by(Alarm.id).offset(skip).limit(limit).all()
    return [_serialize_alarm(a) for a in rows]


@router.post("", response_model=AlarmResponse, status_code=201)
@router.post("/", response_model=AlarmResponse, status_code=201, include_in_schema=False)
def create_alarm(payload: AlarmCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    if not db.query(Stream).filter(Stream.id == payload.stream_id).first():
        raise HTTPException(status_code=404, detail="Stream not found")
    if payload.zone_id is not None:
        zone = db.query(AlarmZone).filter(AlarmZone.id == payload.zone_id).first()
        if not zone or zone.stream_id != payload.stream_id:
            raise HTTPException(status_code=400, detail="Zone does not belong to this stream")

    trigger_dump = payload.trigger_config.model_dump()
    trigger_type = trigger_dump["type"]

    alarm = Alarm(
        stream_id=payload.stream_id,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        severity=payload.severity,
        trigger_type=trigger_type,
        trigger_config=trigger_dump,
        zone_id=payload.zone_id,
        min_on_seconds=payload.min_on_seconds,
        min_off_seconds=payload.min_off_seconds,
        cooldown_seconds=payload.cooldown_seconds,
        schedule=[w.model_dump() for w in payload.schedule] if payload.schedule else None,
        store_events=payload.store_events,
        store_snapshot=payload.store_snapshot,
        store_clip_seconds=payload.store_clip_seconds,
        notify_channels=list(payload.notify_channels),
        webhook_url=payload.webhook_url,
    )
    db.add(alarm)
    db.commit()
    db.refresh(alarm)
    _notify_engine_reload(alarm.stream_id)
    return _serialize_alarm(alarm)


# ── Events ──────────────────────────────────────────────────────────────
# Declared before the ``/{alarm_id}`` routes so the static ``/events`` paths
# take precedence over the integer path parameter.


@router.get("/events/{event_id}/snapshot")
def get_event_snapshot(event_id: int, db: Session = Depends(get_db)):
    """Return the JPEG snapshot saved when this alarm event was triggered."""
    import os

    from fastapi.responses import FileResponse

    event = db.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alarm event not found")
    if not event.snapshot_path or not os.path.isfile(event.snapshot_path):
        raise HTTPException(status_code=404, detail="No snapshot available for this event")
    return FileResponse(event.snapshot_path, media_type="image/jpeg")


@router.get("/events", response_model=list[AlarmEventResponse])
def list_events(
    stream_id: int | None = Query(None),
    alarm_id: int | None = Query(None),
    state: str | None = Query(None),
    since: datetime | None = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[AlarmEvent]:
    q = db.query(AlarmEvent)
    if stream_id is not None:
        q = q.filter(AlarmEvent.stream_id == stream_id)
    if alarm_id is not None:
        q = q.filter(AlarmEvent.alarm_id == alarm_id)
    if state is not None:
        q = q.filter(AlarmEvent.state == state)
    if since is not None:
        q = q.filter(AlarmEvent.started_at >= since)
    return q.order_by(AlarmEvent.started_at.desc()).offset(skip).limit(limit).all()


@router.get("/events/{event_id}", response_model=AlarmEventResponse)
def get_event(event_id: int, db: Session = Depends(get_db)) -> AlarmEvent:
    event = db.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alarm event not found")
    return event


@router.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    """Permanently delete an alarm event (and its snapshot file if present)."""
    event = db.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alarm event not found")
    if event.snapshot_path and os.path.isfile(event.snapshot_path):
        try:
            os.remove(event.snapshot_path)
        except OSError:
            pass
    db.delete(event)
    db.commit()


@router.post("/events/{event_id}/ack", response_model=AlarmEventResponse)
def ack_event(event_id: int, payload: AlarmEventAck, db: Session = Depends(get_db)) -> AlarmEvent:
    event = db.query(AlarmEvent).filter(AlarmEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Alarm event not found")
    event.acknowledged_at = datetime.utcnow()
    event.acknowledged_by = payload.acknowledged_by
    event.ack_note = payload.note
    event.state = "acknowledged" if event.state == "open" else event.state
    db.commit()
    db.refresh(event)
    return event


# ── Alarms by id (declared last so /events and /zones take precedence) ──


@router.get("/{alarm_id}", response_model=AlarmResponse)
def get_alarm(alarm_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return _serialize_alarm(alarm)


@router.put("/{alarm_id}", response_model=AlarmResponse)
def update_alarm(alarm_id: int, payload: AlarmUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")

    data = payload.model_dump(exclude_unset=True)

    if "zone_id" in data and data["zone_id"] is not None:
        zone = db.query(AlarmZone).filter(AlarmZone.id == data["zone_id"]).first()
        if not zone or zone.stream_id != alarm.stream_id:
            raise HTTPException(status_code=400, detail="Zone does not belong to this stream")

    if "trigger_config" in data and data["trigger_config"] is not None:
        cfg = payload.trigger_config.model_dump()  # type: ignore[union-attr]
        alarm.trigger_type = cfg["type"]
        alarm.trigger_config = cfg
        data.pop("trigger_config")

    if "schedule" in data and data["schedule"] is not None:
        data["schedule"] = [w if isinstance(w, dict) else w.model_dump() for w in data["schedule"]]

    if "notify_channels" in data and data["notify_channels"] is not None:
        data["notify_channels"] = list(data["notify_channels"])

    for key, value in data.items():
        setattr(alarm, key, value)

    db.commit()
    db.refresh(alarm)
    _notify_engine_reload(alarm.stream_id)
    return _serialize_alarm(alarm)


@router.delete("/{alarm_id}", status_code=204)
def delete_alarm(alarm_id: int, db: Session = Depends(get_db)) -> None:
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    stream_id = alarm.stream_id
    db.delete(alarm)
    db.commit()
    _notify_engine_reload(stream_id)


@router.post("/{alarm_id}/test", response_model=AlarmTestResponse)
def test_alarm(
    alarm_id: int,
    payload: AlarmTestRequest,
    db: Session = Depends(get_db),
) -> AlarmTestResponse:
    """Replay a synthetic detection set against an alarm rule.

    Stateless: does not touch the live engine and does not persist anything.
    """
    from ...services.alarm_engine import AlarmEngine

    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")

    zone: AlarmZone | None = None
    if alarm.zone_id is not None:
        zone = db.query(AlarmZone).filter(AlarmZone.id == alarm.zone_id).first()

    detections = [d.model_dump() for d in payload.detections]
    result = AlarmEngine.evaluate_once(
        alarm_orm=alarm,
        zone_orm=zone,
        detections=detections,
        frame_shape=(payload.frame_height, payload.frame_width),
    )
    return AlarmTestResponse(**result)
