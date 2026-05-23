"""Pydantic schemas for the alarms subsystem (v2).

Trigger configurations are modelled as a discriminated union so the API can
validate per-trigger-type parameters strictly while keeping the underlying
``trigger_config`` column as a flexible JSON blob.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003  — Pydantic v2 needs this at runtime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

# ── Trigger configurations ──────────────────────────────────────────────


class ClassPresentTrigger(BaseModel):
    """Fires while at least one detection of any listed class is present
    above ``min_confidence``."""

    type: Literal["class_present"] = "class_present"
    class_names: list[str] = Field(..., min_length=1)
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)


class ClassCountTrigger(BaseModel):
    """Fires when the number of concurrent detections of the listed classes
    satisfies ``count op threshold``."""

    type: Literal["class_count"] = "class_count"
    class_names: list[str] = Field(..., min_length=1)
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)
    count_op: Literal[">=", ">", "==", "<=", "<"] = ">="
    count_threshold: int = Field(..., ge=0)


class ClassAbsentForTrigger(BaseModel):
    """Fires when no detection of the listed classes has been seen for at
    least ``absent_seconds`` while the alarm is otherwise eligible
    (schedule, active)."""

    type: Literal["class_absent_for"] = "class_absent_for"
    class_names: list[str] = Field(..., min_length=1)
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)
    absent_seconds: float = Field(..., gt=0.0)


class ZoneEnterTrigger(BaseModel):
    """Fires when a new ``track_id`` enters the alarm's zone. Requires the
    alarm to have ``zone_id`` set."""

    type: Literal["zone_enter"] = "zone_enter"
    class_names: list[str] = Field(..., min_length=1)
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)


class DwellTrigger(BaseModel):
    """Fires when at least one ``track_id`` has been continuously inside the
    alarm's zone for ``dwell_seconds``. Requires the alarm to have
    ``zone_id`` set."""

    type: Literal["dwell"] = "dwell"
    class_names: list[str] = Field(..., min_length=1)
    min_confidence: float = Field(0.5, ge=0.0, le=1.0)
    dwell_seconds: float = Field(..., gt=0.0)


TriggerConfig = Annotated[
    ClassPresentTrigger | ClassCountTrigger | ClassAbsentForTrigger | ZoneEnterTrigger | DwellTrigger,
    Field(discriminator="type"),
]


# ── Schedule ────────────────────────────────────────────────────────────


class ScheduleWindow(BaseModel):
    """A weekly schedule window. ``weekdays`` uses 0=Mon..6=Sun (Python
    ``date.weekday()``). Hours are local server time in 24h."""

    weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    start_hour: int = Field(0, ge=0, le=23)
    end_hour: int = Field(24, ge=1, le=24)


# ── Zones ───────────────────────────────────────────────────────────────


Point = Annotated[list[float], Field(min_length=2, max_length=2)]


class AlarmZoneBase(BaseModel):
    stream_id: int
    name: str
    polygon: list[Point] = Field(..., min_length=3)
    is_active: bool = True


class AlarmZoneCreate(AlarmZoneBase):
    pass


class AlarmZoneUpdate(BaseModel):
    name: str | None = None
    polygon: list[Point] | None = None
    is_active: bool | None = None


class AlarmZoneResponse(AlarmZoneBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Alarms ──────────────────────────────────────────────────────────────


Severity = Literal["info", "warning", "critical"]
NotifyChannel = Literal["ws", "webhook"]


class AlarmBase(BaseModel):
    stream_id: int
    name: str
    description: str | None = None
    is_active: bool = True
    severity: Severity = "warning"

    trigger_config: TriggerConfig
    zone_id: int | None = None

    min_on_seconds: float = Field(0.0, ge=0.0)
    min_off_seconds: float = Field(2.0, ge=0.0)
    cooldown_seconds: float = Field(0.0, ge=0.0)

    schedule: list[ScheduleWindow] | None = None

    store_events: bool = True
    store_snapshot: bool = True
    store_clip_seconds: int = Field(0, ge=0)
    notify_channels: list[NotifyChannel] = Field(default_factory=lambda: ["ws"])
    webhook_url: str | None = None

    @model_validator(mode="after")
    def _zone_required_for_spatial_triggers(self) -> AlarmBase:
        ttype = getattr(self.trigger_config, "type", None)
        if ttype in {"zone_enter", "dwell"} and self.zone_id is None:
            raise ValueError(f"trigger_type '{ttype}' requires zone_id to be set")
        return self


class AlarmCreate(AlarmBase):
    pass


class AlarmUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None
    severity: Severity | None = None
    trigger_config: TriggerConfig | None = None
    zone_id: int | None = None
    min_on_seconds: float | None = Field(None, ge=0.0)
    min_off_seconds: float | None = Field(None, ge=0.0)
    cooldown_seconds: float | None = Field(None, ge=0.0)
    schedule: list[ScheduleWindow] | None = None
    store_events: bool | None = None
    store_snapshot: bool | None = None
    store_clip_seconds: int | None = Field(None, ge=0)
    notify_channels: list[NotifyChannel] | None = None
    webhook_url: str | None = None


class AlarmResponse(AlarmBase):
    id: int
    trigger_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Alarm events ────────────────────────────────────────────────────────


EventState = Literal["open", "closed", "acknowledged", "resolved"]


class AlarmEventResponse(BaseModel):
    id: int
    alarm_id: int
    stream_id: int
    zone_id: int | None
    state: EventState
    started_at: datetime
    ended_at: datetime | None
    peak_confidence: float | None
    peak_count: int | None
    matched_classes: dict[str, int] | None
    matched_track_ids: list[int] | None
    rule_snapshot: dict
    snapshot_path: str | None
    clip_path: str | None
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    ack_note: str | None

    model_config = ConfigDict(from_attributes=True)

    @computed_field  # type: ignore[misc]
    @property
    def has_snapshot(self) -> bool:
        import os

        return bool(self.snapshot_path and os.path.isfile(self.snapshot_path))


class AlarmEventAck(BaseModel):
    acknowledged_by: str
    note: str | None = None
