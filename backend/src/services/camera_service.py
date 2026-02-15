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


class CameraService:
    """Handles camera-related operations such as scanning and streaming."""

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
            # If v4l2-ctl is not available, assume capture is possible
            # and let downstream operations fail if the device is not valid
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
        except Exception:
            pass
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
        if not shutil.which("udevadm"):
            return CameraService._get_device_path_fallback(device_id)
        try:
            result = subprocess.run(
                ["udevadm", "info", f"/dev/video{device_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if "DEVPATH=" in line:
                    return line.split("=")[1].strip()
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
        if not shutil.which("udevadm"):
            return None
        try:
            result = subprocess.run(
                ["udevadm", "info", f"/dev/video{device_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            vendor_id = None
            model_id = None
            for line in result.stdout.splitlines():
                if "ID_VENDOR_ID" in line:
                    vendor_id = line.split("=")[1].strip()
                if "ID_MODEL_ID" in line:
                    model_id = line.split("=")[1].strip()
            if vendor_id and model_id:
                return f"{vendor_id}:{model_id}"
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
            result = subprocess.run(
                ["udevadm", "info", f"/dev/video{device_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            for line in result.stdout.splitlines():
                if "ID_MODEL_FROM_DATABASE" in line or "ID_MODEL" in line:
                    return line.split("=")[1].strip()
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
        seen_devices = set()  # Track unique combinations of physical address and USB ID

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
                    # Get physical address
                    physical_address = CameraService.get_camera_physical_address(device_id)
                    # Get USB ID
                    usb_id = CameraService.get_camera_usb_id(device_id)

                    # Use a combination of physical address and USB ID to ensure uniqueness
                    # If physical_address is unavailable (e.g., udevadm not installed), use device_id as fallback
                    if physical_address:
                        unique_device_key = (physical_address, usb_id)
                    else:
                        # Fallback: use device path from /sys/class/video4linux if available
                        unique_device_key = CameraService._get_device_path_fallback(device_id) or f"device_{device_id}"

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

                    # Obtain a persistent device path (survives reboots)
                    persistent_path = CameraService.get_persistent_device_path(device_id)

                    camera_info = {
                        "device_id": device_id,
                        "device_path": persistent_path or f"/dev/video{device_id}",
                        "physical_address": physical_address,
                        "usb_id": usb_id,
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
