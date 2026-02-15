"""
Stream management endpoints.

This module provides REST API endpoints for managing camera streams via GStreamer
and MediaMTX, supporting RTSP, WebRTC, HLS, and other streaming protocols.
"""

import logging
import time
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from sqlalchemy.orm import Session

from ...api.models.stream import StreamCreate
from ...api.models.stream import StreamResponse
from ...api.models.stream import StreamUpdate
from ...api.models.stream import StreamURLs
from ...core.config import settings
from ...core.security import AuthenticatedUser
from ...db.session import get_db
from ...models.camera import Camera
from ...models.stream import Stream
from ...services.camera_service import CameraService
from ...services.gstreamer import gstreamer_service
from ...services.inference_runtime import inference_metrics_service
from ...services.inference_runtime import inference_runtime_service
from ...services.object_detection import ObjectDetectionService

logger = logging.getLogger(__name__)
router = APIRouter()
camera_service = CameraService()


def _get_detection_settings(stream: Stream) -> dict:
    metadata = stream.stream_metadata or {}
    runtime = inference_runtime_service.get()
    return {
        "enabled": bool(metadata.get("detection_enabled", False)),
        "model": runtime.model_name,
        "accelerator": runtime.accelerator,
        "confidence": float(metadata.get("detection_confidence", 0.5)),
        "classes": metadata.get("detection_classes"),
    }


def _build_stream_detector(stream: Stream) -> ObjectDetectionService:
    """Build detection service configured for a specific stream."""
    detection_settings = _get_detection_settings(stream)
    return ObjectDetectionService(
        model_name=detection_settings["model"],
        accelerator=detection_settings["accelerator"],
    )


def _get_capture_source(stream: Stream, camera: Camera) -> dict:
    """Resolve capture source prioritizing stream source_config over camera snapshot fields."""
    metadata = stream.stream_metadata or {}
    source_config = metadata.get("source_config") or {}
    source_type = source_config.get("source_type")

    if source_type == "v4l2":
        return {
            "camera_type": "local",
            "stream_url": camera.rtsp_url,
            "device_id": source_config.get("device_id", camera.device_id),
            "device_path": source_config.get("device_path") or getattr(camera, "device_path", None),
        }

    if source_type == "rtsp":
        return {
            "camera_type": "rtsp",
            "stream_url": source_config.get("source_uri") or camera.rtsp_url,
            "device_id": None,
            "device_path": None,
        }

    return {
        "camera_type": camera.camera_type,
        "stream_url": camera.rtsp_url,
        "device_id": camera.device_id,
        "device_path": getattr(camera, "device_path", None),
    }


def _get_internal_mediamtx_host() -> str:
    parsed = urlparse(settings.MEDIAMTX_API_URL)
    return parsed.hostname or "mediamtx"


def _detect_stream_frame(stream: Stream, camera: Camera, capture_source_override: dict | None = None) -> dict:
    """Capture one frame from stream camera and run detection."""
    capture_source = capture_source_override or _get_capture_source(stream, camera)
    frame = camera_service.process_stream(
        capture_source["stream_url"],
        camera_type=capture_source["camera_type"],
        device_id=capture_source["device_id"],
        device_path=capture_source["device_path"],
    )
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not capture frame from stream source")

    detector = _build_stream_detector(stream)
    detection_settings = _get_detection_settings(stream)
    detector.set_confidence_threshold(detection_settings["confidence"])
    classes = detection_settings["classes"] if detection_settings["classes"] else None
    detections = detector.detect(frame, classes=classes)

    stats = detector.get_statistics()
    inference_metrics_service.record(
        stream_id=stream.id,
        inference_time_ms=stats.get("average_inference_time_ms", 0),
        model_name=detection_settings["model"],
        accelerator=stats.get("accelerator", "cpu"),
    )
    classes_found = sorted({d["class_name"] for d in detections})

    return {
        "stream_id": stream.id,
        "camera_id": stream.camera_id,
        "model": detection_settings["model"],
        "confidence_threshold": detection_settings["confidence"],
        "classes_filter": detection_settings["classes"],
        "detections_count": len(detections),
        "classes_found": classes_found,
        "detections": detections,
        "performance": {
            "inference_time_ms": stats.get("average_inference_time_ms", 0),
            "fps": stats.get("fps", 0),
            "device": stats.get("device", "cpu"),
            "accelerator": stats.get("accelerator", "cpu"),
        },
    }


def _hardware_and_perf_info(stream: Stream) -> dict:
    """Collect hardware usage and baseline inference performance info."""
    detector = _build_stream_detector(stream)
    hardware = detector.get_hardware_info()

    import numpy as np

    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    timings = []
    for _ in range(5):
        start = time.perf_counter()
        detector.detect(dummy)
        elapsed = (time.perf_counter() - start) * 1000
        timings.append(elapsed)

    avg_ms = sum(timings) / len(timings) if timings else 0
    detection_settings = _get_detection_settings(stream)
    return {
        "stream_id": stream.id,
        "model": detection_settings["model"],
        "hardware": hardware,
        "performance": {
            "avg_inference_time_ms": round(avg_ms, 2),
            "min_inference_time_ms": round(min(timings), 2) if timings else 0,
            "max_inference_time_ms": round(max(timings), 2) if timings else 0,
            "estimated_fps": round(1000 / avg_ms, 2) if avg_ms > 0 else 0,
            "samples": len(timings),
        },
    }


def _generate_stream_name(camera: Camera, stream_id: int) -> str:
    """Generate a unique stream name for GStreamer/MediaMTX."""
    # Sanitize camera name for use in URLs
    safe_name = camera.name.lower().replace(" ", "_").replace("-", "_")
    return f"camera_{camera.id}_{stream_id}_{safe_name}"


def _build_stream_response(stream: Stream, host: str | None = None) -> StreamResponse:
    """Build a StreamResponse with URLs from MediaMTX."""
    detection_settings = _get_detection_settings(stream)
    urls = None
    if stream.stream_name:
        url_dict = gstreamer_service.get_stream_urls(stream.stream_name, host=host)
        urls = StreamURLs(**url_dict)

    return StreamResponse(
        id=stream.id,
        camera_id=stream.camera_id,
        status=stream.status,
        current_frame=stream.current_frame or 0,
        stream_name=stream.stream_name,
        urls=urls,
        stream_metadata=stream.stream_metadata,
        detection_enabled=detection_settings["enabled"],
        detection_model=detection_settings["model"],
        detection_confidence=detection_settings["confidence"],
        detection_classes=detection_settings["classes"],
        created_at=stream.created_at,
        updated_at=stream.updated_at,
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=StreamResponse)
async def create_stream(
    stream: StreamCreate,
    request: Request,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """
    Create a new stream for a camera. Requires authentication.

    This endpoint:
    1. Creates a stream record in the database
    2. Registers the camera source with GStreamer pipeline manager
    3. Returns stream URLs for different protocols (RTSP, WebRTC, HLS, etc.)
    """
    # Verify camera exists
    camera = db.query(Camera).filter(Camera.id == stream.camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Generate unique stream name
    existing_stream = db.query(Stream).filter(Stream.camera_id == stream.camera_id, Stream.status == "active").first()

    if existing_stream:
        raise HTTPException(status_code=400, detail="An active stream already exists for this camera")

    # Create stream name for GStreamer/MediaMTX
    stream_name = _generate_stream_name(camera, 0)  # Will update after commit

    # Build source configuration based on camera type
    try:
        source_config = gstreamer_service.build_source_config(
            camera_type=camera.camera_type,
            rtsp_url=camera.rtsp_url,
            device_id=camera.device_id,
            device_path=camera.device_path,
            width=stream.width or 640,
            height=stream.height or 360,
            codec=stream.codec or "h264",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    stream_metadata = {
        "source_config": source_config,
        "width": stream.width or 640,
        "height": stream.height or 360,
        "codec": stream.codec or "h264",
        "detection_enabled": bool(stream.detection_enabled),
        "detection_model": stream.detection_model or "yolov8n.pt",
        "detection_confidence": stream.detection_confidence or 0.5,
        "detection_classes": stream.detection_classes,
        **(stream.stream_metadata or {}),
    }

    # Create database record
    db_stream = Stream(
        camera_id=stream.camera_id,
        stream_name=stream_name,
        status="starting",
        stream_metadata=stream_metadata,
    )
    db.add(db_stream)
    db.commit()
    db.refresh(db_stream)

    # Update stream name with actual ID
    stream_name = _generate_stream_name(camera, db_stream.id)
    db_stream.stream_name = stream_name

    # Register stream with GStreamer pipeline manager
    success = await gstreamer_service.add_stream(
        name=stream_name,
        source_type=source_config["source_type"],
        source_uri=source_config.get("source_uri"),
        device_id=source_config.get("device_id"),
        device_path=source_config.get("device_path"),
        width=source_config["width"],
        height=source_config["height"],
        codec=source_config["codec"],
    )

    if success:
        db_stream.status = "active"
        logger.info(f"Stream '{stream_name}' created and registered with GStreamer")
    else:
        db_stream.status = "error"
        logger.error(f"Failed to register stream '{stream_name}' with GStreamer")
        db.commit()
        db.refresh(db_stream)
        raise HTTPException(status_code=502, detail=f"Failed to start stream pipeline for '{stream_name}'")

    db.commit()
    db.refresh(db_stream)

    # Get host from request for URL generation
    host = request.headers.get("host", "localhost").split(":")[0]

    return _build_stream_response(db_stream, host=host)


@router.get("/", response_model=list[StreamResponse])
async def list_streams(
    request: Request,
    current_user: AuthenticatedUser,
    skip: int = 0,
    limit: int = 100,
    status_filter: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """List all streams with their RTSP URLs. Requires authentication."""
    query = db.query(Stream)

    if status_filter:
        query = query.filter(Stream.status == status_filter)

    streams = query.offset(skip).limit(limit).all()

    host = request.headers.get("host", "localhost").split(":")[0]
    return [_build_stream_response(s, host=host) for s in streams]


@router.get("/{stream_id}", response_model=StreamResponse)
async def get_stream(
    stream_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Get a specific stream by ID with its RTSP URLs. Requires authentication."""
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    host = request.headers.get("host", "localhost").split(":")[0]
    return _build_stream_response(stream, host=host)


@router.get("/{stream_id}/urls")
async def get_stream_urls(
    stream_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Get all available URLs for a stream. Requires authentication."""
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    if not stream.stream_name:
        raise HTTPException(status_code=400, detail="Stream not registered with GStreamer")

    host = request.headers.get("host", "localhost").split(":")[0]
    return gstreamer_service.get_stream_urls(stream.stream_name, host=host)


@router.put("/{stream_id}", response_model=StreamResponse)
async def update_stream(
    stream_id: int,
    stream_update: StreamUpdate,
    request: Request,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Update a stream's status or metadata. Requires authentication."""
    db_stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if db_stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    update_data = stream_update.dict(exclude_unset=True)
    metadata = dict(db_stream.stream_metadata or {})

    if "stream_metadata" in update_data and update_data["stream_metadata"] is not None:
        metadata.update(update_data.pop("stream_metadata"))

    detection_keys = ["detection_enabled", "detection_model", "detection_confidence", "detection_classes"]
    for key in detection_keys:
        if key in update_data:
            metadata[key] = update_data.pop(key)

    db_stream.stream_metadata = metadata

    for field, value in update_data.items():
        setattr(db_stream, field, value)

    db.commit()
    db.refresh(db_stream)

    host = request.headers.get("host", "localhost").split(":")[0]
    return _build_stream_response(db_stream, host=host)


@router.post("/{stream_id}/restart", response_model=StreamResponse)
async def restart_stream(
    stream_id: int,
    request: Request,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Restart a stream by re-registering it with GStreamer. Requires authentication."""
    db_stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if db_stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    if not db_stream.stream_name:
        raise HTTPException(status_code=400, detail="Stream not properly configured")

    # Get source config from metadata
    source_config = db_stream.stream_metadata.get("source_config") if db_stream.stream_metadata else None
    if not source_config:
        raise HTTPException(status_code=400, detail="Stream source configuration not found")

    # Remove and re-add stream
    await gstreamer_service.remove_stream(db_stream.stream_name)
    success = await gstreamer_service.add_stream(
        name=db_stream.stream_name,
        source_type=source_config["source_type"],
        source_uri=source_config.get("source_uri"),
        device_id=source_config.get("device_id"),
        device_path=source_config.get("device_path"),
        width=source_config.get("width", 640),
        height=source_config.get("height", 360),
        codec=source_config.get("codec", "h264"),
    )

    if success:
        db_stream.status = "active"
        logger.info(f"Stream '{db_stream.stream_name}' restarted")
    else:
        db_stream.status = "error"
        logger.error(f"Failed to restart stream '{db_stream.stream_name}'")

    db.commit()
    db.refresh(db_stream)

    host = request.headers.get("host", "localhost").split(":")[0]
    return _build_stream_response(db_stream, host=host)


@router.delete("/{stream_id}")
async def delete_stream(
    stream_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Delete a stream and remove it from GStreamer. Requires authentication."""
    db_stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if db_stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    # Remove from GStreamer if registered
    if db_stream.stream_name:
        await gstreamer_service.remove_stream(db_stream.stream_name)
        logger.info(f"Stream '{db_stream.stream_name}' removed from GStreamer")

    db.delete(db_stream)
    db.commit()
    return {"message": "Stream deleted successfully"}


@router.get("/health/gstreamer")
async def check_gstreamer_health():
    """Check if GStreamer and MediaMTX services are available."""
    is_healthy = await gstreamer_service.health_check()

    if is_healthy:
        streams = await gstreamer_service.get_streams()
        mediamtx_paths = await gstreamer_service.get_mediamtx_paths()
        # GStreamer API returns streams as {stream_name: stream_info, ...}
        stream_names = list(streams.keys()) if isinstance(streams, dict) else []
        return {
            "status": "healthy",
            "gstreamer_streams": len(stream_names),
            "mediamtx_paths": len(mediamtx_paths.get("items", [])),
            "streams": stream_names,
            "paths": [p.get("name") for p in mediamtx_paths.get("items", [])],
        }
    else:
        raise HTTPException(status_code=503, detail="GStreamer or MediaMTX service is not available")


@router.get("/{stream_id}/detections")
async def detect_objects_for_stream(
    stream_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Run one-shot object detection for a stream using its configured model."""
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    camera = db.query(Camera).filter(Camera.id == stream.camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    return _detect_stream_frame(stream, camera)


@router.get("/{stream_id}/ml-info")
async def get_stream_ml_info(
    stream_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Get hardware capabilities and inference performance for stream model."""
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    return _hardware_and_perf_info(stream)


@router.get("/{stream_id}/metrics")
async def get_stream_realtime_metrics(
    stream_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Get realtime model inference metrics for one stream."""
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    return inference_metrics_service.snapshot(stream_id=stream_id)


@router.get("/metrics/realtime")
async def get_global_realtime_metrics(
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Get realtime global and per-stream model inference metrics."""
    active_streams = db.query(Stream).filter(Stream.status == "active").all()

    for stream in active_streams:
        detection_settings = _get_detection_settings(stream)
        if not detection_settings["enabled"]:
            continue
        if not stream.stream_name:
            continue

        camera = db.query(Camera).filter(Camera.id == stream.camera_id).first()
        if camera is None:
            continue

        mediamtx_host = _get_internal_mediamtx_host()
        rtsp_stream_url = f"rtsp://{mediamtx_host}:{gstreamer_service.rtsp_port}/{stream.stream_name}"

        try:
            _detect_stream_frame(
                stream,
                camera,
                capture_source_override={
                    "camera_type": "rtsp",
                    "stream_url": rtsp_stream_url,
                    "device_id": None,
                    "device_path": None,
                },
            )
        except HTTPException as exc:
            if exc.status_code != 400:
                logger.warning(f"Failed to update realtime inference metrics for stream {stream.id}: {exc}")
        except Exception as exc:
            logger.warning(f"Failed to update realtime inference metrics for stream {stream.id}: {exc}")

    return inference_metrics_service.snapshot()
