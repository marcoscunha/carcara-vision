"""
Stream management endpoints.

This module provides REST API endpoints for managing camera streams via GStreamer
and MediaMTX, supporting RTSP, WebRTC, HLS, and other streaming protocols.
"""
import logging
from typing import List
from typing import Optional

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
from ...db.session import get_db
from ...models.camera import Camera
from ...models.stream import Stream
from ...services.gstreamer import gstreamer_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _generate_stream_name(camera: Camera, stream_id: int) -> str:
    """Generate a unique stream name for GStreamer/MediaMTX."""
    # Sanitize camera name for use in URLs
    safe_name = camera.name.lower().replace(" ", "_").replace("-", "_")
    return f"camera_{camera.id}_{safe_name}"


def _build_stream_response(
    stream: Stream,
    host: Optional[str] = None
) -> StreamResponse:
    """Build a StreamResponse with URLs from MediaMTX."""
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
        created_at=stream.created_at,
        updated_at=stream.updated_at
    )


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=StreamResponse)
async def create_stream(
    stream: StreamCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new stream for a camera.

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
    existing_stream = db.query(Stream).filter(
        Stream.camera_id == stream.camera_id,
        Stream.status == "active"
    ).first()

    if existing_stream:
        raise HTTPException(
            status_code=400,
            detail="An active stream already exists for this camera"
        )

    # Create stream name for GStreamer/MediaMTX
    stream_name = _generate_stream_name(camera, 0)  # Will update after commit

    # Build source configuration based on camera type
    try:
        source_config = gstreamer_service.build_source_config(
            camera_type=camera.camera_type,
            rtsp_url=camera.rtsp_url,
            device_id=camera.device_id,
            width=stream.width or 640,
            height=stream.height or 360,
            codec=stream.codec or "h264"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Create database record
    db_stream = Stream(
        camera_id=stream.camera_id,
        stream_name=stream_name,
        status="starting",
        stream_metadata={
            "source_config": source_config,
            "width": stream.width or 640,
            "height": stream.height or 360,
            "codec": stream.codec or "h264",
            **(stream.stream_metadata or {})
        }
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
        width=source_config["width"],
        height=source_config["height"],
        codec=source_config["codec"]
    )

    if success:
        db_stream.status = "active"
        logger.info(f"Stream '{stream_name}' created and registered with GStreamer")
    else:
        db_stream.status = "error"
        logger.error(f"Failed to register stream '{stream_name}' with GStreamer")

    db.commit()
    db.refresh(db_stream)

    # Get host from request for URL generation
    host = request.headers.get("host", "localhost").split(":")[0]

    return _build_stream_response(db_stream, host=host)


@router.get("/", response_model=List[StreamResponse])
async def list_streams(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """List all streams with their RTSP URLs."""
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
    db: Session = Depends(get_db)
):
    """Get a specific stream by ID with its RTSP URLs."""
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    host = request.headers.get("host", "localhost").split(":")[0]
    return _build_stream_response(stream, host=host)


@router.get("/{stream_id}/urls")
async def get_stream_urls(
    stream_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Get all available URLs for a stream."""
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
    db: Session = Depends(get_db)
):
    """Update a stream's status or metadata."""
    db_stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if db_stream is None:
        raise HTTPException(status_code=404, detail="Stream not found")

    for field, value in stream_update.dict(exclude_unset=True).items():
        setattr(db_stream, field, value)

    db.commit()
    db.refresh(db_stream)

    host = request.headers.get("host", "localhost").split(":")[0]
    return _build_stream_response(db_stream, host=host)


@router.post("/{stream_id}/restart", response_model=StreamResponse)
async def restart_stream(
    stream_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Restart a stream by re-registering it with GStreamer."""
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
        width=source_config.get("width", 640),
        height=source_config.get("height", 360),
        codec=source_config.get("codec", "h264")
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
    db: Session = Depends(get_db)
):
    """Delete a stream and remove it from GStreamer."""
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
            "paths": [p.get("name") for p in mediamtx_paths.get("items", [])]
        }
    else:
        raise HTTPException(
            status_code=503,
            detail="GStreamer or MediaMTX service is not available"
        )


# Legacy endpoint for backward compatibility
@router.get("/health/go2rtc")
async def check_go2rtc_health_legacy():
    """Legacy endpoint - redirects to GStreamer health check."""
    return await check_gstreamer_health()
