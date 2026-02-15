"""
Object Detection Service using the ML infrastructure.

This service provides a unified interface for object detection and
VLM-based image analysis, with automatic hardware acceleration selection.
"""

import logging
from typing import Any

import numpy as np

from ..core.config import settings
from ..ml import InferenceEngineFactory
from ..ml.accelerators.detector import HardwareDetector
from ..ml.base import HardwareAccelerator
from ..ml.engines.yolo import YOLOEngine

logger = logging.getLogger(__name__)


class ObjectDetectionService:
    """
    Unified object detection service with multi-model and multi-hardware support.

    Features:
    - YOLO object detection (v5, v8, v11)
    - VLM-based image analysis
    - Automatic hardware acceleration
    - Model hot-swapping
    - ROI-based detection
    - Inference performance tracking
    """

    def __init__(
        self,
        model_name: str | None = None,
        model_type: str = "yolo",
        accelerator: HardwareAccelerator | None = None,
    ):
        """
        Initialize the detection service.

        Args:
            model_name: Model to use (default from settings)
            model_type: "yolo" or "vlm"
            accelerator: Preferred hardware accelerator
        """
        self.model_name = model_name or settings.DEFAULT_MODEL
        self.model_type = model_type
        self.confidence_threshold = settings.CONFIDENCE_THRESHOLD

        # Detect best accelerator if not specified
        if accelerator is None:
            self._accelerator = self._detect_accelerator()
        else:
            self._accelerator = accelerator

        # Initialize engine
        self._engine: YOLOEngine | None = None
        self._initialize_engine()

        # Statistics
        self._inference_count = 0
        self._total_inference_time = 0.0
        self._min_inference_time = float("inf")
        self._max_inference_time = 0.0

    def _detect_accelerator(self) -> HardwareAccelerator:
        """Detect the best available hardware accelerator."""
        try:
            available = HardwareDetector.detect_all()

            # Priority order based on settings
            if settings.USE_GPU and available.get(HardwareAccelerator.CUDA):
                return HardwareAccelerator.CUDA

            if available.get(HardwareAccelerator.TENSORRT):
                return HardwareAccelerator.TENSORRT

            if available.get(HardwareAccelerator.JETSON):
                return HardwareAccelerator.JETSON

            if available.get(HardwareAccelerator.CORAL_TPU):
                return HardwareAccelerator.CORAL_TPU
        except Exception as e:
            logger.warning(f"Failed to detect hardware: {e}")

        return HardwareAccelerator.CPU

    def _initialize_engine(self) -> None:
        """Initialize the inference engine."""
        logger.info(f"Initializing {self.model_type} engine with {self.model_name}")
        logger.info(f"Target accelerator: {self._accelerator}")

        try:
            if self.model_type == "yolo":
                self._engine = InferenceEngineFactory.create_yolo(
                    model_path=self.model_name,
                    confidence=self.confidence_threshold,
                    accelerator=self._accelerator,
                )
            elif self.model_type == "vlm":
                self._engine = InferenceEngineFactory.create_vlm(
                    model_name=self.model_name,
                    backend=getattr(settings, "VLM_BACKEND", "ollama"),
                )
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")

            # Load the model
            if not self._engine.load():
                raise RuntimeError(f"Failed to load model: {self.model_name}")

            # Warmup
            self._engine.warmup(iterations=2)

            logger.info(f"Engine initialized on {self._engine.current_accelerator}")

        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}")
            raise

    @property
    def device(self) -> str:
        """Get current device string."""
        if self._engine and self._engine.current_accelerator:
            return self._engine.current_accelerator.value
        return "cpu"

    @property
    def is_loaded(self) -> bool:
        """Check if engine is loaded."""
        return self._engine is not None and self._engine.is_loaded

    def detect(
        self,
        frame: np.ndarray,
        roi: dict[str, Any] | None = None,
        classes: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Perform object detection on a single frame.

        Args:
            frame: Input image (BGR, HWC format)
            roi: Optional region of interest {"x": int, "y": int, "width": int, "height": int}
            classes: Optional list of class IDs to detect

        Returns:
            List of detection dictionaries with bbox, confidence, class_name, class_id
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        # Apply ROI if specified
        detection_frame = frame
        roi_offset = (0, 0)

        if roi:
            x, y = roi.get("x", 0), roi.get("y", 0)
            w, h = roi.get("width", frame.shape[1]), roi.get("height", frame.shape[0])
            detection_frame = frame[y : y + h, x : x + w]
            roi_offset = (x, y)

        # Run inference
        result = self._engine.infer(detection_frame, classes=classes)

        # Update statistics
        self._inference_count += 1
        self._total_inference_time += result.inference_time_ms
        self._min_inference_time = min(self._min_inference_time, result.inference_time_ms)
        self._max_inference_time = max(self._max_inference_time, result.inference_time_ms)

        # Adjust bounding boxes for ROI offset
        detections = []
        for det in result.detections:
            if roi_offset != (0, 0):
                bbox = det["bbox"]
                det["bbox"] = [
                    bbox[0] + roi_offset[0],
                    bbox[1] + roi_offset[1],
                    bbox[2] + roi_offset[0],
                    bbox[3] + roi_offset[1],
                ]
            detections.append(det)

        return detections

    def detect_batch(
        self,
        frames: list[np.ndarray],
        classes: list[int] | None = None,
    ) -> list[list[dict[str, Any]]]:
        """
        Perform batch detection on multiple frames.

        Args:
            frames: List of input images
            classes: Optional class filter

        Returns:
            List of detection lists, one per frame
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded")

        if isinstance(self._engine, YOLOEngine):
            results = self._engine.infer_batch(frames, classes=classes)
            self._inference_count += len(frames)
            for r in results:
                self._total_inference_time += r.inference_time_ms
            return [r.detections for r in results]
        else:
            # Fallback to sequential for non-batched engines
            return [self.detect(f, classes=classes) for f in frames]

    def analyze_image(
        self,
        frame: np.ndarray,
        prompt: str | None = None,
    ) -> str:
        """
        Analyze image using VLM (Vision Language Model).

        Args:
            frame: Input image
            prompt: Custom prompt for analysis

        Returns:
            Text analysis from VLM
        """
        from ..ml.engines.vlm import VLMEngine

        if not isinstance(self._engine, VLMEngine):
            # Create a temporary VLM engine for analysis
            vlm = InferenceEngineFactory.create_vlm(
                model_name=getattr(settings, "VLM_MODEL", "llava"),
            )
            vlm.load()
            result = vlm.infer(frame, prompt=prompt)
            vlm.unload()
            return result.text_response or ""

        result = self._engine.infer(frame, prompt=prompt)
        return result.text_response or ""

    def track(
        self,
        frame: np.ndarray,
        persist: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Perform object tracking on a frame.

        Args:
            frame: Input image
            persist: Persist tracks across frames

        Returns:
            List of detections with track_id
        """
        if not isinstance(self._engine, YOLOEngine):
            raise RuntimeError("Tracking only supported with YOLO engine")

        result = self._engine.track(frame, persist=persist)
        return result.detections

    def switch_model(
        self,
        model_name: str,
        model_type: str | None = None,
    ) -> None:
        """
        Switch to a different model.

        Args:
            model_name: New model name/path
            model_type: Optional new model type
        """
        logger.info(f"Switching model to {model_name}")

        # Unload current engine
        if self._engine:
            self._engine.unload()

        # Update settings
        self.model_name = model_name
        if model_type:
            self.model_type = model_type

        # Reinitialize
        self._initialize_engine()

        # Reset statistics
        self.reset_statistics()

    def set_confidence_threshold(self, threshold: float) -> None:
        """Set confidence threshold for detections."""
        self.confidence_threshold = threshold
        if self._engine:
            self._engine.config.confidence_threshold = threshold

    def get_available_models(self) -> list[str]:
        """Get list of available models from settings."""
        return settings.SUPPORTED_MODELS

    def get_class_names(self) -> dict[int, str]:
        """Get the model's class names mapping."""
        if isinstance(self._engine, YOLOEngine):
            return self._engine.get_class_names()
        return {}

    def get_statistics(self) -> dict[str, Any]:
        """Get inference statistics."""
        avg_time = 0.0
        if self._inference_count > 0:
            avg_time = self._total_inference_time / self._inference_count

        return {
            "model_name": self.model_name,
            "model_type": self.model_type,
            "device": self.device,
            "accelerator": self._accelerator.value,
            "inference_count": self._inference_count,
            "total_inference_time_ms": round(self._total_inference_time, 2),
            "average_inference_time_ms": round(avg_time, 2),
            "min_inference_time_ms": round(self._min_inference_time, 2)
            if self._min_inference_time != float("inf")
            else 0,
            "max_inference_time_ms": round(self._max_inference_time, 2),
            "fps": round(1000 / avg_time, 2) if avg_time > 0 else 0,
        }

    def reset_statistics(self) -> None:
        """Reset inference statistics."""
        self._inference_count = 0
        self._total_inference_time = 0.0
        self._min_inference_time = float("inf")
        self._max_inference_time = 0.0

    def get_hardware_info(self) -> dict[str, Any]:
        """
        Get detailed hardware information for inference.

        Returns:
            Dictionary with hardware capabilities and current configuration.
        """
        info = {
            "current_accelerator": self._accelerator.value,
            "model_loaded": self.is_loaded,
            "model_name": self.model_name,
            "available_accelerators": {},
            "cuda_info": None,
            "system_info": {},
        }

        # Detect available accelerators
        try:
            available = HardwareDetector.detect_all()
            info["available_accelerators"] = {k.value: v for k, v in available.items()}
        except Exception as e:
            logger.warning(f"Failed to detect accelerators: {e}")

        # Get CUDA info
        try:
            import torch

            if torch.cuda.is_available():
                info["cuda_info"] = {
                    "available": True,
                    "device_count": torch.cuda.device_count(),
                    "current_device": torch.cuda.current_device(),
                    "device_name": torch.cuda.get_device_name(0),
                    "device_capability": torch.cuda.get_device_capability(0),
                    "total_memory_gb": round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2),
                }
        except ImportError:
            pass

        # Get system info
        try:
            import psutil

            info["system_info"] = {
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "memory_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "memory_percent": psutil.virtual_memory().percent,
            }
        except ImportError:
            pass

        return info

    def __del__(self):
        """Cleanup on destruction."""
        if self._engine:
            try:
                self._engine.unload()
            except Exception:
                pass


# ============================================================================
# Backward-compatible aliases
# ============================================================================


def detect_objects(frame: np.ndarray, model_name: str | None = None) -> list[dict[str, Any]]:
    """
    Legacy function for backward compatibility.

    Args:
        frame: Input image
        model_name: Optional model name

    Returns:
        List of detections
    """
    service = ObjectDetectionService(model_name=model_name)
    return service.detect(frame)
