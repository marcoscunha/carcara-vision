"""
Camera service utilities for local and RTSP cameras.
"""

import glob
import logging
import os
import shutil
import subprocess
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


LOCAL_CAMERA_SCAN_LIMIT = 256


class CameraService:
    """Handles camera-related operations such as scanning and streaming."""

    @staticmethod
    def _read_udev_properties(device_node: str) -> dict[str, str]:
        """Read udev properties for a device node, returning an empty dict on failure."""
        if not shutil.which("udevadm"):
            return {}

        try:
            result = subprocess.run(
                ["udevadm", "info", "--query=property", "--name", device_node],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except Exception as exc:
            logger.warning("Error retrieving udev properties for %s: %s", device_node, exc)
            return {}

        properties: dict[str, str] = {}
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
        return properties

    @staticmethod
    def _get_sysfs_device_dir(device_node: str) -> str | None:
        """Return the resolved sysfs directory for a V4L2 device node."""
        video_name = os.path.basename(os.path.realpath(device_node))
        sysfs_path = os.path.join("/sys/class/video4linux", video_name, "device")
        if not os.path.exists(sysfs_path):
            return None
        return os.path.realpath(sysfs_path)

    @staticmethod
    def _read_sysfs_attribute(start_dir: str | None, attr_name: str) -> str | None:
        """Walk parent sysfs directories until the requested USB attribute is found."""
        current = start_dir
        while current and current != "/":
            candidate = os.path.join(current, attr_name)
            if os.path.isfile(candidate):
                try:
                    with open(candidate) as file_handle:
                        value = file_handle.read().strip().rstrip("\x00")
                    return value or None
                except OSError:
                    return None

            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return None

    @staticmethod
    def describe_local_device(device_id: int | None = None, *, device_path: str | None = None) -> dict[str, Any]:
        """
        Return stable identity data for a local V4L2 device.

        The returned dictionary is designed to be persisted and later used to
        rebind a logical camera to the current ``/dev/videoX`` node after a
        reboot or device re-enumeration.
        """
        dev = CameraService._dev_path_or_index(device_path, device_id)
        real_dev = CameraService.resolve_device_path(dev)
        resolved_device_id = CameraService.resolve_device_index(real_dev)
        udev = CameraService._read_udev_properties(real_dev)
        sysfs_dir = CameraService._get_sysfs_device_dir(real_dev)

        usb_vendor_id = udev.get("ID_VENDOR_ID") or CameraService._read_sysfs_attribute(sysfs_dir, "idVendor")
        usb_product_id = udev.get("ID_MODEL_ID") or CameraService._read_sysfs_attribute(sysfs_dir, "idProduct")
        usb_serial_number = udev.get("ID_SERIAL_SHORT") or CameraService._read_sysfs_attribute(sysfs_dir, "serial")
        physical_address = (
            udev.get("ID_PATH")
            or udev.get("DEVPATH")
            or (CameraService._get_device_path_fallback(resolved_device_id) if resolved_device_id is not None else None)
        )

        persistent_path = None
        if resolved_device_id is not None:
            persistent_path = CameraService.get_persistent_device_path(resolved_device_id)

        return {
            "device_id": resolved_device_id,
            "device_path": persistent_path or real_dev,
            "physical_address": physical_address,
            "usb_vendor_id": usb_vendor_id,
            "usb_product_id": usb_product_id,
            "usb_serial_number": usb_serial_number,
            "usb_id": f"{usb_vendor_id}:{usb_product_id}" if usb_vendor_id and usb_product_id else None,
        }

    @staticmethod
    def _camera_identity_score(
        candidate: dict[str, Any],
        *,
        device_id: int | None = None,
        device_path: str | None = None,
        physical_address: str | None = None,
        usb_vendor_id: str | None = None,
        usb_product_id: str | None = None,
        usb_serial_number: str | None = None,
    ) -> int | None:
        """Score how well a scanned camera matches a stored identity."""
        score = 0

        candidate_path = candidate.get("device_path")
        candidate_vendor = candidate.get("usb_vendor_id")
        candidate_product = candidate.get("usb_product_id")
        candidate_serial = candidate.get("usb_serial_number")
        candidate_physical = candidate.get("physical_address")

        if device_id is not None and candidate.get("device_id") == device_id:
            score += 10

        if usb_serial_number:
            if candidate_serial != usb_serial_number:
                return None
            score += 100

        if physical_address:
            if candidate_physical == physical_address:
                score += 60
            elif not usb_serial_number:
                return None

        if usb_vendor_id:
            if candidate_vendor != usb_vendor_id:
                return None
            score += 20

        if usb_product_id:
            if candidate_product != usb_product_id:
                return None
            score += 20

        if device_path and candidate_path:
            if candidate_path == device_path:
                score += 40
            elif os.path.basename(candidate_path) == os.path.basename(device_path):
                score += 20

        return score

    @staticmethod
    def resolve_local_camera(
        device_id: int | None = None,
        *,
        device_path: str | None = None,
        physical_address: str | None = None,
        usb_vendor_id: str | None = None,
        usb_product_id: str | None = None,
        usb_serial_number: str | None = None,
        max_devices: int = LOCAL_CAMERA_SCAN_LIMIT,
    ) -> dict[str, Any] | None:
        """
        Resolve a logical local camera to the current live device node.

        Matching prefers USB serial number when available, then falls back to
        physical address, persistent path, and finally vendor/product pairs.
        Ambiguous weak matches intentionally return ``None``.
        """
        direct_candidate = None
        if device_path or device_id is not None:
            try:
                direct_candidate = CameraService.describe_local_device(device_id=device_id, device_path=device_path)
            except Exception:
                direct_candidate = None

        has_stable_identity = any((device_path, physical_address, usb_vendor_id, usb_product_id, usb_serial_number))
        if direct_candidate and not has_stable_identity:
            return direct_candidate

        candidates = CameraService.scan_local_camera_identities(max_devices=max_devices)
        scored_candidates: list[tuple[int, dict[str, Any]]] = []

        for candidate in candidates:
            score = CameraService._camera_identity_score(
                candidate,
                device_id=device_id,
                device_path=device_path,
                physical_address=physical_address,
                usb_vendor_id=usb_vendor_id,
                usb_product_id=usb_product_id,
                usb_serial_number=usb_serial_number,
            )
            if score is not None and score > 0:
                scored_candidates.append((score, candidate))

        if direct_candidate:
            score = CameraService._camera_identity_score(
                direct_candidate,
                device_id=device_id,
                device_path=device_path,
                physical_address=physical_address,
                usb_vendor_id=usb_vendor_id,
                usb_product_id=usb_product_id,
                usb_serial_number=usb_serial_number,
            )
            if score is not None and score > 0:
                scored_candidates.append((score + 1, direct_candidate))

        if not scored_candidates:
            if direct_candidate and not has_stable_identity:
                return direct_candidate

            # Recovery heuristic for cameras created without stable USB identity:
            # if there is only one active local camera, rebind to it.
            if len(candidates) == 1:
                return candidates[0]

            # Prefer exact index match when available.
            if device_id is not None:
                exact_index = [c for c in candidates if c.get("device_id") == device_id]
                if len(exact_index) == 1:
                    return exact_index[0]
            return None

        scored_candidates.sort(key=lambda item: item[0], reverse=True)
        best_score = scored_candidates[0][0]
        best_matches = [candidate for score, candidate in scored_candidates if score == best_score]
        if len(best_matches) > 1:
            return None

        best_match = best_matches[0]
        if best_score < 40 and usb_serial_number is None and physical_address is None:
            return None
        return best_match

    @staticmethod
    def scan_local_camera_identities(max_devices: int = 10) -> list[dict[str, Any]]:
        """
        Scan local camera identities without opening video streams.

        This method is intended for camera rebinding/reconnect logic where we
        only need stable identity fields, not frame capture validation.
        """
        candidates: list[dict[str, Any]] = []
        seen_devices: set[tuple[Any, ...]] = set()

        existing_video_devices = sorted(
            int(p.replace("/dev/video", "")) for p in glob.glob("/dev/video*") if p.replace("/dev/video", "").isdigit()
        )
        device_ids = [d for d in existing_video_devices if d < max_devices]

        for device_id in device_ids:
            try:
                if not CameraService.is_capture_device(device_id=device_id):
                    continue

                identity = CameraService.describe_local_device(device_id=device_id)
                unique_key = (
                    identity.get("usb_vendor_id"),
                    identity.get("usb_product_id"),
                    identity.get("usb_serial_number")
                    or identity.get("physical_address")
                    or identity.get("device_path")
                    or f"device_{device_id}",
                )
                if unique_key in seen_devices:
                    continue

                candidates.append(
                    {
                        "device_id": identity.get("device_id"),
                        "device_path": identity.get("device_path") or f"/dev/video{device_id}",
                        "physical_address": identity.get("physical_address"),
                        "usb_vendor_id": identity.get("usb_vendor_id"),
                        "usb_product_id": identity.get("usb_product_id"),
                        "usb_serial_number": identity.get("usb_serial_number"),
                        "usb_id": identity.get("usb_id"),
                    }
                )
                seen_devices.add(unique_key)
            except Exception as e:
                logger.warning("Error reading camera identity for /dev/video%d: %s", device_id, e)

        return candidates

    # ------------------------------------------------------------------ #
    #  Persistent device path helpers                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_persistent_device_path(device_id: int) -> str | None:
        """
        Find a persistent symlink for /dev/videoN that survives reboots.

        Looks in /dev/v4l/by-id/ first (stable across USB ports) then falls
        back to /dev/v4l/by-path/ (stable per physical port).

        Args:
            device_id: The current V4L2 index (e.g. 0 for /dev/video0).

        Returns:
            Absolute path of a persistent symlink, or None.
        """
        real_dev = os.path.realpath(f"/dev/video{device_id}")

        # Prefer by-id (unique per physical device)
        for search_dir in ("/dev/v4l/by-id", "/dev/v4l/by-path"):
            if not os.path.isdir(search_dir):
                continue
            for entry in sorted(os.listdir(search_dir)):
                full = os.path.join(search_dir, entry)
                if os.path.realpath(full) == real_dev:
                    return full
        return None

    @staticmethod
    def resolve_device_path(device_path: str) -> str:
        """
        Resolve a persistent symlink to the real /dev/videoN path.

        If *device_path* is already a ``/dev/videoN`` path it is returned
        unchanged.  If it is a symlink (e.g. ``/dev/v4l/by-id/…``) it is
        resolved via ``os.path.realpath``.

        Args:
            device_path: Persistent or direct device path.

        Returns:
            The real ``/dev/videoN`` device node path.
        """
        return os.path.realpath(device_path)

    @staticmethod
    def resolve_device_index(device_path: str) -> int | None:
        """
        Resolve a device path (persistent or direct) to a V4L2 integer index.

        Args:
            device_path: e.g. ``/dev/v4l/by-id/usb-…-video-index0`` or ``/dev/video2``.

        Returns:
            Integer index (e.g. 2) or None if the path cannot be resolved.
        """
        real = os.path.realpath(device_path)
        base = os.path.basename(real)  # e.g. "video2"
        if base.startswith("video") and base[5:].isdigit():
            return int(base[5:])
        return None

    @staticmethod
    def device_path_for_opencv(device_path: str) -> int | str:
        """
        Return the best argument to pass to ``cv2.VideoCapture()``.

        Prefers the integer index when resolvable, because some OpenCV
        builds don't support string device paths on all platforms.
        Falls back to the resolved real path.
        """
        idx = CameraService.resolve_device_index(device_path)
        if idx is not None:
            return idx
        return CameraService.resolve_device_path(device_path)

    # ------------------------------------------------------------------ #
    #  V4L2 capability helpers                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def is_capture_device(device_id: int | None = None, *, device_path: str | None = None) -> bool:
        """
        Check if a V4L2 device has VIDEO_CAPTURE capability.

        Metadata devices (like those created by UVC webcams for metadata
        streaming) do not have VIDEO_CAPTURE capability and should be
        excluded from camera scanning.

        Args:
            device_id: The V4L2 device index (e.g., 0 for /dev/video0).
            device_path: Persistent or direct device path (preferred).

        Returns:
            True if the device supports VIDEO_CAPTURE, False otherwise.
        """
        if device_path:
            dev = os.path.realpath(device_path)
        elif device_id is not None:
            dev = f"/dev/video{device_id}"
        else:
            return False

        if not shutil.which("v4l2-ctl"):
            # Fallback without v4l2-ctl: try sysfs capabilities bitmask.
            try:
                video_name = os.path.basename(os.path.realpath(dev))
                caps_file = os.path.join("/sys/class/video4linux", video_name, "device", "capabilities")
                if os.path.isfile(caps_file):
                    with open(caps_file) as fh:
                        raw = fh.read().strip()
                    caps_value = int(raw, 16)
                    # V4L2_CAP_VIDEO_CAPTURE = 0x00000001
                    return bool(caps_value & 0x00000001)
            except Exception as exc:
                logger.debug("Could not read sysfs capabilities for %s: %s", dev, exc)

            # Without v4l2-ctl and without readable sysfs caps, assume capture is
            # possible and let OpenCV / downstream fail if the node is invalid.
            # This restores the original permissive behaviour; deduplication in
            # scan_local_cameras handles multi-node cameras.
            return True

        try:
            result = subprocess.run(
                ["v4l2-ctl", "--device", dev, "-D"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False

            # Look for "Video Capture" in Device Caps section
            # Device Caps indicate what THIS specific device node supports
            in_device_caps = False
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith("Device Caps"):
                    in_device_caps = True
                    continue
                if in_device_caps:
                    if stripped.startswith("0x") or not stripped:
                        # Still in Device Caps header
                        continue
                    if not line.startswith("\t\t"):
                        # Exited Device Caps section
                        break
                    if "Video Capture" in stripped:
                        return True
            return False
        except Exception as e:
            logger.warning("Error checking capture capability for %s: %s", dev, e)
            return False

    # ------------------------------------------------------------------ #
    #  Device metadata helpers (accept device_path OR device_id)          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _dev_path_or_index(device_path: str | None = None, device_id: int | None = None) -> str:
        """Internal: return a ``/dev/videoN`` path from either argument."""
        if device_path:
            return CameraService.resolve_device_path(device_path)
        if device_id is not None:
            return f"/dev/video{device_id}"
        raise ValueError("Either device_path or device_id must be provided")

    @staticmethod
    def get_camera_name(device_id: int | None = None, *, device_path: str | None = None) -> str:
        """Retrieve the product name of the camera using v4l2-ctl."""
        dev = CameraService._dev_path_or_index(device_path, device_id)
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--device", dev, "--all"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if "Card type" in line:
                    return line.split(":")[1].strip()
        except Exception as e:
            logger.warning("Error retrieving name for camera %s: %s", dev, e)
        return f"Camera {os.path.basename(dev)}"

    @staticmethod
    def _get_device_path_fallback(device_id: int) -> str | None:
        """
        Get a unique device identifier from /sys/class/video4linux as fallback.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing a unique path for the device, or None if unavailable.
        """
        try:
            device_path = f"/sys/class/video4linux/video{device_id}/device"
            if os.path.exists(device_path):
                return os.path.realpath(device_path)
        except Exception as exc:
            logger.debug("Error resolving sysfs fallback path for camera %d: %s", device_id, exc)
        return None

    @staticmethod
    def get_camera_physical_address(device_id: int) -> str | None:
        """
        Retrieve the physical address of the camera using udevadm.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing the physical address of the camera, or None if unavailable.
        """
        try:
            return CameraService.describe_local_device(device_id=device_id).get("physical_address")
        except Exception as e:
            logger.warning("Error retrieving physical address for camera %d: %s", device_id, e)
            return CameraService._get_device_path_fallback(device_id)

    @staticmethod
    def get_camera_usb_id(device_id: int) -> str | None:
        """
        Retrieve the USB ID of the camera using udevadm.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing the USB ID of the camera (e.g., "1d6b:0002"), or None if unavailable.
        """
        try:
            return CameraService.describe_local_device(device_id=device_id).get("usb_id")
        except Exception as e:
            logger.warning("Error retrieving USB ID for camera %d: %s", device_id, e)
            return None

    @staticmethod
    def get_camera_friendly_name(device_id: int) -> str | None:
        """
        Retrieve the friendly name of the camera using udevadm.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing the friendly name of the camera, or None if unavailable.
        """
        if not shutil.which("udevadm"):
            return None
        try:
            props = CameraService._read_udev_properties(f"/dev/video{device_id}")
            return props.get("ID_MODEL_FROM_DATABASE") or props.get("ID_V4L_PRODUCT") or props.get("ID_MODEL")
        except Exception as e:
            logger.warning("Error retrieving friendly name for camera %d: %s", device_id, e)
            return None

    @staticmethod
    def get_supported_resolutions(device_id: int | None = None, *, device_path: str | None = None) -> list[tuple]:
        """
        Retrieve the list of supported resolutions for a camera using v4l2-ctl.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).
            device_path: Persistent or direct device path (preferred).

        Returns:
            A list of tuples representing supported resolutions (width, height).
        """
        dev = CameraService._dev_path_or_index(device_path, device_id)
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--device", dev, "--list-formats-ext"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            resolutions = []
            for line in result.stdout.splitlines():
                if "Size:" in line:
                    # Extract resolution from the line (e.g., "Size: Discrete 1920x1080")
                    parts = line.split()
                    if len(parts) >= 3:
                        width, height = map(int, parts[2].split("x"))
                        resolutions.append((width, height))
            return resolutions
        except Exception as e:
            logger.warning("Error retrieving supported resolutions for camera %s: %s", dev, e)
            return []

    # ------------------------------------------------------------------ #
    #  Scan                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def scan_local_cameras(max_devices: int = 10) -> list[dict[str, Any]]:
        """
        Scan for available local camera devices.

        Each discovered camera includes a ``device_path`` field containing a
        persistent symlink (from ``/dev/v4l/by-id/`` or ``/dev/v4l/by-path/``)
        that remains stable across reboots and V4L2 index changes.  The
        ``device_id`` field still contains the *current* integer index for
        informational purposes, but ``device_path`` should be used for all
        persistent storage and streaming operations.

        Args:
            max_devices: Maximum number of devices to scan (default: 10)

        Returns:
            List of dictionaries containing device information.
        """
        available_cameras = []
        seen_devices = set()

        # Only probe /dev/video* devices that actually exist instead of
        # blindly iterating indices, which causes OpenCV errors for
        # non-existent devices.
        existing_video_devices = sorted(
            int(p.replace("/dev/video", "")) for p in glob.glob("/dev/video*") if p.replace("/dev/video", "").isdigit()
        )
        device_ids = [d for d in existing_video_devices if d < max_devices]

        for device_id in device_ids:
            try:
                # First check if this is a VIDEO_CAPTURE device (not metadata-only)
                if not CameraService.is_capture_device(device_id=device_id):
                    logger.debug("Skipping /dev/video%d: not a capture device", device_id)
                    continue

                cap = cv2.VideoCapture(device_id)
                if cap.isOpened():
                    device_identity = CameraService.describe_local_device(device_id=device_id)

                    # Build a deduplication key that is stable across all video nodes
                    # belonging to the same physical USB device.
                    #
                    # Priority:
                    #  1. vendor+product+serial  → uniquely identifies an individual unit
                    #  2. vendor+product+sysfs_parent_path  → same parent dir for all nodes
                    #     of the same physical device (index0, index1, …)
                    #  3. sysfs_parent_path alone  → no USB identity info available
                    #  4. device_id string  → absolute last resort
                    #
                    # Crucially we do NOT use device_path (the persistent by-id symlink) as a
                    # fallback: those paths include a "-video-index0" / "-video-index1" suffix
                    # which differs per node, breaking deduplication for multi-node cameras.
                    sysfs_parent = CameraService._get_device_path_fallback(device_id)
                    usb_serial = device_identity.get("usb_serial_number")
                    usb_vendor = device_identity.get("usb_vendor_id")
                    usb_product = device_identity.get("usb_product_id")

                    if usb_serial:
                        unique_device_key = (usb_vendor, usb_product, usb_serial)
                    elif usb_vendor or usb_product:
                        unique_device_key = (usb_vendor, usb_product, sysfs_parent or f"device_{device_id}")
                    else:
                        unique_device_key = sysfs_parent or f"device_{device_id}"

                    if unique_device_key in seen_devices:
                        cap.release()
                        continue

                    # Get camera properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)

                    # Try to get a frame to confirm camera is working
                    ret, frame = cap.read()
                    is_available = ret and frame is not None

                    # Use the method to get supported resolutions
                    supported_resolutions = CameraService.get_supported_resolutions(device_id)

                    camera_info = {
                        "device_id": device_id,
                        "device_path": device_identity.get("device_path") or f"/dev/video{device_id}",
                        "physical_address": device_identity.get("physical_address"),
                        "usb_vendor_id": device_identity.get("usb_vendor_id"),
                        "usb_product_id": device_identity.get("usb_product_id"),
                        "usb_serial_number": device_identity.get("usb_serial_number"),
                        "usb_id": device_identity.get("usb_id"),
                        "name": CameraService.get_camera_name(device_id),
                        "friendly_name": CameraService.get_camera_friendly_name(device_id),
                        "resolution": (width, height),
                        "fps": fps,
                        "is_available": is_available,
                        "supported_resolutions": supported_resolutions,
                    }

                    # Add camera to the list and mark its unique key as seen
                    available_cameras.append(camera_info)
                    seen_devices.add(unique_device_key)
                cap.release()
            except Exception as e:
                logger.warning("Error accessing camera %d: %s", device_id, e)
                continue

        return available_cameras

    @staticmethod
    def process_stream(
        stream_url: str,
        camera_type: str = "rtsp",
        device_id: int | None = None,
        device_path: str | None = None,
    ) -> np.ndarray | None:
        """
        Process a video stream and return the current frame.

        Args:
            stream_url: URL of the video stream (for RTSP cameras)
            camera_type: Type of camera ("rtsp" or "local")
            device_id: Device ID for local cameras (legacy, prefer device_path)
            device_path: Persistent device path for local cameras (preferred)

        Returns:
            Current frame as numpy array or None if stream is not available.
        """
        if camera_type == "local":
            if device_path:
                cap_arg = CameraService.device_path_for_opencv(device_path)
                cap = cv2.VideoCapture(cap_arg)
            elif device_id is not None:
                cap = cv2.VideoCapture(device_id)
            else:
                return None
        else:
            cap = cv2.VideoCapture(stream_url)

        if not cap.isOpened():
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        return frame
