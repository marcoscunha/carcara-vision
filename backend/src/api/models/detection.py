from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


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
    metadata: dict[str, Any] = Field(validation_alias="detection_metadata")
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
