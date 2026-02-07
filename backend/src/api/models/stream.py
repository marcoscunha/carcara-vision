from datetime import datetime
from typing import Any

from pydantic import BaseModel


class StreamBase(BaseModel):
    camera_id: int | None = None
    stream_metadata: dict[str, Any] | None = None


class StreamCreate(StreamBase):
    """Schema for creating a new stream."""

    width: int | None = 640
    height: int | None = 360
    codec: str | None = "h264"


class StreamUpdate(BaseModel):
    status: str | None = None
    stream_metadata: dict[str, Any] | None = None


class StreamURLs(BaseModel):
    """Available stream URLs for different protocols."""

    rtsp: str
    webrtc: str
    hls: str
    mse: str
    mjpeg: str
    ws: str


class StreamResponse(StreamBase):
    id: int
    status: str
    current_frame: int
    stream_name: str | None = None
    urls: StreamURLs | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
