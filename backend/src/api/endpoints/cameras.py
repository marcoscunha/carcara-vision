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
LOCAL_CAMERA_TYPES = {"local", "usb"}
LOCAL_CAMERA_IDENTITY_FIELDS = (
    "device_id",
    "device_path",
    "physical_address",
    "usb_vendor_id",
    "usb_product_id",
    "usb_serial_number",
)


def _local_camera_payload_from_resolution(
    resolved: dict | None,
    *,
    fallback: dict,
) -> dict:
    payload = {field: fallback.get(field) for field in LOCAL_CAMERA_IDENTITY_FIELDS}
    if resolved is None:
        return payload

    for field in LOCAL_CAMERA_IDENTITY_FIELDS:
        payload[field] = resolved.get(field)
    return payload


def _resolve_local_camera_payload(camera_data: dict, existing_camera: Camera | None = None) -> dict:
    merged_identity = {
        field: camera_data.get(field, getattr(existing_camera, field, None)) for field in LOCAL_CAMERA_IDENTITY_FIELDS
    }
    resolved = CameraService.resolve_local_camera(**merged_identity)
    return _local_camera_payload_from_resolution(resolved, fallback=merged_identity)


@router.post("/", response_model=CameraResponse)
def create_camera(
    camera: CameraCreate,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Create a new camera. Requires authentication."""
    camera_data = camera.model_dump()
    if camera.camera_type in LOCAL_CAMERA_TYPES:
        camera_data.update(_resolve_local_camera_payload(camera_data))
    else:
        for field in LOCAL_CAMERA_IDENTITY_FIELDS:
            camera_data[field] = None

    db_camera = Camera(**camera_data)
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
    usb_vendor_id: str | None
    usb_product_id: str | None
    usb_serial_number: str | None
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
async def update_camera(
    camera_id: int,
    camera_update: CameraUpdate,
    current_user: AuthenticatedUser,
    db: Session = Depends(get_db),
):
    """Update a camera's information. Requires authentication."""
    from ...models.stream import Stream
    from ...services.gstreamer import gstreamer_service
    from ...services.inference_worker_manager import inference_worker_manager
    from .streams import recover_streams_for_camera

    db_camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if db_camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = camera_update.model_dump(exclude_unset=True)
    target_camera_type = update_data.get("camera_type", db_camera.camera_type)

    if target_camera_type in LOCAL_CAMERA_TYPES:
        update_data.update(_resolve_local_camera_payload(update_data, existing_camera=db_camera))
    elif "camera_type" in update_data:
        for field in LOCAL_CAMERA_IDENTITY_FIELDS:
            update_data[field] = None

    was_active = bool(db_camera.is_active)

    for field, value in update_data.items():
        setattr(db_camera, field, value)

    # When the camera transitions to inactive, tear down all associated streams
    # so GStreamer stops consuming the source and inference workers stop.
    deactivating = was_active and update_data.get("is_active") is False
    activating = not was_active and update_data.get("is_active") is True

    if deactivating:
        streams = db.query(Stream).filter(Stream.camera_id == camera_id).all()
        for stream in streams:
            if stream.stream_name:
                try:
                    await gstreamer_service.remove_stream(stream.stream_name)
                except Exception as e:
                    print(f"Warning: Failed to remove stream {stream.stream_name} from GStreamer: {e}")
            inference_worker_manager.stop_worker(stream.id)
            stream.status = "offline"

    db.commit()
    db.refresh(db_camera)

    # When the camera transitions to active, bring its streams back online by
    # re-registering pipelines and inference workers.
    if activating:
        try:
            await recover_streams_for_camera(db, camera_id)
            db.refresh(db_camera)
        except Exception as e:
            print(f"Warning: Failed to recover streams for camera {camera_id}: {e}")

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
