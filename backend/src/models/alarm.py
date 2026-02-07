from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.base_class import Base


class Alarm(Base):
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    camera_id = Column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"))
    class_name = Column(String)
    confidence_threshold = Column(Float)
    region_of_interest = Column(JSON)  # Store as array of points
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    camera = relationship("Camera", back_populates="alarms")

    # Relationships
    camera = relationship("Camera", back_populates="alarms")
