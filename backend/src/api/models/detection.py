from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DetectionBase(BaseModel):
    camera_id: int
    stream_id: int
    frame_number: int


class DetectionCreate(DetectionBase):
    pass


class DetectionResponse(DetectionBase):
    id: int
    detection_model_name: str
    confidence: float
    class_name: str
    bbox: list[float]
    metadata: dict[str, Any]
    timestamp: datetime

    class Config:
        from_attributes = True
