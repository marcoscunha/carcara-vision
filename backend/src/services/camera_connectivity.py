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
    Refresh persisted USB identity for local/USB cameras and stop streams that
    point at detached devices. Never modifies `Camera.is_active` — that flag
    reflects user intent and is owned exclusively by the cameras endpoints.
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
            # Hardware is present: refresh persisted identity fields, but do NOT
            # auto-reactivate. `is_active` reflects user intent (manual toggle in
            # the UI) and must only be changed by an explicit user action.
            for field in LOCAL_CAMERA_IDENTITY_FIELDS:
                new_value = resolved.get(field)
                if getattr(camera, field, None) != new_value:
                    setattr(camera, field, new_value)
                    changed = True
            continue

        # Hardware is missing: stop running streams so we don't keep trying to
        # consume a detached device. We still leave `is_active` untouched so
        # the user's intent is preserved across reconnects.
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
