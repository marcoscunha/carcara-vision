from datetime import datetime

from pydantic import BaseModel


class ROIBase(BaseModel):
    camera_id: int
    name: str
    points: list[float]  # [x1, y1, x2, y2, ...]
    is_active: bool = True


class ROICreate(ROIBase):
    pass


class ROIUpdate(ROIBase):
    name: str | None = None
    points: list[float] | None = None
    is_active: bool | None = None


class ROIResponse(ROIBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
