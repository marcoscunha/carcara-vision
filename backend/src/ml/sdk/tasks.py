"""
Task adapters.

Each adapter owns:
  - ``__call__`` for single-input inference
  - ``batch`` for batched input
  - ``stream`` for iterator/generator input
  - ``benchmark`` for throughput/latency measurement

Adapters translate between the engine's InferenceResult and the SDK's
stable output types (DetectionResult, VLMResult, ...).
"""

from __future__ import annotations

import logging
import time
from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Generator
    from collections.abc import Iterator

    from ..base import BaseInferenceEngine
    from ..base import InferenceResult
    from .config import PipelineConfig
    from .resolver import ResolvedPlan

from .types import BBox
from .types import Detection
from .types import DetectionBatchResult
from .types import DetectionResult
from .types import RuntimeInfo
from .types import VLMResult

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Base                                                                         #
# --------------------------------------------------------------------------- #


class BaseTaskPipeline(ABC):
    """
    Base class for all task adapters.

    Concrete adapters implement ``_infer_one`` which receives a single numpy
    frame and returns the SDK output type.
    """

    def __init__(self, engine: BaseInferenceEngine, plan: ResolvedPlan) -> None:
        self._engine = engine
        self._plan = plan
        self._config: PipelineConfig = plan.config

    # ---------------------------------------------------------------------- #
    # Public interface                                                         #
    # ---------------------------------------------------------------------- #

    def __call__(self, inputs: Any, **kwargs: Any) -> Any:
        """
        Run inference on a single input or a list of inputs.

        Parameters
        ----------
        inputs:
            numpy array (HxWxC uint8) or list of such arrays.
        **kwargs:
            Task-specific overrides (confidence, iou, …).
        """
        if isinstance(inputs, list | tuple):
            return self.batch(inputs, **kwargs)
        return self._infer_one(inputs, **kwargs)

    def batch(
        self,
        inputs: list[Any],
        batch_size: int | None = None,
        **kwargs: Any,
    ) -> DetectionBatchResult | list[Any]:
        """
        Run inference on a list of inputs.

        Results are collected into a DetectionBatchResult (or a plain list for
        VLM tasks where batching is less meaningful).
        """
        bs = batch_size or self._config.batch_size
        results: list[Any] = []
        t_start = time.perf_counter()

        for i in range(0, len(inputs), bs):
            chunk = inputs[i : i + bs]
            for frame in chunk:
                results.append(self._infer_one(frame, **kwargs))

        elapsed_ms = (time.perf_counter() - t_start) * 1000
        fps = len(inputs) / max(elapsed_ms / 1000, 1e-9)

        return self._wrap_batch(results, elapsed_ms, fps)

    def stream(
        self,
        iterable: Iterator[Any] | Generator[Any],
        batch_size: int | None = None,
        **kwargs: Any,
    ) -> Generator[Any]:
        """
        Yield results one-by-one for a streaming source (camera, dataset, …).
        """
        for item in iterable:
            yield self._infer_one(item, **kwargs)

    def warmup(self, iterations: int = 3, frame_size: tuple[int, int] = (640, 640)) -> None:
        """Run the engine on synthetic frames to prime CUDA/TRT kernels."""
        dummy = np.zeros((*frame_size, 3), dtype=np.uint8)
        logger.info("Warming up '%s' for %d iterations…", self._config.model, iterations)
        for _ in range(iterations):
            self._infer_one(dummy)

    def benchmark(
        self,
        samples: int = 100,
        frame_size: tuple[int, int] = (640, 640),
        warmup: int = 5,
    ) -> dict[str, float]:
        """
        Measure throughput and latency over *samples* synthetic frames.

        Returns a dict with keys:
        ``samples``, ``warmup``, ``total_ms``, ``mean_ms``, ``min_ms``,
        ``max_ms``, ``throughput_fps``.
        """
        dummy = np.zeros((*frame_size, 3), dtype=np.uint8)

        # warmup pass (not counted)
        for _ in range(warmup):
            self._infer_one(dummy)

        latencies: list[float] = []
        t_total_start = time.perf_counter()
        for _ in range(samples):
            t0 = time.perf_counter()
            self._infer_one(dummy)
            latencies.append((time.perf_counter() - t0) * 1000)
        total_ms = (time.perf_counter() - t_total_start) * 1000

        return {
            "samples": samples,
            "warmup": warmup,
            "total_ms": round(total_ms, 3),
            "mean_ms": round(sum(latencies) / len(latencies), 3),
            "min_ms": round(min(latencies), 3),
            "max_ms": round(max(latencies), 3),
            "throughput_fps": round(samples / max(total_ms / 1000, 1e-9), 2),
        }

    def info(self) -> dict[str, Any]:
        """Return a summary of the resolved plan (runtime, device, dtype, …)."""
        return {
            "task": self._config.task,
            "model": self._config.model,
            **self._plan.to_dict(),
        }

    def close(self) -> None:
        """Unload the engine and free resources."""
        try:
            self._engine.unload()
        except Exception:
            logger.debug("Engine unload raised (may be a no-op).", exc_info=True)

    # ---------------------------------------------------------------------- #
    # Subclass contract                                                        #
    # ---------------------------------------------------------------------- #

    @abstractmethod
    def _infer_one(self, frame: Any, **kwargs: Any) -> Any:
        """Run inference on a single input and return an SDK output type."""

    @abstractmethod
    def _wrap_batch(self, results: list[Any], total_ms: float, fps: float) -> Any:
        """Wrap a list of single results into a batch output."""

    # ---------------------------------------------------------------------- #
    # Helpers                                                                  #
    # ---------------------------------------------------------------------- #

    def _make_runtime_info(self) -> RuntimeInfo:
        return RuntimeInfo(
            runtime=self._plan.runtime,
            device=self._plan.accelerator.value,
            dtype=self._plan.dtype,
            providers=self._plan.providers,
            model_path=self._plan.model_path,
        )


# --------------------------------------------------------------------------- #
# Object-detection adapter                                                     #
# --------------------------------------------------------------------------- #


class ObjectDetectionPipeline(BaseTaskPipeline):
    """Adapter for object-detection, instance-segmentation, and pose tasks."""

    def _infer_one(self, frame: Any, **kwargs: Any) -> DetectionResult:
        confidence = kwargs.get("confidence", self._config.confidence)
        engine_kwargs = {k: v for k, v in kwargs.items() if k != "confidence"}

        t0 = time.perf_counter()
        raw: InferenceResult = self._engine.infer(frame, **engine_kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000

        detections = [
            Detection(
                bbox=BBox.from_list(d["bbox"]),
                score=d["confidence"],
                label=d["class_name"],
                class_id=d["class_id"],
                track_id=d.get("track_id"),
            )
            for d in raw.detections
            if d["confidence"] >= confidence
        ]

        return DetectionResult(
            detections=detections,
            latency_ms=latency_ms,
            runtime_info=self._make_runtime_info(),
        )

    def _wrap_batch(self, results: list[DetectionResult], total_ms: float, fps: float) -> DetectionBatchResult:
        return DetectionBatchResult(
            items=results,
            total_latency_ms=total_ms,
            throughput_fps=fps,
            runtime_info=self._make_runtime_info(),
        )


# --------------------------------------------------------------------------- #
# VLM adapter                                                                  #
# --------------------------------------------------------------------------- #


class VLMPipeline(BaseTaskPipeline):
    """Adapter for image-text-to-text (VLM) tasks."""

    def _infer_one(self, frame: Any, **kwargs: Any) -> VLMResult:
        t0 = time.perf_counter()
        raw: InferenceResult = self._engine.infer(frame)
        latency_ms = (time.perf_counter() - t0) * 1000

        return VLMResult(
            text=raw.text_response or "",
            latency_ms=latency_ms,
            runtime_info=self._make_runtime_info(),
        )

    def _wrap_batch(self, results: list[VLMResult], total_ms: float, fps: float) -> list[VLMResult]:
        return results


# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

_TASK_ADAPTER: dict[str, type[BaseTaskPipeline]] = {
    "object-detection": ObjectDetectionPipeline,
    "instance-segmentation": ObjectDetectionPipeline,
    "pose-estimation": ObjectDetectionPipeline,
    "image-text-to-text": VLMPipeline,
}


def get_adapter_class(task: str) -> type[BaseTaskPipeline]:
    """Return the adapter class for the given task string."""
    cls = _TASK_ADAPTER.get(task)
    if cls is None:
        raise ValueError(f"No adapter registered for task '{task}'.")
    return cls
