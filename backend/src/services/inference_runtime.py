"""System-wide inference runtime configuration and metrics tracking."""

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any

from ..core.config import settings
from ..ml.accelerators.detector import HardwareDetector
from ..ml.base import HardwareAccelerator


def _resolve_default_accelerator() -> HardwareAccelerator:
    try:
        return HardwareDetector.get_best_accelerator()
    except Exception:
        return HardwareAccelerator.CPU


@dataclass
class InferenceRuntimeConfig:
    model_name: str
    accelerator: HardwareAccelerator


class InferenceRuntimeService:
    """In-memory system-wide runtime settings for model execution."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._config = InferenceRuntimeConfig(
            model_name=settings.DEFAULT_MODEL,
            accelerator=_resolve_default_accelerator(),
        )

    def get(self) -> InferenceRuntimeConfig:
        with self._lock:
            return InferenceRuntimeConfig(
                model_name=self._config.model_name,
                accelerator=self._config.accelerator,
            )

    def update(
        self, model_name: str | None = None, accelerator: str | HardwareAccelerator | None = None
    ) -> InferenceRuntimeConfig:
        with self._lock:
            if model_name:
                self._config.model_name = model_name
            if accelerator is not None:
                self._config.accelerator = self._coerce_accelerator(accelerator)
            return InferenceRuntimeConfig(
                model_name=self._config.model_name,
                accelerator=self._config.accelerator,
            )

    def list_available_accelerators(self) -> list[str]:
        available = HardwareDetector.detect_all()
        return [acc.value for acc, enabled in available.items() if enabled]

    @staticmethod
    def _coerce_accelerator(accelerator: str | HardwareAccelerator) -> HardwareAccelerator:
        if isinstance(accelerator, HardwareAccelerator):
            return accelerator
        return HardwareAccelerator(accelerator)


class InferenceMetricsService:
    """Tracks rolling realtime inference metrics globally and per stream."""

    def __init__(self, window_size: int = 100) -> None:
        self._lock = Lock()
        self._window_size = window_size
        self._global_times: deque[float] = deque(maxlen=window_size)
        self._per_stream: dict[int, deque[float]] = {}
        self._last_by_stream: dict[int, dict[str, Any]] = {}

    def record(self, stream_id: int, inference_time_ms: float, model_name: str, accelerator: str) -> None:
        value = round(float(inference_time_ms), 2)
        with self._lock:
            self._global_times.append(value)
            stream_times = self._per_stream.setdefault(stream_id, deque(maxlen=self._window_size))
            stream_times.append(value)
            self._last_by_stream[stream_id] = {
                "last_inference_time_ms": value,
                "model_name": model_name,
                "accelerator": accelerator,
            }

    def snapshot(self, stream_id: int | None = None) -> dict[str, Any]:
        with self._lock:
            if stream_id is not None:
                return {
                    "stream_id": stream_id,
                    **self._build_stats(self._per_stream.get(stream_id, deque())),
                    **self._last_by_stream.get(
                        stream_id,
                        {
                            "last_inference_time_ms": 0.0,
                            "model_name": None,
                            "accelerator": None,
                        },
                    ),
                }

            per_stream = {}
            for key, times in self._per_stream.items():
                per_stream[key] = {
                    "stream_id": key,
                    **self._build_stats(times),
                    **self._last_by_stream.get(
                        key,
                        {
                            "last_inference_time_ms": 0.0,
                            "model_name": None,
                            "accelerator": None,
                        },
                    ),
                }

            return {
                "global": self._build_stats(self._global_times),
                "per_stream": per_stream,
            }

    @staticmethod
    def _build_stats(times: deque[float]) -> dict[str, Any]:
        values = list(times)
        count = len(values)
        if count == 0:
            return {
                "samples": 0,
                "avg_inference_time_ms": 0.0,
                "min_inference_time_ms": 0.0,
                "max_inference_time_ms": 0.0,
                "fps": 0.0,
            }

        avg = round(sum(values) / count, 2)
        return {
            "samples": count,
            "avg_inference_time_ms": avg,
            "min_inference_time_ms": round(min(values), 2),
            "max_inference_time_ms": round(max(values), 2),
            "fps": round(1000 / avg, 2) if avg > 0 else 0.0,
        }


inference_runtime_service = InferenceRuntimeService()
inference_metrics_service = InferenceMetricsService()
