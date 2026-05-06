"""Helpers to synchronize local camera connectivity with persisted camera/stream state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from ..models.camera import Camera
from ..models.stream import Stream
from .camera_service import CameraService
from .inference_worker_manager import inference_worker_manager

LOCAL_CAMERA_TYPES = ("local", "usb")
LOCAL_CAMERA_IDENTITY_FIELDS = (
    "device_id",
    "device_path",
    "physical_address",
    "usb_vendor_id",
    "usb_product_id",
    "usb_serial_number",
)


def sync_local_camera_connectivity(db: Session, camera_ids: set[int] | None = None) -> bool:
    """
    Refresh persisted availability state for local/USB cameras.

    When a camera is detached, mark the camera inactive and move all related
    streams from active/starting to offline.
    """
    query = db.query(Camera).filter(Camera.camera_type.in_(LOCAL_CAMERA_TYPES))
    if camera_ids:
        query = query.filter(Camera.id.in_(camera_ids))

    cameras = query.all()
    if not cameras:
        return False

    changed = False

    for camera in cameras:
        identity = {field: getattr(camera, field, None) for field in LOCAL_CAMERA_IDENTITY_FIELDS}
        resolved = CameraService.resolve_local_camera(**identity)

        if resolved is not None:
            if camera.is_active is not True:
                camera.is_active = True
                changed = True

            for field in LOCAL_CAMERA_IDENTITY_FIELDS:
                new_value = resolved.get(field)
                if getattr(camera, field, None) != new_value:
                    setattr(camera, field, new_value)
                    changed = True
            continue

        if camera.is_active is not False:
            camera.is_active = False
            changed = True

        impacted_streams = (
            db.query(Stream).filter(Stream.camera_id == camera.id, Stream.status.in_(("active", "starting"))).all()
        )

        for stream in impacted_streams:
            if stream.status != "offline":
                stream.status = "offline"
                changed = True
            inference_worker_manager.stop_worker(stream.id)

    if changed:
        db.commit()

    return changed
