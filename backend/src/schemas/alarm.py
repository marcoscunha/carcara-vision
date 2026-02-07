from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AlarmBase(BaseModel):
    name: str
    camera_id: int
    class_name: str
    confidence_threshold: float
    region_of_interest: list[float]
    is_active: bool = True
    description: str | None = None


class AlarmCreate(AlarmBase):
    pass


class AlarmUpdate(AlarmBase):
    name: str | None = None
    camera_id: int | None = None
    class_name: str | None = None
    confidence_threshold: float | None = None
    region_of_interest: list[float] | None = None
    is_active: bool | None = None
    description: str | None = None


class AlarmResponse(AlarmBase):
    id: int
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]

    class Config:
        from_attributes = True
