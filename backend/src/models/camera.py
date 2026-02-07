from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from ..db.base_class import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    camera_type = Column(String, default="rtsp")  # rtsp or local
    device_id = Column(Integer, nullable=True)  # For local cameras (volatile V4L2 index)
    device_path = Column(String, nullable=True)  # Persistent device path (e.g. /dev/v4l/by-id/...)
    rtsp_url = Column(String, unique=True, index=True, nullable=True)  # For RTSP cameras
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships - cascade delete all related records when camera is deleted
    streams = relationship("Stream", back_populates="camera", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="camera", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="camera", cascade="all, delete-orphan")
    rois = relationship("RegionOfInterest", back_populates="camera", cascade="all, delete-orphan")
    streams = relationship("Stream", back_populates="camera", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="camera", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="camera", cascade="all, delete-orphan")
    rois = relationship("RegionOfInterest", back_populates="camera", cascade="all, delete-orphan")
