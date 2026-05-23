"""SQLAlchemy models for the alarms subsystem (v2).

The alarm subsystem is stream-scoped:

* ``Alarm`` is a rule attached to a single stream. Its evaluation criteria
  are encoded by a ``trigger_type`` discriminator plus a free-form
  ``trigger_config`` JSON blob (see ``schemas.alarm`` for the discriminated
  union).
* ``AlarmZone`` is a named polygon (normalized [0..1] coordinates) on a
  stream that rules can optionally reference for spatial filtering.
* ``AlarmEvent`` is one lifecycle of a fired rule (open → closed,
  optionally acknowledged) with snapshot/clip artefacts and the rule
  snapshot captured at trigger time.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from ..db.base_class import Base


class AlarmZone(Base):
    __tablename__ = "alarm_zones"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    polygon = Column(JSON, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    stream = relationship("Stream", back_populates="alarm_zones")
    alarms = relationship("Alarm", back_populates="zone")
    events = relationship("AlarmEvent", back_populates="zone")


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    severity = Column(String, nullable=False, default="warning")  # info|warning|critical

    trigger_type = Column(String, nullable=False)
    trigger_config = Column(JSON, nullable=False)
    zone_id = Column(Integer, ForeignKey("alarm_zones.id", ondelete="SET NULL"), nullable=True)

    min_on_seconds = Column(Float, nullable=False, default=0.0)
    min_off_seconds = Column(Float, nullable=False, default=2.0)
    cooldown_seconds = Column(Float, nullable=False, default=0.0)

    schedule = Column(JSON, nullable=True)

    store_events = Column(Boolean, nullable=False, default=True)
    store_snapshot = Column(Boolean, nullable=False, default=True)
    store_clip_seconds = Column(Integer, nullable=False, default=0)
    notify_channels = Column(JSON, nullable=False, default=lambda: ["ws"])
    webhook_url = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    stream = relationship("Stream", back_populates="alarms")
    zone = relationship("AlarmZone", back_populates="alarms")
    events = relationship("AlarmEvent", back_populates="alarm", cascade="all, delete-orphan")


class AlarmEvent(Base):
    __tablename__ = "alarm_events"

    id = Column(Integer, primary_key=True, index=True)
    alarm_id = Column(Integer, ForeignKey("alarms.id", ondelete="CASCADE"), nullable=False, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey("alarm_zones.id", ondelete="SET NULL"), nullable=True)

    state = Column(String, nullable=False, default="open", index=True)  # open|closed|acknowledged|resolved
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = Column(DateTime, nullable=True)

    peak_confidence = Column(Float, nullable=True)
    peak_count = Column(Integer, nullable=True)
    matched_classes = Column(JSON, nullable=True)
    matched_track_ids = Column(JSON, nullable=True)

    rule_snapshot = Column(JSON, nullable=False)
    snapshot_path = Column(String, nullable=True)
    clip_path = Column(String, nullable=True)

    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)
    ack_note = Column(String, nullable=True)

    alarm = relationship("Alarm", back_populates="events")
    zone = relationship("AlarmZone", back_populates="events")
