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
    detection_enabled: bool | None = False
    detection_model: str | None = "yolov8n"
    detection_task_type: str | None = "detect"
    detection_confidence: float | None = 0.5
    detection_classes: list[int] | None = None


class StreamUpdate(BaseModel):
    status: str | None = None
    stream_metadata: dict[str, Any] | None = None
    detection_enabled: bool | None = None
    detection_model: str | None = None
    detection_task_type: str | None = None
    detection_confidence: float | None = None
    detection_classes: list[int] | None = None


class StreamURLs(BaseModel):
    """Available stream URLs for different protocols."""

    rtsp: str
    webrtc: str
    hls: str
    mse: str
    mjpeg: str
    ws: str
    # Annotated stream (server-side AI overlay)
    annotated_rtsp: str = ""
    annotated_webrtc: str = ""
    annotated_hls: str = ""


class StreamResponse(StreamBase):
    id: int
    status: str
    current_frame: int
    stream_name: str | None = None
    urls: StreamURLs | None = None
    worker_active: bool = False
    stream_metadata: dict[str, Any] | None = None
    detection_enabled: bool
    detection_model: str
    detection_task_type: str
    detection_confidence: float
    detection_classes: list[int] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
