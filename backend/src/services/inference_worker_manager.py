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
import os

from ..core.config import settings
from ..ml.registry import TASK_TYPE_DETECT
from ..ml.registry import model_registry
from .alarm_engine import AlarmEngine
from .inference_worker import InferenceWorker
from .inference_worker import WorkerConfig
from .model_batch_coordinator import model_batch_coordinator

if TYPE_CHECKING:
    import asyncio

    from ..models.stream import Stream

logger = logging.getLogger(__name__)


def _resolve_registered_model(name: str | None):
    if not name:
        return None
    info = model_registry.get_model(name)
    if info is not None:
        return info
    stem, ext = os.path.splitext(str(name))
    if ext.lower() in {".pt", ".onnx", ".engine", ".trt"} and stem:
        return model_registry.get_model(stem)
    return None


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
    assigned_model_name = metadata.get("detection_model") or rt.model_name
    model_info = _resolve_registered_model(assigned_model_name)
    if model_info is None:
        raise RuntimeError(f"Configured model '{assigned_model_name}' is not registered")
    if not model_info.is_downloaded:
        raise RuntimeError(f"Configured model '{assigned_model_name}' is not downloaded")
    model_name = model_info.path
    task_type = metadata.get("detection_task_type") or getattr(rt, "task_type", TASK_TYPE_DETECT)
    runtime = metadata.get("detection_runtime", "auto")
    dtype = metadata.get("detection_dtype", "auto")
    providers = metadata.get("detection_providers")
    if providers is not None and not isinstance(providers, list):
        providers = None
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
    encoder_mode = getattr(rt, "accel_encoder_mode", "x264")

    return WorkerConfig(
        stream_id=stream.id,
        stream_name=stream.stream_name,
        rtsp_url=rtsp_url,
        mediamtx_rtsp_base=rtsp_base,
        model_name=model_name,
        assigned_model_name=assigned_model_name,
        task_type=task_type,
        runtime=runtime,
        dtype=dtype,
        providers=providers,
        confidence=confidence,
        classes_filter=classes_filter,
        accelerator=accelerator,
        width=width,
        height=height,
        max_inference_fps=max_inference_fps,
        output_fps=output_fps,
        encoder_mode=encoder_mode,
    )


def _is_detection_enabled(stream: Stream) -> bool:
    metadata = stream.stream_metadata or {}
    if "detection_enabled" in metadata:
        return bool(metadata.get("detection_enabled"))
    return bool(getattr(stream, "detection_enabled", False))


def _build_batch_group_key(config: WorkerConfig) -> str | None:
    """Return a stable key for streams that can share batched inference."""
    if config.task_type != TASK_TYPE_DETECT:
        return None

    providers_key = ",".join(config.providers or [])
    return "|".join(
        [
            str(config.model_name),
            str(config.task_type),
            str(config.accelerator),
            str(config.runtime),
            str(config.dtype),
            providers_key,
        ]
    )


class InferenceWorkerManager:
    """
    Global manager for all per-stream InferenceWorkers.

    Thread-safe: all public methods acquire a simple lock.
    """

    def __init__(self) -> None:
        self._workers: dict[int, InferenceWorker] = {}
        self._engines: dict[int, AlarmEngine] = {}
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

        try:
            config = _build_worker_config(stream, runtime)
            config.batch_group_key = _build_batch_group_key(config)
            config.batch_coordinator = model_batch_coordinator
            with self._lock:
                self._stop_and_remove(stream.id)
                model_batch_coordinator.register_stream(stream.id, config.batch_group_key)
                worker = InferenceWorker(config)
                engine = self._build_engine(stream.id)
                worker.set_alarm_callback(engine.evaluate)
                worker.start()
                self._workers[stream.id] = worker
                self._engines[stream.id] = engine
                logger.info("Worker started for stream %d (%s)", stream.id, stream.stream_name)
        except Exception as exc:
            logger.warning("Worker not started for stream %d: %s", stream.id, exc)

    def stop_worker(self, stream_id: int) -> None:
        """Stop and remove the worker for the given stream ID."""
        with self._lock:
            self._stop_and_remove(stream_id)
            self._engines.pop(stream_id, None)

    def restart_worker(self, stream: Stream, runtime: Any | None = None) -> None:
        """Stop then start the worker (useful after config changes)."""
        self.stop_worker(stream.id)
        self.start_worker(stream, runtime)

    def stop_all(self) -> None:
        """Stop every running worker (called on application shutdown)."""
        with self._lock:
            for stream_id in list(self._workers):
                self._stop_and_remove(stream_id)
            self._engines.clear()
        logger.info("All inference workers stopped")

    def get_worker(self, stream_id: int) -> InferenceWorker | None:
        with self._lock:
            return self._workers.get(stream_id)

    def get_all_engines(self) -> list[AlarmEngine]:
        """Return a snapshot of all active engines (for dispatcher polling)."""
        with self._lock:
            return list(self._engines.values())

    def reload_alarms_for_stream(self, stream_id: int) -> None:
        """Reload alarm rules from DB into the live engine for ``stream_id``.

        Called by alarm API endpoints after CRUD operations so that rule
        changes take effect immediately without restarting the worker.
        """
        with self._lock:
            engine = self._engines.get(stream_id)
        if engine is None:
            return
        try:
            from ..db.session import SessionLocal
            from ..models.alarm import Alarm, AlarmZone

            db = SessionLocal()
            try:
                alarms = db.query(Alarm).filter(Alarm.stream_id == stream_id, Alarm.is_active.is_(True)).all()
                zones = db.query(AlarmZone).filter(AlarmZone.stream_id == stream_id).all()
                zones_by_id = {z.id: z.polygon for z in zones if z.polygon}
                engine.load_rules(alarms, zones_by_id)
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to reload alarms for stream %d", stream_id)

    def list_stats(self) -> list[dict[str, Any]]:
        with self._lock:
            return [w.get_stats() for w in self._workers.values()]

    def get_snapshot_frame(self, stream_id: int) -> Any | None:
        """Return the last decoded frame from the running worker, or None."""
        with self._lock:
            worker = self._workers.get(stream_id)
        if worker is None:
            return None
        return worker.get_snapshot_frame()

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

    def _build_engine(self, stream_id: int) -> AlarmEngine:
        """Create and populate an AlarmEngine for ``stream_id`` from DB."""
        engine = AlarmEngine(stream_id)
        try:
            from ..db.session import SessionLocal
            from ..models.alarm import Alarm, AlarmZone

            db = SessionLocal()
            try:
                alarms = db.query(Alarm).filter(Alarm.stream_id == stream_id, Alarm.is_active.is_(True)).all()
                zones = db.query(AlarmZone).filter(AlarmZone.stream_id == stream_id).all()
                zones_by_id = {z.id: z.polygon for z in zones if z.polygon}
                engine.load_rules(alarms, zones_by_id)
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to load alarms for stream %d engine", stream_id)
        return engine

    def _stop_and_remove(self, stream_id: int) -> None:
        """Stop and remove worker; caller must hold ``_lock``."""
        model_batch_coordinator.unregister_stream(stream_id)
        worker = self._workers.pop(stream_id, None)
        if worker:
            worker.stop()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
inference_worker_manager = InferenceWorkerManager()
