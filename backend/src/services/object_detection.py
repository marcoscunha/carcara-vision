"""
Object Detection Service using the ML infrastructure.

This service provides a unified interface for object detection and
VLM-based image analysis, with automatic hardware acceleration selection.
"""

import logging
import os
from typing import Any

import numpy as np

from ..core.config import settings
from ..ml.accelerators.detector import HardwareDetector
from ..ml.base import HardwareAccelerator
from ..ml.engines.yolo import YOLOEngine
from ..ml.sdk import BaseTaskPipeline
from ..ml.sdk import Detection
from ..ml.sdk import DetectionBatchResult
from ..ml.sdk import DetectionResult
from ..ml.sdk import VLMResult
from ..ml.sdk import pipeline as build_pipeline
from ..ml.sdk.exceptions import ModelNotFoundError

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

        # Initialize SDK pipeline and compatibility engine handle
        self._pipeline: BaseTaskPipeline | None = None
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
        """Initialize the SDK pipeline (and expose engine for compatibility)."""
        logger.info(f"Initializing {self.model_type} engine with {self.model_name}")
        logger.info(f"Target accelerator: {self._accelerator}")

        try:
            if self.model_type == "yolo":
                model_candidates = [self.model_name]

                # If a .pt/.onnx/.engine name is provided but the file does not exist,
                # try the registry identifier without extension (e.g. yolov8n.pt -> yolov8n).
                if (
                    isinstance(self.model_name, str)
                    and os.path.splitext(self.model_name)[1].lower() in {".pt", ".onnx", ".engine", ".trt"}
                    and not os.path.isfile(self.model_name)
                ):
                    stem = os.path.splitext(self.model_name)[0]
                    if stem and stem not in model_candidates:
                        model_candidates.append(stem)

                # Last-resort fallback for startup safety.
                if "yolov8n" not in model_candidates:
                    model_candidates.append("yolov8n")

                last_error: Exception | None = None
                for candidate in model_candidates:
                    try:
                        self._pipeline = build_pipeline(
                            task="object-detection",
                            model=candidate,
                            device=self._accelerator.value,
                            confidence=self.confidence_threshold,
                            warmup_iterations=2,
                        )
                        self.model_name = candidate
                        break
                    except ModelNotFoundError as exc:
                        last_error = exc
                        logger.warning("Model candidate '%s' not available, trying next fallback", candidate)

                if self._pipeline is None:
                    raise RuntimeError(
                        f"Unable to initialize YOLO pipeline from candidates: {model_candidates}"
                    ) from last_error
            elif self.model_type == "vlm":
                backend = getattr(settings, "VLM_BACKEND", "ollama")
                runtime = {
                    "openai": "openai_vlm",
                    "ollama": "ollama_vlm",
                    "local": "local_vlm",
                }.get(backend, "ollama_vlm")

                self._pipeline = build_pipeline(
                    task="image-text-to-text",
                    model=self.model_name,
                    device=self._accelerator.value,
                    runtime=runtime,
                    warmup_iterations=1,
                )
            else:
                raise ValueError(f"Unknown model type: {self.model_type}")

            self._engine = getattr(self._pipeline, "_engine", None)
            if self._engine is None:
                raise RuntimeError("SDK pipeline did not expose a backing engine")

            logger.info("Engine initialized on %s", self.device)

        except Exception as e:
            logger.error(f"Failed to initialize engine: {e}")
            # Keep the API process alive even when an optional default model is missing.
            self._pipeline = None
            self._engine = None

    @property
    def device(self) -> str:
        """Get current device string."""
        if self._engine and self._engine.current_accelerator:
            return self._engine.current_accelerator.value
        return "cpu"

    @property
    def engine(self) -> YOLOEngine:
        """Expose underlying inference engine for worker integrations."""
        if self._engine is None:
            raise RuntimeError("Inference engine not initialized")
        return self._engine

    @property
    def is_loaded(self) -> bool:
        """Check if engine is loaded."""
        return self._pipeline is not None and self._engine is not None and self._engine.is_loaded

    @staticmethod
    def _to_legacy_detection(det: Detection) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "bbox": det.bbox.to_list(),
            "confidence": det.score,
            "class_name": det.label,
            "class_id": det.class_id,
        }
        if det.track_id is not None:
            payload["track_id"] = det.track_id
        return payload

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

        if self._pipeline is None or not callable(self._pipeline):
            raise RuntimeError("Object detection pipeline is not initialized")

        # Run inference through SDK pipeline
        result: DetectionResult = self._pipeline(
            detection_frame,
            confidence=self.confidence_threshold,
            classes=classes,
        )

        # Update statistics
        self._inference_count += 1
        self._total_inference_time += result.latency_ms
        self._min_inference_time = min(self._min_inference_time, result.latency_ms)
        self._max_inference_time = max(self._max_inference_time, result.latency_ms)

        # Adjust bounding boxes for ROI offset
        detections: list[dict[str, Any]] = []
        for sdk_det in result.detections:
            det = self._to_legacy_detection(sdk_det)
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

        if self._pipeline is None or not hasattr(self._pipeline, "batch"):
            return [self.detect(f, classes=classes) for f in frames]

        batch_result = self._pipeline.batch(
            frames,
            confidence=self.confidence_threshold,
            classes=classes,
        )
        if not isinstance(batch_result, DetectionBatchResult):
            return [self.detect(f, classes=classes) for f in frames]

        self._inference_count += len(batch_result.items)
        self._total_inference_time += batch_result.total_latency_ms
        for item in batch_result.items:
            self._min_inference_time = min(self._min_inference_time, item.latency_ms)
            self._max_inference_time = max(self._max_inference_time, item.latency_ms)

        return [[self._to_legacy_detection(det) for det in item.detections] for item in batch_result.items]

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
        if self.model_type == "vlm" and self._pipeline is not None:
            result: VLMResult = self._pipeline(frame, prompt=prompt)
            return result.text

        # Fallback: create a transient VLM SDK pipeline for analysis.
        vlm_model = getattr(settings, "VLM_MODEL", "llava")
        backend = getattr(settings, "VLM_BACKEND", "ollama")
        runtime = {
            "openai": "openai_vlm",
            "ollama": "ollama_vlm",
            "local": "local_vlm",
        }.get(backend, "ollama_vlm")

        temp = build_pipeline(
            task="image-text-to-text",
            model=vlm_model,
            device=self._accelerator.value,
            runtime=runtime,
        )
        try:
            result: VLMResult = temp(frame, prompt=prompt)
            return result.text
        finally:
            temp.close()

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

        # Unload current pipeline
        if self._pipeline:
            self._pipeline.close()
        self._pipeline = None
        self._engine = None

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
        if self._engine and hasattr(self._engine, "config"):
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
        if self._pipeline:
            try:
                self._pipeline.close()
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
