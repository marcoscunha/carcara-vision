"""
SDK pipeline configuration.

PipelineConfig is the single data structure passed through the whole SDK.
It mirrors the vocabulary of the design (task, model, device, runtime, dtype)
and maps cleanly onto the existing ModelConfig / HardwareAccelerator internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Literal

# --------------------------------------------------------------------------- #
# Vocabulary types (Literals give IDE completion while keeping them plain str) #
# --------------------------------------------------------------------------- #

DeviceLiteral = Literal["auto", "cpu", "cuda", "tensorrt", "jetson"]
RuntimeLiteral = Literal["auto", "yolo", "onnxruntime", "tensorrt", "openai_vlm", "ollama_vlm", "local_vlm"]
DTypeLiteral = Literal["auto", "fp32", "fp16", "int8"]
TaskLiteral = Literal["object-detection", "instance-segmentation", "pose-estimation", "image-text-to-text"]


@dataclass
class PipelineConfig:
    """
    User-facing configuration for a pipeline.

    All fields have sensible defaults; only ``task`` and ``model`` are required.

    Examples
    --------
    >>> cfg = PipelineConfig(task="object-detection", model="yolo11n")
    >>> cfg = PipelineConfig(
    ...     task="object-detection",
    ...     model="models/detector.onnx",
    ...     device="cuda",
    ...     runtime="onnxruntime",
    ...     dtype="fp16",
    ... )
    """

    # Required
    task: TaskLiteral
    model: str

    # Hardware / runtime selection
    device: DeviceLiteral = "auto"
    runtime: RuntimeLiteral = "auto"
    dtype: DTypeLiteral = "auto"

    # Inference parameters
    batch_size: int = 1
    confidence: float = 0.5
    iou: float = 0.45
    max_detections: int = 100

    # Lifecycle
    warmup_iterations: int = 0

    # Passthrough for engine-specific options (ORT session options, YOLO kwargs …)
    options: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        valid_tasks: set[str] = {
            "object-detection",
            "instance-segmentation",
            "pose-estimation",
            "image-text-to-text",
        }
        if self.task not in valid_tasks:
            raise ValueError(f"Unknown task '{self.task}'. Valid tasks: {sorted(valid_tasks)}")

        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")

        if not (0.0 < self.confidence <= 1.0):
            raise ValueError("confidence must be in (0, 1]")

        if not (0.0 < self.iou <= 1.0):
            raise ValueError("iou must be in (0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "model": self.model,
            "device": self.device,
            "runtime": self.runtime,
            "dtype": self.dtype,
            "batch_size": self.batch_size,
            "confidence": self.confidence,
            "iou": self.iou,
            "max_detections": self.max_detections,
            "warmup_iterations": self.warmup_iterations,
            "options": self.options,
        }
