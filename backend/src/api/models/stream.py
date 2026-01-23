from datetime import datetime
from typing import Any
from typing import Dict
from typing import Optional

from pydantic import BaseModel


class StreamBase(BaseModel):
    camera_id: Optional[int] = None
    stream_metadata: Optional[Dict[str, Any]] = None


class StreamCreate(StreamBase):
    """Schema for creating a new stream."""
    width: Optional[int] = 640
    height: Optional[int] = 360
    codec: Optional[str] = "h264"


class StreamUpdate(BaseModel):
    status: Optional[str] = None
    stream_metadata: Optional[Dict[str, Any]] = None


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
    stream_name: Optional[str] = None
    urls: Optional[StreamURLs] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
