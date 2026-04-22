"""
SDK output types.

These are task-stable output objects that remain constant regardless of the
underlying runtime (YOLO, ONNX Runtime, TensorRT, VLM APIs).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class BBox:
    """Normalised bounding-box in pixel coordinates (x1, y1, x2, y2)."""

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
    def area(self) -> float:
        return self.width * self.height

    @classmethod
    def from_list(cls, coords: list[float]) -> BBox:
        return cls(x1=coords[0], y1=coords[1], x2=coords[2], y2=coords[3])


@dataclass
class Detection:
    """A single object detection result."""

    bbox: BBox
    score: float
    label: str
    class_id: int
    track_id: int | None = None
    mask: Any | None = None  # numpy array when segmentation is run
    keypoints: Any | None = None  # numpy array when pose is run
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "bbox": self.bbox.to_dict(),
            "score": self.score,
            "label": self.label,
            "class_id": self.class_id,
        }
        if self.track_id is not None:
            d["track_id"] = self.track_id
        if self.extra:
            d.update(self.extra)
        return d


@dataclass
class RuntimeInfo:
    """Describes the runtime actually used for a given inference call."""

    runtime: str  # yolo | onnxruntime | tensorrt | openai_vlm | …
    device: str  # cpu | cuda | jetson | …
    dtype: str  # fp32 | fp16 | int8 | auto
    providers: list[str] = field(default_factory=list)  # ORT ExecutionProvider list
    model_path: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime": self.runtime,
            "device": self.device,
            "dtype": self.dtype,
            "providers": self.providers,
            "model_path": self.model_path,
            **self.extra,
        }


@dataclass
class DetectionResult:
    """
    Output of a single call to an object-detection / segmentation / pose pipeline.

    Mirrors `InferenceResult` from ml/base.py but decoupled from engine internals.
    """

    detections: list[Detection]
    latency_ms: float
    runtime_info: RuntimeInfo
    frame_id: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detections": [d.to_dict() for d in self.detections],
            "latency_ms": self.latency_ms,
            "runtime_info": self.runtime_info.to_dict(),
            **({"frame_id": self.frame_id} if self.frame_id is not None else {}),
            **self.extra,
        }

    @property
    def count(self) -> int:
        return len(self.detections)


@dataclass
class DetectionBatchResult:
    """Output of a batched detection call."""

    items: list[DetectionResult]
    total_latency_ms: float
    throughput_fps: float
    runtime_info: RuntimeInfo

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [r.to_dict() for r in self.items],
            "total_latency_ms": self.total_latency_ms,
            "throughput_fps": self.throughput_fps,
            "runtime_info": self.runtime_info.to_dict(),
        }


@dataclass
class VLMResult:
    """Output of a vision-language model pipeline call."""

    text: str
    latency_ms: float
    runtime_info: RuntimeInfo
    tokens_used: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "latency_ms": self.latency_ms,
            "runtime_info": self.runtime_info.to_dict(),
            **({"tokens_used": self.tokens_used} if self.tokens_used is not None else {}),
            **self.extra,
        }
