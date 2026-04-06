"""
Inference Worker Manager — singleton that owns all per-stream InferenceWorkers.

Responsibilities:
  - Start workers when a stream becomes active with detection enabled.
  - Stop/restart workers on stream deletion or config change.
  - Provide WebSocket subscription routing.
  - Expose aggregate stats across all workers.

Usage::

    # On application startup
    inference_worker_manager.restore_workers(active_streams, db_session)

    # When a stream is created / detection toggled on
    inference_worker_manager.start_worker(stream, runtime_config)

    # When a stream is deleted / detection toggled off
    inference_worker_manager.stop_worker(stream_id)

    # WebSocket endpoint (per stream)
    queue = asyncio.Queue(maxsize=30)
    inference_worker_manager.subscribe(stream_id, queue)
    try:
        event = await queue.get()
    finally:
        inference_worker_manager.unsubscribe(stream_id, queue)
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlparse

from ..core.config import settings
from ..ml.registry import TASK_TYPE_DETECT
from ..ml.registry import model_registry
from .inference_worker import InferenceWorker
from .inference_worker import WorkerConfig

if TYPE_CHECKING:
    import asyncio

    from ..models.stream import Stream

logger = logging.getLogger(__name__)


def _mediamtx_rtsp_base() -> str:
    """Internal RTSP base URL for reading Raw streams from MediaMTX."""
    parsed = urlparse(settings.MEDIAMTX_API_URL)
    host = parsed.hostname or "mediamtx"
    return f"rtsp://{host}:{settings.MEDIAMTX_RTSP_PORT}"


def _build_worker_config(stream: Stream, runtime: Any | None = None) -> WorkerConfig:
    """
    Derive a ``WorkerConfig`` from a ``Stream`` ORM object.

    Per-stream metadata takes precedence; falls back to global runtime config.
    """
    from ..services.inference_runtime import inference_runtime_service

    metadata = stream.stream_metadata or {}
    rt = runtime or inference_runtime_service.get()

    # Persisted stream metadata is authoritative; runtime is fallback.
    model_name = metadata.get("detection_model") or rt.model_name
    model_info = model_registry.get_model(model_name) if model_name else None
    if model_info and model_info.path:
        model_name = model_info.path
    task_type = metadata.get("detection_task_type") or getattr(rt, "task_type", TASK_TYPE_DETECT)
    confidence = float(metadata.get("detection_confidence", 0.5))
    classes_filter = metadata.get("detection_classes") or None
    accelerator = rt.accelerator.value if hasattr(rt.accelerator, "value") else str(rt.accelerator)

    width = int(metadata.get("width", 640))
    height = int(metadata.get("height", 360))
    max_inference_fps = int(metadata.get("max_inference_fps", metadata.get("detection_max_inference_fps", 10)))
    output_fps = int(metadata.get("output_fps", metadata.get("fps", 25)))

    max_inference_fps = max(1, min(max_inference_fps, 60))
    output_fps = max(1, min(output_fps, 60))

    rtsp_base = _mediamtx_rtsp_base()
    rtsp_url = f"{rtsp_base}/{stream.stream_name}"

    return WorkerConfig(
        stream_id=stream.id,
        stream_name=stream.stream_name,
        rtsp_url=rtsp_url,
        mediamtx_rtsp_base=rtsp_base,
        model_name=model_name,
        task_type=task_type,
        confidence=confidence,
        classes_filter=classes_filter,
        accelerator=accelerator,
        width=width,
        height=height,
        max_inference_fps=max_inference_fps,
        output_fps=output_fps,
    )


def _is_detection_enabled(stream: Stream) -> bool:
    metadata = stream.stream_metadata or {}
    if "detection_enabled" in metadata:
        return bool(metadata.get("detection_enabled"))
    return bool(getattr(stream, "detection_enabled", False))


class InferenceWorkerManager:
    """
    Global manager for all per-stream InferenceWorkers.

    Thread-safe: all public methods acquire a simple lock.
    """

    def __init__(self) -> None:
        self._workers: dict[int, InferenceWorker] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Worker lifecycle
    # ------------------------------------------------------------------ #

    def start_worker(self, stream: Stream, runtime: Any | None = None) -> None:
        """
        Start (or restart) the inference worker for ``stream``.

        Silently skips if detection is not enabled on the stream.
        """
        if not _is_detection_enabled(stream):
            logger.debug("Detection not enabled for stream %d — no worker started", stream.id)
            return
        if not stream.stream_name:
            logger.warning("Stream %d has no stream_name — skipping worker start", stream.id)
            return

        config = _build_worker_config(stream, runtime)
        with self._lock:
            self._stop_and_remove(stream.id)
            worker = InferenceWorker(config)
            worker.start()
            self._workers[stream.id] = worker
            logger.info("Worker started for stream %d (%s)", stream.id, stream.stream_name)

    def stop_worker(self, stream_id: int) -> None:
        """Stop and remove the worker for the given stream ID."""
        with self._lock:
            self._stop_and_remove(stream_id)

    def restart_worker(self, stream: Stream, runtime: Any | None = None) -> None:
        """Stop then start the worker (useful after config changes)."""
        self.stop_worker(stream.id)
        self.start_worker(stream, runtime)

    def stop_all(self) -> None:
        """Stop every running worker (called on application shutdown)."""
        with self._lock:
            for stream_id in list(self._workers):
                self._stop_and_remove(stream_id)
        logger.info("All inference workers stopped")

    def get_worker(self, stream_id: int) -> InferenceWorker | None:
        with self._lock:
            return self._workers.get(stream_id)

    def list_stats(self) -> list[dict[str, Any]]:
        with self._lock:
            return [w.get_stats() for w in self._workers.values()]

    # ------------------------------------------------------------------ #
    # WebSocket subscription routing
    # ------------------------------------------------------------------ #

    def subscribe(self, stream_id: int, queue: asyncio.Queue) -> bool:
        """
        Register a WebSocket queue to receive events from ``stream_id``.

        Returns True if the worker exists and the subscription was added.
        """
        with self._lock:
            worker = self._workers.get(stream_id)
        if worker is None:
            return False
        worker.add_subscriber(queue)
        return True

    def unsubscribe(self, stream_id: int, queue: asyncio.Queue) -> None:
        with self._lock:
            worker = self._workers.get(stream_id)
        if worker:
            worker.remove_subscriber(queue)

    # ------------------------------------------------------------------ #
    # Startup restore
    # ------------------------------------------------------------------ #

    def restore_workers(self, active_streams: list[Stream], runtime: Any | None = None) -> None:
        """
        Re-create workers for streams that are already active in the DB.

        Call this once during application lifespan startup after the DB is
        available.
        """
        for stream in active_streams:
            if _is_detection_enabled(stream) and stream.status == "active":
                self.start_worker(stream, runtime)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _stop_and_remove(self, stream_id: int) -> None:
        """Stop and remove worker; caller must hold ``_lock``."""
        worker = self._workers.pop(stream_id, None)
        if worker:
            worker.stop()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
inference_worker_manager = InferenceWorkerManager()
