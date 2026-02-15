from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...api.models.camera import CameraCreate
from ...api.models.camera import CameraResponse
from ...api.models.camera import CameraUpdate
from ...core.security import AuthenticatedUser
from ...db.session import get_db
from ...models.camera import Camera
from ...services.camera_service import CameraService
from ...services.object_detection import ObjectDetectionService

router = APIRouter()
detection_service = ObjectDetectionService()


@router.post("/", response_model=CameraResponse)
def create_camera(
    camera: CameraCreate,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Create a new camera. Requires authentication."""
    # For local cameras, resolve the current device_id from device_path
    device_id = camera.device_id
    device_path = camera.device_path
    if camera.camera_type in ("local", "usb") and device_path:
        resolved_id = CameraService.resolve_device_index(device_path)
        if resolved_id is not None:
            device_id = resolved_id

    db_camera = Camera(
        name=camera.name,
        camera_type=camera.camera_type,
        device_id=device_id,
        device_path=device_path,
        rtsp_url=camera.rtsp_url,
        is_active=camera.is_active,
    )
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera


@router.get("/", response_model=list[CameraResponse])
def list_cameras(
    current_user: AuthenticatedUser,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all cameras. Requires authentication."""
    cameras = db.query(Camera).offset(skip).limit(limit).all()
    return cameras


class CameraInfo(BaseModel):
    device_id: int
    device_path: str  # Persistent path (e.g. /dev/v4l/by-id/...)
    physical_address: str | None
    usb_id: str | None
    name: str
    friendly_name: str | None
    resolution: list[int]
    fps: float
    is_available: bool
    supported_resolutions: list[tuple[int, int]]


@router.get("/scan", response_model=list[CameraInfo])
async def scan_local_cameras(
    current_user: AuthenticatedUser,
    max_devices: int = 10,
    camera_service: CameraService = Depends(lambda: CameraService()),
) -> list[CameraInfo]:
    """
    Scan for available local camera devices. Requires authentication.

    Args:
        max_devices: Maximum number of devices to scan (default: 10)

    Returns:
        List of available camera devices with their properties
    """
    try:
        cameras = camera_service.scan_local_cameras(max_devices)
        for camera in cameras:
            if isinstance(camera["resolution"], tuple):
                camera["resolution"] = list(camera["resolution"])
        return [CameraInfo(**camera) for camera in cameras]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan for cameras: {e!s}")


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(
    camera_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Get a specific camera by ID. Requires authentication."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.get("/{camera_id}/status", response_model=dict)
def get_camera_status(
    camera_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """
    Get the status of a specific camera by ID. Requires authentication.

    Args:
        camera_id: ID of the camera.

    Returns:
        A dictionary containing the camera's status.
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Example logic to determine camera status
    status = "active" if camera.is_active else "inactive"
    return {"status": status}


@router.put("/{camera_id}", response_model=CameraResponse)
def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Update a camera's information. Requires authentication."""
    db_camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    for field, value in camera_update.dict(exclude_unset=True).items():
        setattr(db_camera, field, value)

    db.commit()
    db.refresh(db_camera)
    return db_camera


@router.delete("/{camera_id}")
async def delete_camera(
    camera_id: int,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Delete a camera and all associated streams, detections, alarms, and ROIs. Requires authentication."""
    from ...models.stream import Stream
    from ...services.gstreamer import gstreamer_service

    db_camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    # Stop and remove all associated streams from GStreamer before deleting
    streams = db.query(Stream).filter(Stream.camera_id == camera_id).all()
    for stream in streams:
        if stream.stream_name:
            try:
                await gstreamer_service.remove_stream(stream.stream_name)
            except Exception as e:
                # Log but don't fail if GStreamer cleanup fails
                print(f"Warning: Failed to remove stream {stream.stream_name} from GStreamer: {e}")

    # Delete camera (cascade will delete related streams, detections, alarms, ROIs)
    db.delete(db_camera)
    db.commit()
    return {"message": "Camera deleted successfully"}

    # Delete camera (cascade will delete related streams, detections, alarms, ROIs)
    db.delete(db_camera)
    db.commit()
    return {"message": "Camera deleted successfully"}

    # Delete camera (cascade will delete related streams, detections, alarms, ROIs)
    db.delete(db_camera)
    db.commit()
    return {"message": "Camera deleted successfully"}
