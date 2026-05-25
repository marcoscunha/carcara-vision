"""
Stream management endpoints.

This module provides REST API endpoints for managing camera streams via GStreamer
and MediaMTX, supporting RTSP, WebRTC, HLS, and other streaming protocols.
"""

import asyncio
import json
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ...api.models.benchmark import BenchmarkExportResponse
from ...api.models.benchmark import BenchmarkHistoryItem
from ...api.models.benchmark import BenchmarkHistoryResponse
from ...api.models.benchmark import BenchmarkScenario
from ...api.models.stream import StreamCreate
from ...api.models.stream import StreamReorderRequest
from ...api.models.stream import StreamResponse
from ...api.models.stream import StreamUpdate
from ...api.models.stream import StreamURLs
from ...core.config import settings
from ...core.security import AuthenticatedUser
from ...db.session import get_db
from ...models.camera import Camera
from ...models.stream import Stream
from ...services.benchmark_reporting import default_benchmark_scenario
from ...services.benchmark_reporting import export_benchmark_report
from ...services.camera_connectivity import sync_local_camera_connectivity
from ...services.camera_service import CameraService
from ...services.gstreamer import gstreamer_service
from ...services.inference_runtime import inference_metrics_service
from ...services.inference_runtime import inference_runtime_service
from ...services.inference_worker_manager import inference_worker_manager
from ...services.object_detection import ObjectDetectionService

logger = logging.getLogger(__name__)
router = APIRouter()
camera_service = CameraService()
LOCAL_CAMERA_TYPES = {"local", "usb"}
LOCAL_CAMERA_IDENTITY_FIELDS = (
    "device_id",
    "device_path",
    "physical_address",
    "usb_vendor_id",
    "usb_product_id",
    "usb_serial_number",
)


def _local_camera_identity(camera: Camera, source_config: dict | None = None) -> dict:
    identity = {}
    for field in LOCAL_CAMERA_IDENTITY_FIELDS:
        config_value = (source_config or {}).get(field)
        identity[field] = config_value if config_value is not None else getattr(camera, field, None)
    return identity


def _apply_resolved_camera_binding(camera: Camera, resolved_camera: dict | None) -> None:
    if resolved_camera is None:
        return
    for field in LOCAL_CAMERA_IDENTITY_FIELDS:
        setattr(camera, field, resolved_camera.get(field))


def _resolve_local_capture_source(camera: Camera, source_config: dict | None = None) -> dict:
    identity = _local_camera_identity(camera, source_config)
    resolved = camera_service.resolve_local_camera(**identity)
    effective = resolved or identity

    return {
        "camera_type": "local",
        "stream_url": camera.rtsp_url,
        **{field: effective.get(field) for field in LOCAL_CAMERA_IDENTITY_FIELDS},
    }


def _list_benchmark_history(output_dir: str = "./benchmark_reports", limit: int = 20) -> BenchmarkHistoryResponse:
    reports_dir = Path(output_dir).resolve()
    if not reports_dir.exists():
        return BenchmarkHistoryResponse(reports_dir=str(reports_dir), count=0, items=[])

    items: list[BenchmarkHistoryItem] = []
    json_reports = sorted(reports_dir.glob("benchmark_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for json_path in json_reports[:limit]:
        run_id = json_path.stem
        csv_path = reports_dir / f"{run_id}.csv"
        created_at: str | None = None
        scenario_name = run_id
        model_name: str | None = None
        streams_count = 0

        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            created_at = payload.get("created_at")
            scenario_name = (payload.get("scenario") or {}).get("scenario_name") or run_id
            model_name = (payload.get("scenario") or {}).get("model_name")
            per_stream = payload.get("per_stream") or []
            streams_count = len(per_stream)
        except Exception:
            logger.warning("Failed to parse benchmark report metadata: %s", json_path)

        items.append(
            BenchmarkHistoryItem(
                run_id=run_id,
                created_at=created_at,
                scenario_name=scenario_name,
                model_name=model_name,
                streams_count=streams_count,
                json_report_path=str(json_path.resolve()),
                csv_report_path=str(csv_path.resolve()) if csv_path.exists() else "",
            )
        )

    return BenchmarkHistoryResponse(reports_dir=str(reports_dir), count=len(items), items=items)


def _build_source_config_for_camera(
    camera: Camera,
    *,
    width: int,
    height: int,
    codec: str,
    source_config: dict | None = None,
) -> tuple[dict, dict | None]:
    if camera.camera_type in LOCAL_CAMERA_TYPES:
        resolved_source = _resolve_local_capture_source(camera, source_config)
        return (
            gstreamer_service.build_source_config(
                camera_type=camera.camera_type,
                rtsp_url=camera.rtsp_url,
                device_id=resolved_source.get("device_id"),
                device_path=resolved_source.get("device_path"),
                physical_address=resolved_source.get("physical_address"),
                usb_vendor_id=resolved_source.get("usb_vendor_id"),
                usb_product_id=resolved_source.get("usb_product_id"),
                usb_serial_number=resolved_source.get("usb_serial_number"),
                width=width,
                height=height,
                codec=codec,
            ),
            resolved_source,
        )

    return (
        gstreamer_service.build_source_config(
            camera_type=camera.camera_type,
            rtsp_url=camera.rtsp_url,
            device_id=camera.device_id,
            device_path=camera.device_path,
            width=width,
            height=height,
            codec=codec,
        ),
        None,
    )


def _get_detection_settings(stream: Stream) -> dict:
    metadata = stream.stream_metadata or {}
    runtime = inference_runtime_service.get()
    return {
        "enabled": bool(metadata.get("detection_enabled", False)),
        # Persisted stream metadata is authoritative; runtime is fallback.
        "model": metadata.get("detection_model") or runtime.model_name,
        "accelerator": runtime.accelerator,
        "task_type": metadata.get("detection_task_type") or getattr(runtime, "task_type", "detect"),
        "confidence": float(metadata.get("detection_confidence", 0.5)),
        "classes": metadata.get("detection_classes"),
    }


def _build_stream_detector(stream: Stream) -> ObjectDetectionService:
    """
    Return the persistent detector from the active worker when available.

    Falls back to creating a new ObjectDetectionService (slower) only if
    no worker is currently running for this stream — e.g. on-demand single
    shot detection with detection_enabled=False.
    """
    worker = inference_worker_manager.get_worker(stream.id)
    if worker is not None and worker._detector is not None:
        return worker._detector

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
        return _resolve_local_capture_source(camera, source_config)

    if source_type == "rtsp":
        return {
            "camera_type": "rtsp",
            "stream_url": source_config.get("source_uri") or camera.rtsp_url,
            "device_id": None,
            "device_path": None,
        }

    if camera.camera_type in LOCAL_CAMERA_TYPES:
        return _resolve_local_capture_source(camera, source_config)

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


async def restore_active_stream_pipelines(db: Session) -> tuple[int, int]:
    """
    Re-register active DB streams in GStreamer/MediaMTX after service restarts.

    Returns:
        Tuple of (restored_count, failed_count).
    """
    active_streams = db.query(Stream).filter(Stream.status == "active").all()
    restored = 0
    failed = 0

    for db_stream in active_streams:
        camera = db.query(Camera).filter(Camera.id == db_stream.camera_id).first()
        if camera is None:
            db_stream.status = "error"
            failed += 1
            logger.error("Cannot restore stream %s: camera %s not found", db_stream.id, db_stream.camera_id)
            continue

        metadata = dict(db_stream.stream_metadata or {})
        previous_source_config = metadata.get("source_config") or {}

        try:
            source_config, resolved_source = _build_source_config_for_camera(
                camera,
                width=int(previous_source_config.get("width") or metadata.get("width") or 640),
                height=int(previous_source_config.get("height") or metadata.get("height") or 360),
                codec=previous_source_config.get("codec") or metadata.get("codec") or "h264",
                source_config=previous_source_config,
            )

            if not db_stream.stream_name:
                db_stream.stream_name = _generate_stream_name(camera, db_stream.id)

            _apply_resolved_camera_binding(camera, resolved_source)
            metadata["source_config"] = source_config
            db_stream.stream_metadata = metadata

            # Ensure idempotent startup restore: remove stale stream if present, then add.
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
                restored += 1
                logger.info("Restored active stream '%s'", db_stream.stream_name)
            else:
                db_stream.status = "error"
                failed += 1
                logger.error("Failed restoring stream '%s'", db_stream.stream_name)
        except Exception as exc:
            db_stream.status = "error"
            failed += 1
            logger.exception("Error restoring stream %s: %s", db_stream.id, exc)

    db.commit()
    return restored, failed


async def _recover_reconnected_local_streams(db: Session) -> tuple[int, int]:
    """
    Re-register offline local streams when their camera becomes active again.

    This auto-heals the common USB detach/reattach flow where ``/dev/videoX``
    changed and streams were marked offline while the camera was disconnected.
    """
    gst_streams = await gstreamer_service.get_streams()

    candidates = (
        db.query(Stream)
        .join(Camera, Camera.id == Stream.camera_id)
        .filter(
            Camera.camera_type.in_(tuple(LOCAL_CAMERA_TYPES)),
            Camera.is_active.is_(True),
        )
        .all()
    )

    recovered = 0
    failed = 0
    failed_stream_ids: list[int] = []

    for stream in candidates:
        gst_info = gst_streams.get(stream.stream_name or "", {}) if isinstance(gst_streams, dict) else {}
        gst_status = gst_info.get("status")
        needs_recovery = stream.status in ("offline", "error") or gst_status in (None, "error")
        if not needs_recovery:
            continue

        camera = db.query(Camera).filter(Camera.id == stream.camera_id).first()
        if camera is None:
            continue

        metadata = dict(stream.stream_metadata or {})
        previous_source_config = metadata.get("source_config") or {}

        try:
            source_config, resolved_source = _build_source_config_for_camera(
                camera,
                width=int(previous_source_config.get("width") or metadata.get("width") or 640),
                height=int(previous_source_config.get("height") or metadata.get("height") or 360),
                codec=previous_source_config.get("codec") or metadata.get("codec") or "h264",
                source_config=previous_source_config,
            )

            if not stream.stream_name:
                stream.stream_name = _generate_stream_name(camera, stream.id)

            _apply_resolved_camera_binding(camera, resolved_source)
            metadata["source_config"] = source_config
            stream.stream_metadata = metadata

            # Ensure stale source is removed before re-adding updated config.
            await gstreamer_service.remove_stream(stream.stream_name)
            success = await gstreamer_service.add_stream(
                name=stream.stream_name,
                source_type=source_config["source_type"],
                source_uri=source_config.get("source_uri"),
                device_id=source_config.get("device_id"),
                device_path=source_config.get("device_path"),
                width=source_config.get("width", 640),
                height=source_config.get("height", 360),
                codec=source_config.get("codec", "h264"),
            )

            if success:
                stream.status = "active"
                inference_worker_manager.restart_worker(stream)
                recovered += 1
                logger.info("Recovered local stream '%s' after camera reconnect", stream.stream_name)
            else:
                stream.status = "error"
                failed += 1
                failed_stream_ids.append(stream.id)
                logger.warning("Failed recovering local stream '%s' after reconnect", stream.stream_name)
        except Exception as exc:
            stream.status = "error"
            failed += 1
            failed_stream_ids.append(stream.id)
            logger.exception("Error recovering local stream %s: %s", stream.id, exc)

    if recovered or failed:
        db.commit()

    if failed and settings.GSTREAMER_AUTO_RECREATE:
        restarted = await gstreamer_service.restart_service_container()
        if restarted:
            await asyncio.sleep(3)
            retry_ids = set(failed_stream_ids)
            retry_candidates = db.query(Stream).filter(Stream.id.in_(retry_ids)).all() if retry_ids else []
            failed = 0
            for stream in retry_candidates:
                camera = db.query(Camera).filter(Camera.id == stream.camera_id).first()
                if camera is None:
                    continue

                metadata = dict(stream.stream_metadata or {})
                previous_source_config = metadata.get("source_config") or {}
                try:
                    source_config, resolved_source = _build_source_config_for_camera(
                        camera,
                        width=int(previous_source_config.get("width") or metadata.get("width") or 640),
                        height=int(previous_source_config.get("height") or metadata.get("height") or 360),
                        codec=previous_source_config.get("codec") or metadata.get("codec") or "h264",
                        source_config=previous_source_config,
                    )
                    if not stream.stream_name:
                        stream.stream_name = _generate_stream_name(camera, stream.id)

                    _apply_resolved_camera_binding(camera, resolved_source)
                    metadata["source_config"] = source_config
                    stream.stream_metadata = metadata

                    await gstreamer_service.remove_stream(stream.stream_name)
                    success = await gstreamer_service.add_stream(
                        name=stream.stream_name,
                        source_type=source_config["source_type"],
                        source_uri=source_config.get("source_uri"),
                        device_id=source_config.get("device_id"),
                        device_path=source_config.get("device_path"),
                        width=source_config.get("width", 640),
                        height=source_config.get("height", 360),
                        codec=source_config.get("codec", "h264"),
                    )
                    if success:
                        stream.status = "active"
                        inference_worker_manager.restart_worker(stream)
                        recovered += 1
                        logger.info("Recovered local stream '%s' after GStreamer container restart", stream.stream_name)
                    else:
                        stream.status = "error"
                        failed += 1
                except Exception as exc:
                    stream.status = "error"
                    failed += 1
                    logger.exception("Retry recovery failed for local stream %s: %s", stream.id, exc)

            db.commit()

    return recovered, failed


def _build_stream_response(stream: Stream, host: str | None = None) -> StreamResponse:
    """Build a StreamResponse with URLs from MediaMTX."""
    detection_settings = _get_detection_settings(stream)
    metadata = stream.stream_metadata or {}
    sync_video_predictions = bool(metadata.get("sync_video_predictions", settings.VIDEO_PREDICTION_SYNC_ENABLED))
    worker = inference_worker_manager.get_worker(stream.id)
    worker_active = bool(worker and worker.is_running())
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
        worker_active=worker_active,
        stream_metadata=stream.stream_metadata,
        detection_enabled=detection_settings["enabled"],
        detection_model=detection_settings["model"],
        detection_task_type=detection_settings["task_type"],
        detection_confidence=detection_settings["confidence"],
        detection_classes=detection_settings["classes"],
        sync_video_predictions=sync_video_predictions,
        display_order=stream.display_order or 0,
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
        source_config, resolved_source = _build_source_config_for_camera(
            camera,
            width=stream.width or 640,
            height=stream.height or 360,
            codec=stream.codec or "h264",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _apply_resolved_camera_binding(camera, resolved_source)

    runtime_cfg = inference_runtime_service.get()
    default_model = runtime_cfg.model_name or settings.DEFAULT_MODEL

    stream_metadata = {
        "source_config": source_config,
        "width": stream.width or 640,
        "height": stream.height or 360,
        "codec": stream.codec or "h264",
        "detection_enabled": bool(stream.detection_enabled),
        "detection_model": stream.detection_model or default_model,
        "detection_task_type": stream.detection_task_type or "detect",
        "detection_confidence": stream.detection_confidence or 0.5,
        "detection_classes": stream.detection_classes,
        "sync_video_predictions": (
            settings.VIDEO_PREDICTION_SYNC_ENABLED
            if stream.sync_video_predictions is None
            else bool(stream.sync_video_predictions)
        ),
        **(stream.stream_metadata or {}),
    }

    # Create database record
    next_order = (db.query(sa_func.coalesce(sa_func.max(Stream.display_order), 0)).scalar() or 0) + 1
    db_stream = Stream(
        camera_id=stream.camera_id,
        stream_name=stream_name,
        status="starting",
        stream_metadata=stream_metadata,
        display_order=next_order,
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

    # Start inference worker if detection enabled
    inference_worker_manager.start_worker(db_stream)

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
    changed = sync_local_camera_connectivity(db)
    if changed:
        await _recover_reconnected_local_streams(db)

    query = db.query(Stream)

    if status_filter:
        query = query.filter(Stream.status == status_filter)

    streams = query.order_by(Stream.display_order.asc(), Stream.id.asc()).offset(skip).limit(limit).all()

    host = request.headers.get("host", "localhost").split(":")[0]
    return [_build_stream_response(s, host=host) for s in streams]


@router.post("/reorder", response_model=list[StreamResponse])
async def reorder_streams(
    payload: StreamReorderRequest,
    request: Request,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Persist a new display order for streams.

    The provided `ordered_ids` define positions 1..N (in order). Any stream not
    listed keeps its current `display_order`. Unknown IDs are ignored.
    """
    if not payload.ordered_ids:
        raise HTTPException(status_code=400, detail="ordered_ids must not be empty")

    if len(set(payload.ordered_ids)) != len(payload.ordered_ids):
        raise HTTPException(status_code=400, detail="ordered_ids must be unique")

    existing = {s.id: s for s in db.query(Stream).filter(Stream.id.in_(payload.ordered_ids)).all()}
    for position, stream_id in enumerate(payload.ordered_ids, start=1):
        stream = existing.get(stream_id)
        if stream is not None:
            stream.display_order = position

    db.commit()

    host = request.headers.get("host", "localhost").split(":")[0]
    streams = db.query(Stream).order_by(Stream.display_order.asc(), Stream.id.asc()).all()
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

    changed = sync_local_camera_connectivity(db, camera_ids={stream.camera_id})
    if changed:
        await _recover_reconnected_local_streams(db)
    db.refresh(stream)

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

    changed = sync_local_camera_connectivity(db, camera_ids={stream.camera_id})
    if changed:
        await _recover_reconnected_local_streams(db)
    db.refresh(stream)

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

    detection_keys = [
        "detection_enabled",
        "detection_model",
        "detection_task_type",
        "detection_confidence",
        "detection_classes",
        "sync_video_predictions",
    ]
    detection_changed = any(k in update_data for k in detection_keys)
    for key in detection_keys:
        if key in update_data:
            metadata[key] = update_data.pop(key)

    db_stream.stream_metadata = metadata

    for field, value in update_data.items():
        setattr(db_stream, field, value)

    db.commit()
    db.refresh(db_stream)

    # Restart inference worker when detection settings change
    if detection_changed:
        inference_worker_manager.restart_worker(db_stream)

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

    camera = db.query(Camera).filter(Camera.id == db_stream.camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    try:
        source_config, resolved_source = _build_source_config_for_camera(
            camera,
            width=source_config.get("width", 640),
            height=source_config.get("height", 360),
            codec=source_config.get("codec", "h264"),
            source_config=source_config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _apply_resolved_camera_binding(camera, resolved_source)
    metadata = dict(db_stream.stream_metadata or {})
    metadata["source_config"] = source_config
    db_stream.stream_metadata = metadata

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

    # Re-launch inference worker if detection is enabled
    inference_worker_manager.restart_worker(db_stream)

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

    # Stop inference worker if running
    inference_worker_manager.stop_worker(db_stream.id)

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


@router.get("/{stream_id}/snapshot")
async def get_stream_snapshot(
    stream_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Capture a single JPEG frame from the stream source."""
    import cv2
    from fastapi.responses import Response

    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")
    camera = db.query(Camera).filter(Camera.id == stream.camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Fast path: reuse the frame already captured by the running inference
    # worker — avoids opening a second RTSP connection.
    from ...services.inference_worker_manager import inference_worker_manager

    frame = inference_worker_manager.get_snapshot_frame(stream_id)

    # Slow path: open the stream on-demand (stream may not be running).
    if frame is None:
        capture_source = _get_capture_source(stream, camera)
        frame = camera_service.process_stream(
            capture_source["stream_url"],
            camera_type=capture_source["camera_type"],
            device_id=capture_source["device_id"],
            device_path=capture_source["device_path"],
        )

    if frame is None:
        raise HTTPException(status_code=503, detail="Could not capture frame from stream source")

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode frame")

    return Response(content=buf.tobytes(), media_type="image/jpeg")


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
    """Get realtime global and per-stream model inference metrics from active workers."""
    worker_stats = inference_worker_manager.list_stats()
    if not worker_stats:
        return {
            "global": {
                "samples": 0,
                "avg_inference_time_ms": 0.0,
                "min_inference_time_ms": 0.0,
                "max_inference_time_ms": 0.0,
                "fps": 0.0,
            },
            "per_stream": {},
        }

    per_stream: dict[int, dict] = {}
    all_avg_ms: list[float] = []

    for stats in worker_stats:
        stage_inference = (stats.get("stage_timings_ms") or {}).get("inference_engine", {})
        avg_ms = float(stats.get("avg_inference_ms", 0.0) or 0.0)
        min_ms = float(stage_inference.get("min", avg_ms) or 0.0)
        max_ms = float(stage_inference.get("max", avg_ms) or 0.0)

        stream_id = int(stats["stream_id"])
        per_stream[stream_id] = {
            "stream_id": stream_id,
            "samples": int(stats.get("frames_processed", 0) or 0),
            "avg_inference_time_ms": round(avg_ms, 2),
            "min_inference_time_ms": round(min_ms, 2),
            "max_inference_time_ms": round(max_ms, 2),
            "fps": round(float(stats.get("fps", 0.0) or 0.0), 2),
            "inference_throughput_fps": round(float(stats.get("inference_throughput_fps", 0.0) or 0.0), 2),
            "target_inference_fps": round(float(stats.get("target_inference_fps", 0.0) or 0.0), 2),
            "output_fps": round(float(stats.get("output_fps", 0.0) or 0.0), 2),
            "last_inference_time_ms": round(float(stage_inference.get("last", avg_ms) or 0.0), 2),
            "model_name": stats.get("model"),
            "accelerator": stats.get("accelerator"),
        }
        if avg_ms > 0:
            all_avg_ms.append(avg_ms)

    if all_avg_ms:
        global_avg_ms = sum(all_avg_ms) / len(all_avg_ms)
        global_min_ms = min(all_avg_ms)
        global_max_ms = max(all_avg_ms)
        global_fps = round(1000 / global_avg_ms, 2) if global_avg_ms > 0 else 0.0
    else:
        global_avg_ms = 0.0
        global_min_ms = 0.0
        global_max_ms = 0.0
        global_fps = 0.0

    return {
        "global": {
            "samples": sum(int(stats.get("frames_processed", 0) or 0) for stats in worker_stats),
            "avg_inference_time_ms": round(global_avg_ms, 2),
            "min_inference_time_ms": round(global_min_ms, 2),
            "max_inference_time_ms": round(global_max_ms, 2),
            "fps": global_fps,
        },
        "per_stream": per_stream,
    }


@router.get("/metrics/benchmark/scenario-template", response_model=BenchmarkScenario)
async def get_benchmark_scenario_template(
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Return a default benchmark scenario payload template."""
    _ = db
    return default_benchmark_scenario()


@router.post("/metrics/benchmark/export", response_model=BenchmarkExportResponse)
async def export_benchmark_metrics(
    scenario: BenchmarkScenario,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Export active worker metrics to JSON and CSV benchmark artifacts."""
    _ = db
    worker_stats = inference_worker_manager.list_stats()
    runtime = inference_runtime_service.get()
    runtime_payload = {
        "model_name": runtime.model_name,
        "accelerator": runtime.accelerator.value,
        "task_type": runtime.task_type,
        "acceleration_profile": runtime.acceleration_profile,
        "accel_preprocess_mode": runtime.accel_preprocess_mode,
        "accel_postprocess_mode": runtime.accel_postprocess_mode,
        "accel_annotate_mode": runtime.accel_annotate_mode,
        "accel_encoder_mode": runtime.accel_encoder_mode,
    }

    report = export_benchmark_report(
        scenario=scenario,
        worker_stats=worker_stats,
        runtime_config=runtime_payload,
    )
    return BenchmarkExportResponse(**report)


@router.get("/metrics/benchmark/history", response_model=BenchmarkHistoryResponse)
async def get_benchmark_history(
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """Return latest benchmark reports previously exported by the system."""
    _ = current_user
    _ = db
    return _list_benchmark_history(limit=limit)
