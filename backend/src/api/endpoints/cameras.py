from typing import List
from typing import Optional
from typing import Tuple

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...api.models.camera import CameraCreate
from ...api.models.camera import CameraResponse
from ...api.models.camera import CameraUpdate
from ...db.session import get_db
from ...models.camera import Camera
from ...services.detection import CameraService
from ...services.detection import ObjectDetectionService

router = APIRouter()
detection_service = ObjectDetectionService()


@router.post("/", response_model=CameraResponse)
def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_db)
):
    """Create a new IP camera."""
    db_camera = Camera(
        name=camera.name,
        camera_type=camera.camera_type,
        device_id=camera.device_id,
        rtsp_url=camera.rtsp_url,
        is_active=camera.is_active
    )
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera


@router.get("/", response_model=List[CameraResponse])
def list_cameras(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all cameras."""
    cameras = db.query(Camera).offset(skip).limit(limit).all()
    return cameras


class CameraInfo(BaseModel):
    device_id: int
    physical_address: Optional[str]
    usb_id: Optional[str]
    name: str
    friendly_name: Optional[str]
    resolution: List[int]
    fps: float
    is_available: bool
    supported_resolutions: List[Tuple[int, int]]


@router.get("/scan", response_model=List[CameraInfo])
async def scan_local_cameras(
    max_devices: int = 10,
    camera_service: CameraService = Depends(
        lambda: CameraService()
    )
) -> List[CameraInfo]:
    """
    Scan for available local camera devices.

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
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scan for cameras: {str(e)}"
        )


@router.get("/{camera_id}", response_model=CameraResponse)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific camera by ID."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.get("/{camera_id}/status", response_model=dict)
def get_camera_status(
    camera_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the status of a specific camera by ID.

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
    db: Session = Depends(get_db)
):
    """Update a camera's information."""
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
    db: Session = Depends(get_db)
):
    """Delete a camera and all associated streams, detections, alarms, and ROIs."""
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
