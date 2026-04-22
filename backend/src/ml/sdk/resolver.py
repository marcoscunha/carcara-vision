"""
SDK resolver - the "Auto" layer.

Translates the user-visible (device, runtime, dtype) choices in PipelineConfig
into the internal (ModelConfig, engine_class) pair that the factory understands.

Resolution order
----------------
1. If ``device`` / ``runtime`` are explicit -> validate and use them.
2. If either is ``"auto"`` -> infer from model file extension and HardwareDetector.
3. Choose dtype / providers accordingly.

This is intentionally a *stateless* module of pure functions so it is easy to
unit-test the decision matrix without spinning up any hardware.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING
from typing import Any

from ..accelerators.detector import HardwareDetector
from ..base import HardwareAccelerator
from ..base import ModelConfig
from ..base import ModelType
from ..registry import ModelRegistry
from .exceptions import DeviceUnavailableError
from .exceptions import ModelNotFoundError
from .exceptions import RuntimeNotSupportedError

if TYPE_CHECKING:
    from .config import PipelineConfig


logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Internal maps                                                                #
# --------------------------------------------------------------------------- #

_TASK_TO_MODEL_TYPE: dict[str, ModelType] = {
    "object-detection": ModelType.YOLO,
    "instance-segmentation": ModelType.YOLO,
    "pose-estimation": ModelType.YOLO,
    "image-text-to-text": ModelType.VLM,
}

_DEVICE_TO_ACCELERATOR: dict[str, HardwareAccelerator] = {
    "cpu": HardwareAccelerator.CPU,
    "cuda": HardwareAccelerator.CUDA,
    "tensorrt": HardwareAccelerator.TENSORRT,
    "jetson": HardwareAccelerator.JETSON,
}

_RUNTIME_REQUIRES_IMPORT: dict[str, str] = {
    "tensorrt": "tensorrt",
    "onnxruntime": "onnxruntime",
    "ollama_vlm": "ollama",
    "local_vlm": "transformers",
}

# dtype -> ort dtype string (informational only at this layer)
_DTYPE_ORT: dict[str, str] = {
    "fp32": "float32",
    "fp16": "float16",
    "int8": "int8",
    "auto": "float32",
}


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #


class ResolvedPlan:
    """
    The concrete plan derived from PipelineConfig by the resolver.

    Passed through to the task adapter / engine factory.
    """

    def __init__(
        self,
        config: PipelineConfig,
        model_path: str,
        model_type: ModelType,
        accelerator: HardwareAccelerator,
        runtime: str,
        dtype: str,
        providers: list[str],
        extra: dict[str, Any],
    ) -> None:
        self.config = config
        self.model_path = model_path
        self.model_type = model_type
        self.accelerator = accelerator
        self.runtime = runtime
        self.dtype = dtype
        self.providers = providers
        self.extra = extra

    def build_model_config(self) -> ModelConfig:
        """Build a ModelConfig for the engine factory."""
        return ModelConfig(
            model_path=self.model_path,
            model_type=self.model_type,
            model_name=self.config.model,
            confidence_threshold=self.config.confidence,
            iou_threshold=self.config.iou,
            max_detections=self.config.max_detections,
            preferred_accelerator=self.accelerator,
            fallback_accelerators=[HardwareAccelerator.CPU],
            options={**self.config.options, **self.extra},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_path": self.model_path,
            "model_type": self.model_type.value,
            "accelerator": self.accelerator.value,
            "runtime": self.runtime,
            "dtype": self.dtype,
            "providers": self.providers,
        }


def resolve(config: PipelineConfig) -> ResolvedPlan:
    """
    Main entry point.  Returns a ResolvedPlan for the given config.

    Raises
    ------
    ModelNotFoundError
        When the model id / path cannot be located.
    DeviceUnavailableError
        When the explicitly requested device is not available.
    RuntimeNotSupportedError
        When the explicitly requested runtime is not installed.
    """
    model_path = _resolve_model_path(config.model)
    model_type = _resolve_model_type(config.task, model_path)
    accelerator = _resolve_accelerator(config.device)
    runtime = _resolve_runtime(config.runtime, model_path, accelerator)
    dtype = _resolve_dtype(config.dtype, runtime, accelerator)
    providers = _resolve_ort_providers(runtime, accelerator)

    plan = ResolvedPlan(
        config=config,
        model_path=model_path,
        model_type=model_type,
        accelerator=accelerator,
        runtime=runtime,
        dtype=dtype,
        providers=providers,
        extra={},
    )

    logger.info(
        "Resolved plan: model=%s type=%s device=%s runtime=%s dtype=%s",
        model_path,
        model_type.value,
        accelerator.value,
        runtime,
        dtype,
    )
    return plan


# --------------------------------------------------------------------------- #
# Internal helpers                                                             #
# --------------------------------------------------------------------------- #


def _resolve_model_path(model: str) -> str:
    """
    Turn a model identifier into an absolute path.

    Lookup order:
    1. Existing file path (absolute or relative to cwd)
    2. ModelRegistry by name
    3. Raise ModelNotFoundError
    """
    # Direct file path
    if os.path.isfile(model):
        return os.path.abspath(model)

    # Registry lookup
    registry = ModelRegistry()
    info = registry.get_model(model)
    if info is not None and os.path.isfile(info.path):
        return os.path.abspath(info.path)

    raise ModelNotFoundError(model)


def _resolve_model_type(task: str, model_path: str) -> ModelType:
    """Determine ModelType from task and file extension."""
    if task == "image-text-to-text":
        return ModelType.VLM

    ext = os.path.splitext(model_path)[1].lower()
    if ext in (".engine", ".trt"):
        return ModelType.TENSORRT
    if ext == ".onnx":
        return ModelType.ONNX
    # Default YOLO for vision tasks
    return _TASK_TO_MODEL_TYPE.get(task, ModelType.YOLO)


def _resolve_accelerator(device: str) -> HardwareAccelerator:
    """Map device string to HardwareAccelerator, or auto-detect."""
    if device == "auto":
        return HardwareDetector.get_best_accelerator()

    accelerator = _DEVICE_TO_ACCELERATOR.get(device)
    if accelerator is None:
        raise DeviceUnavailableError(device, f"Unknown device '{device}'")

    available = HardwareDetector.detect_all()
    if not available.get(accelerator, False):
        raise DeviceUnavailableError(
            device,
            f"Hardware accelerator '{device}' was not detected on this machine.",
        )

    return accelerator


def _resolve_runtime(runtime: str, model_path: str, accelerator: HardwareAccelerator) -> str:
    """Infer or validate the runtime string."""
    if runtime != "auto":
        _assert_runtime_available(runtime)
        return runtime

    # Auto-infer from extension
    ext = os.path.splitext(model_path)[1].lower()
    if ext in (".engine", ".trt"):
        return "tensorrt"
    if ext == ".onnx":
        return "onnxruntime"
    if ext == ".pt":
        return "yolo"

    # Fallback by accelerator capability
    if accelerator in (HardwareAccelerator.TENSORRT, HardwareAccelerator.JETSON):
        return "tensorrt"
    if accelerator == HardwareAccelerator.CUDA:
        return "onnxruntime"
    return "yolo"


def _resolve_dtype(dtype: str, runtime: str, accelerator: HardwareAccelerator) -> str:
    """Pick a concrete dtype if 'auto' was requested."""
    if dtype != "auto":
        return dtype

    # fp16 is safe for CUDA and TRT
    if accelerator in (HardwareAccelerator.CUDA, HardwareAccelerator.TENSORRT, HardwareAccelerator.JETSON):
        return "fp16"
    return "fp32"


def _resolve_ort_providers(runtime: str, accelerator: HardwareAccelerator) -> list[str]:
    """Build the ORT ExecutionProvider list when runtime is onnxruntime."""
    if runtime != "onnxruntime":
        return []

    providers: list[str] = []
    if accelerator == HardwareAccelerator.TENSORRT:
        providers.append("TensorrtExecutionProvider")
    if accelerator in (HardwareAccelerator.CUDA, HardwareAccelerator.JETSON):
        providers.append("CUDAExecutionProvider")
    providers.append("CPUExecutionProvider")
    return providers


def _assert_runtime_available(runtime: str) -> None:
    """Raise RuntimeNotSupportedError if a required package is missing."""
    required = _RUNTIME_REQUIRES_IMPORT.get(runtime)
    if required is None:
        return
    try:
        __import__(required)
    except ImportError:
        raise RuntimeNotSupportedError(
            runtime,
            f"Python package '{required}' is not installed.",
        )
