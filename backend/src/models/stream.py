from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import relationship

from ..db.base_class import Base


class Stream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"))
    stream_name = Column(String, unique=True, index=True)  # Unique name for go2rtc
    status = Column(String)  # active, paused, stopped
    current_frame = Column(Integer, default=0)
    display_order = Column(Integer, default=0, nullable=False, index=True)
    stream_metadata = Column(JSON)  # Store additional stream information
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    camera = relationship("Camera", back_populates="streams")
    detections = relationship("Detection", back_populates="stream", cascade="all, delete-orphan")
