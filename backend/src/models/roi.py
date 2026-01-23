from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import relationship

from ..db.base_class import Base


class RegionOfInterest(Base):
    __tablename__ = "roi"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    camera_id = Column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"))
    points = Column(JSON)  # Store as array of points
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    camera = relationship("Camera", back_populates="rois")
