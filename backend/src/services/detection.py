import hashlib
import os
import subprocess
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from ..core.config import settings


class CameraService:
    """Handles camera-related operations such as scanning and streaming."""

    @staticmethod
    def get_camera_name(device_id: int) -> str:
        """Retrieve the product name of the camera using v4l2-ctl."""
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--device", f"/dev/video{device_id}", "--all"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                if "Card type" in line:
                    return line.split(":")[1].strip()
        except Exception as e:
            print(f"Error retrieving name for camera {device_id}: {str(e)}")
        return f"Camera {device_id}"

    @staticmethod
    def _get_device_path_fallback(device_id: int) -> Optional[str]:
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
    def get_camera_physical_address(device_id: int) -> Optional[str]:
        """
        Retrieve the physical address of the camera using udevadm.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing the physical address of the camera, or None if unavailable.
        """
        try:
            result = subprocess.run(
                ["udevadm", "info", f"/dev/video{device_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                if "DEVPATH=" in line:
                    return line.split("=")[1].strip()
        except Exception as e:
            print(f"Error retrieving physical address for camera {device_id}: {str(e)}")
            return None

    @staticmethod
    def get_camera_usb_id(device_id: int) -> Optional[str]:
        """
        Retrieve the USB ID of the camera using udevadm.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing the USB ID of the camera (e.g., "1d6b:0002"), or None if unavailable.
        """
        try:
            result = subprocess.run(
                ["udevadm", "info", f"/dev/video{device_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
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
            print(f"Error retrieving USB ID for camera {device_id}: {str(e)}")
            return None

    @staticmethod
    def get_camera_friendly_name(device_id: int) -> Optional[str]:
        """
        Retrieve the friendly name of the camera using udevadm.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A string representing the friendly name of the camera, or None if unavailable.
        """
        try:
            result = subprocess.run(
                ["udevadm", "info", f"/dev/video{device_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                if "ID_MODEL_FROM_DATABASE" in line:
                    return line.split("=")[1].strip()
                elif "ID_MODEL" in line:  # Fallback to ID_MODEL if ID_MODEL_FROM_DATABASE is unavailable
                    return line.split("=")[1].strip()
        except Exception as e:
            print(f"Error retrieving friendly name for camera {device_id}: {str(e)}")
            return None

    @staticmethod
    def get_supported_resolutions(device_id: int) -> List[tuple]:
        """
        Retrieve the list of supported resolutions for a camera using v4l2-ctl.

        Args:
            device_id: The ID of the video device (e.g., 0 for /dev/video0).

        Returns:
            A list of tuples representing supported resolutions (width, height).
        """
        try:
            result = subprocess.run(
                ["v4l2-ctl", "--device", f"/dev/video{device_id}", "--list-formats-ext"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
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
            print(f"Error retrieving supported resolutions for camera {device_id}: {str(e)}")
            return []

    @staticmethod
    def scan_local_cameras(max_devices: int = 10) -> List[Dict[str, Any]]:
        """
        Scan for available local camera devices.

        Args:
            max_devices: Maximum number of devices to scan (default: 10)

        Returns:
            List of dictionaries containing device information.
        """
        available_cameras = []
        seen_devices = set()  # Track unique combinations of physical address and USB ID

        for device_id in range(max_devices):
            try:
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

                    camera_info = {
                        "device_id": device_id,
                        "physical_address": physical_address,
                        "usb_id": usb_id,
                        "name": CameraService.get_camera_name(device_id),
                        "friendly_name": CameraService.get_camera_friendly_name(device_id),  # Add friendly name
                        "resolution": (width, height),
                        "fps": fps,
                        "is_available": is_available,
                        "supported_resolutions": supported_resolutions
                    }

                    # Add camera to the list and mark its unique key as seen
                    available_cameras.append(camera_info)
                    seen_devices.add(unique_device_key)
                cap.release()
            except Exception as e:
                print(f"Error accessing camera {device_id}: {str(e)}")
                continue

        return available_cameras

    @staticmethod
    def process_stream(stream_url: str, camera_type: str = "rtsp", device_id: Optional[int] = None) -> Optional[np.ndarray]:
        """
        Process a video stream and return the current frame.

        Args:
            stream_url: URL of the video stream (for RTSP cameras)
            camera_type: Type of camera ("rtsp" or "local")
            device_id: Device ID for local cameras

        Returns:
            Current frame as numpy array or None if stream is not available.
        """
        if camera_type == "local":
            if device_id is None:
                return None
            cap = cv2.VideoCapture(device_id)
        else:
            cap = cv2.VideoCapture(stream_url)

        if not cap.isOpened():
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        return frame


class ObjectDetectionService:
    """Handles object detection operations."""

    def __init__(self, detection_model_name: str = settings.DEFAULT_MODEL):
        self.detection_model_name = detection_model_name
        self.device = self._get_device()
        self.model = self._load_model()
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD

    def _get_device(self) -> str:
        """Detect if CUDA is available and return appropriate device."""
        try:
            # Check if nvidia-smi is available
            subprocess.run(['nvidia-smi'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            # Check if CUDA is available in PyTorch
            if torch.cuda.is_available():
                return "cuda"
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return "cpu"

    def _load_model(self) -> YOLO:
        """Load the YOLO model with appropriate device settings."""
        print(f"Loading model on {self.device} device...")
        return YOLO(self.detection_model_name).to(self.device)

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Perform object detection on a single frame.

        Args:
            frame: numpy array containing the image

        Returns:
            List of detections with bounding boxes and class information.
        """
        results = self.model(frame, conf=self.confidence_threshold)[0]
        detections = []

        for box in results.boxes:
            detection = {
                "bbox": box.xyxy[0].tolist(),
                "confidence": float(box.conf[0]),
                "class_name": results.names[int(box.cls[0])],
                "class_id": int(box.cls[0])
            }
            detections.append(detection)

        return detections

    def get_available_models(self) -> List[str]:
        """Return list of available YOLO models."""
        return settings.SUPPORTED_MODELS
