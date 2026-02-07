"""
Base classes for ML inference abstraction layer.

This module defines the core abstractions for all inference engines,
enabling support for multiple model types and hardware accelerators.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class ModelType(str, Enum):
    """Supported model types."""

    YOLO = "yolo"
    VLM = "vlm"  # Vision Language Models (LLaVA, GPT-4V, etc.)
    CUSTOM = "custom"
    ONNX = "onnx"
    TENSORRT = "tensorrt"


class HardwareAccelerator(str, Enum):
    """Supported hardware accelerators."""

    CPU = "cpu"
    CUDA = "cuda"
    TENSORRT = "tensorrt"
    JETSON = "jetson"  # Jetson Nano / Xavier / Orin
    RPI = "rpi"  # Raspberry Pi (with optional Coral TPU)
    CORAL_TPU = "coral_tpu"  # Google Coral Edge TPU
    OPENVINO = "openvino"  # Intel OpenVINO
    HAILO = "hailo"  # Hailo-8 AI accelerator


@dataclass
class BoundingBox:
    """Bounding box detection result."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_list(self) -> list[float]:
        return [self.x1, self.y1, self.x2, self.y2]

    def to_dict(self) -> dict[str, float]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center(self) -> tuple:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass
class InferenceResult:
    """
    Unified inference result structure.

    Supports both object detection and VLM responses.
    """

    # Common fields
    model_name: str
    inference_time_ms: float
    hardware_used: HardwareAccelerator

    # Object detection fields
    detections: list[dict[str, Any]] = field(default_factory=list)

    # VLM response fields (for vision-language models)
    text_response: str | None = None

    # Raw model output for custom processing
    raw_output: Any | None = None

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_detection(
        self,
        bbox: BoundingBox | list[float],
        class_name: str,
        class_id: int,
        confidence: float,
        **extra,
    ):
        """Add a detection to the results."""
        if isinstance(bbox, BoundingBox):
            bbox_data = bbox.to_list()
        else:
            bbox_data = bbox

        detection = {
            "bbox": bbox_data,
            "class_name": class_name,
            "class_id": class_id,
            "confidence": confidence,
            **extra,
        }
        self.detections.append(detection)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "model_name": self.model_name,
            "inference_time_ms": self.inference_time_ms,
            "hardware_used": self.hardware_used.value,
            "detections": self.detections,
            "text_response": self.text_response,
            "metadata": self.metadata,
        }


@dataclass
class ModelConfig:
    """Configuration for loading and running a model."""

    model_path: str
    model_type: ModelType
    model_name: str

    # Inference settings
    confidence_threshold: float = 0.5
    iou_threshold: float = 0.45
    max_detections: int = 100

    # Hardware settings
    preferred_accelerator: HardwareAccelerator = HardwareAccelerator.CPU
    fallback_accelerators: list[HardwareAccelerator] = field(default_factory=list)

    # Input preprocessing
    input_size: tuple = (640, 640)  # (width, height)
    normalize: bool = True
    bgr_to_rgb: bool = True

    # Model-specific options
    options: dict[str, Any] = field(default_factory=dict)

    # VLM-specific settings
    vlm_prompt: str | None = None
    vlm_max_tokens: int = 512
    vlm_temperature: float = 0.7


class BaseInferenceEngine(ABC):
    """
    Abstract base class for all inference engines.

    Implement this class to add support for new model types or hardware accelerators.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self._model = None
        self._is_loaded = False
        self._current_accelerator: HardwareAccelerator | None = None

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready for inference."""
        return self._is_loaded

    @property
    def current_accelerator(self) -> HardwareAccelerator | None:
        """Get the currently active hardware accelerator."""
        return self._current_accelerator

    @abstractmethod
    def load(self) -> bool:
        """
        Load the model into memory.

        Returns:
            True if model loaded successfully, False otherwise.
        """
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release model resources."""
        pass

    @abstractmethod
    def infer(self, image: np.ndarray, **kwargs) -> InferenceResult:
        """
        Run inference on an image.

        Args:
            image: Input image as numpy array (BGR format, HWC)
            **kwargs: Additional inference parameters

        Returns:
            InferenceResult containing detections or VLM response
        """
        pass

    @abstractmethod
    def get_supported_accelerators(self) -> list[HardwareAccelerator]:
        """Return list of hardware accelerators supported by this engine."""
        pass

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for model input.

        Override this method for custom preprocessing.
        """
        import cv2

        # Resize to model input size
        target_w, target_h = self.config.input_size
        processed = cv2.resize(image, (target_w, target_h))

        # BGR to RGB conversion
        if self.config.bgr_to_rgb:
            processed = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)

        # Normalize
        if self.config.normalize:
            processed = processed.astype(np.float32) / 255.0

        return processed

    def warmup(self, iterations: int = 3) -> None:
        """
        Warm up the model with dummy inference.

        Useful for TensorRT and other JIT-compiled models.
        """
        if not self._is_loaded:
            raise RuntimeError("Model must be loaded before warmup")

        dummy_input = np.zeros((self.config.input_size[1], self.config.input_size[0], 3), dtype=np.uint8)

        for _ in range(iterations):
            self.infer(dummy_input)

    def __enter__(self):
        """Context manager entry."""
        self.load()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.unload()


class BaseAcceleratorBackend(ABC):
    """
    Abstract base class for hardware accelerator backends.

    Implement this to add support for new hardware accelerators.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this accelerator is available on the system."""
        pass

    @abstractmethod
    def get_device_info(self) -> dict[str, Any]:
        """Get information about the accelerator device."""
        pass

    @abstractmethod
    def optimize_model(self, model_path: str, output_path: str, **kwargs) -> str:
        """
        Optimize a model for this accelerator.

        Args:
            model_path: Path to the original model
            output_path: Path to save optimized model
            **kwargs: Accelerator-specific optimization options

        Returns:
            Path to the optimized model
        """
        pass
