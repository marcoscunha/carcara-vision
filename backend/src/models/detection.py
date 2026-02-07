from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from ..db.base_class import Base


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"))
    stream_id = Column(Integer, ForeignKey("streams.id", ondelete="CASCADE"))
    frame_number = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)
    detection_model_name = Column(String)
    confidence = Column(Float)
    class_name = Column(String)
    bbox = Column(JSON)  # [x1, y1, x2, y2]
    detection_metadata = Column(JSON)  # Additional detection information

    # Relationships
    camera = relationship("Camera", back_populates="detections")
    stream = relationship("Stream", back_populates="detections")
