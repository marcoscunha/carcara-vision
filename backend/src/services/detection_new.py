"""
Deprecated compatibility module.

Use:
- src.services.camera_service.CameraService
- src.services.object_detection.ObjectDetectionService
"""

from .object_detection import ObjectDetectionService
from .object_detection import detect_objects

__all__ = ["ObjectDetectionService", "detect_objects"]
