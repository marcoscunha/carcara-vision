from datetime import datetime

from pydantic import BaseModel


class CameraBase(BaseModel):
    name: str
    camera_type: str = "rtsp"
    device_id: int | None = None
    device_path: str | None = None  # Persistent device path (e.g. /dev/v4l/by-id/...)
    rtsp_url: str | None = None
    is_active: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: str | None = None
    camera_type: str | None = None
    device_id: int | None = None
    device_path: str | None = None
    rtsp_url: str | None = None
    is_active: bool | None = None


class CameraResponse(CameraBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
