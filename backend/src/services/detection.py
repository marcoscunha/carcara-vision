"""
Compatibility module for legacy imports.

New split modules:
- camera service: src.services.camera_service
- object detection service: src.services.object_detection
"""

from .camera_service import CameraService
from .object_detection import ObjectDetectionService
from .object_detection import detect_objects

__all__ = ["CameraService", "ObjectDetectionService", "detect_objects"]
