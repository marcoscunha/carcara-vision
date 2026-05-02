"""
Inference Worker — continuous per-stream AI background task.

Each active stream with detection enabled gets one ``InferenceWorker``.
The worker:
  1. Opens the stream's MediaMTX RTSP URL with OpenCV.
  2. Reads every source frame in a non-blocking loop at full source fps.
  3. Runs the SDK pipeline throttled to ``max_inference_fps`` (inference cadence)
      and caches the latest detections for reuse on non-inferred frames.
      The pipeline is loaded once and reused for the worker lifetime.
  4. Overlays the cached detections on every frame and pushes all frames to
      ``AnnotatedStreamWriter`` at ``output_fps`` — the annotated stream is
      always smooth regardless of inference speed.
  5. Broadcasts detection JSON to all subscribed WebSocket clients.
  6. Evaluates alarm rules and emits alarm events when conditions match.

Design patterns used:
  - Strategy: task_type selects the inference strategy at construction time.
  - Observer: set of WebSocket queues subscribes to detection events.
  - Thread isolation: the blocking OpenCV capture and FFmpeg push run in a
    dedicated ``threading.Thread``; asyncio queues bridge to the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

import cv2

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

from ..core.config import settings
from ..ml.annotator import FrameAnnotator
from ..ml.base import HardwareAccelerator
from ..ml.registry import TASK_TYPE_DETECT
from ..ml.registry import TASK_TYPE_POSE
from ..ml.registry import TASK_TYPE_SEGMENT
from ..ml.sdk import BaseTaskPipeline
from ..ml.sdk import Detection
from ..ml.sdk import DetectionResult
from ..ml.sdk import pipeline as build_sdk_pipeline
from ..ml.sdk.exceptions import ModelNotFoundError
from ..services.annotated_stream_writer import AnnotatedStreamWriter

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Immutable configuration for an InferenceWorker."""

    stream_id: int
    stream_name: str
    rtsp_url: str  # MediaMTX RTSP input (raw stream)
    mediamtx_rtsp_base: str  # e.g. "rtsp://mediamtx:8554"
    model_name: str
    task_type: str = TASK_TYPE_DETECT
    runtime: str = "auto"
    dtype: str = "auto"
    providers: list[str] | None = None
    confidence: float = 0.5
    classes_filter: list[int] | None = None
    accelerator: str = "cpu"
    width: int = 640
    height: int = 360
    max_inference_fps: int = 10  # cap inference to reduce CPU pressure
    output_fps: int = 25  # annotated stream frame-rate (decoupled from inference rate)
    encoder_mode: str = "x264"  # resolved hardware encoder: nvenc | jetson | v4l2 | x264


@dataclass
class DetectionEvent:
    """Payload broadcast to WebSocket subscribers after each inference cycle."""

    stream_id: int
    stream_name: str
    timestamp: float
    task_type: str
    model_name: str
    detections: list[dict[str, Any]]
    inference_time_ms: float
    fps: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_id": self.stream_id,
            "stream_name": self.stream_name,
            "timestamp": self.timestamp,
            "task_type": self.task_type,
            "model_name": self.model_name,
            "detections": self.detections,
            "inference_time_ms": round(self.inference_time_ms, 2),
            "fps": round(self.fps, 2),
        }


class InferenceWorker:
    """
    Per-stream inference worker.

    Lifecycle::

        worker = InferenceWorker(config)
        worker.start()
        # ... stream active ...
        worker.stop()

    Detection events are delivered to registered subscriber queues:
        worker.add_subscriber(asyncio.Queue())

    Alarm callbacks receive the same ``DetectionEvent``:
        worker.set_alarm_callback(fn)
    """

    def __init__(self, config: WorkerConfig) -> None:
        self._config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Persistent pipeline + backing engine handle (for track/pose/segment parsing)
        self._pipeline: BaseTaskPipeline | None = None
        self._engine: Any | None = None

        # Annotated stream writer
        self._annotated_writer: AnnotatedStreamWriter | None = None

        # Last known detections — reused for every frame between inference cycles
        self._last_detections: list[dict[str, Any]] = []

        # Observer: set of asyncio.Queue for WebSocket subscribers
        self._subscribers: set[asyncio.Queue] = set()
        self._subscribers_lock = threading.Lock()

        # Alarm callback (called with DetectionEvent)
        self._alarm_callback: Callable[[DetectionEvent], None] | None = None

        # Rolling inference stats
        self._frame_count: int = 0
        self._total_inference_ms: float = 0.0
        self._event_intervals_ms: deque[float] = deque(maxlen=120)
        self._last_event_time: float | None = None
        self._read_failures_total: int = 0
        self._max_consecutive_read_failures: int = 0
        self._reconnect_count: int = 0
        self._dropped_events_total: int = 0
        self._missed_slots_total: int = 0

        # Rolling per-stage timings (milliseconds)
        self._stage_timings_ms: dict[str, deque[float]] = {
            "read": deque(maxlen=240),
            "inference_total": deque(maxlen=240),
            "inference_engine": deque(maxlen=240),
            "annotate": deque(maxlen=240),
            "resize": deque(maxlen=240),
            "publish_annotated": deque(maxlen=240),
            "broadcast": deque(maxlen=240),
            "alarm_callback": deque(maxlen=240),
            "loop_total": deque(maxlen=240),
        }

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the background inference thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Worker for stream %d already running", self._config.stream_id)
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"inference-worker-{self._config.stream_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "InferenceWorker started for stream '%s' (task=%s)", self._config.stream_name, self._config.task_type
        )

    def stop(self) -> None:
        """Signal the worker to stop and wait for the thread to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._annotated_writer:
            self._annotated_writer.stop()
            self._annotated_writer = None
        if self._pipeline:
            self._pipeline.close()
            self._pipeline = None
            self._engine = None
        logger.info("InferenceWorker stopped for stream '%s'", self._config.stream_name)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ #
    # Observer management
    # ------------------------------------------------------------------ #

    def add_subscriber(self, queue: asyncio.Queue) -> None:
        with self._subscribers_lock:
            self._subscribers.add(queue)

    def remove_subscriber(self, queue: asyncio.Queue) -> None:
        with self._subscribers_lock:
            self._subscribers.discard(queue)

    def set_alarm_callback(self, callback: Callable[[DetectionEvent], None] | None) -> None:
        self._alarm_callback = callback

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def get_stats(self) -> dict[str, Any]:
        throughput_fps = 0.0
        avg_ms = 0.0
        if self._frame_count > 0:
            avg_ms = self._total_inference_ms / self._frame_count
            throughput_fps = 1000 / avg_ms if avg_ms > 0 else 0.0

        intervals = list(self._event_intervals_ms)
        avg_event_interval_ms = sum(intervals) / len(intervals) if intervals else 0.0
        max_event_interval_ms = max(intervals) if intervals else 0.0
        min_event_interval_ms = min(intervals) if intervals else 0.0

        cadence_fps = 1000 / avg_event_interval_ms if avg_event_interval_ms > 0 else throughput_fps
        fps = min(cadence_fps, float(self._config.max_inference_fps))

        stage_timings = self._stage_timing_snapshot()

        return {
            "stream_id": self._config.stream_id,
            "frames_processed": self._frame_count,
            "avg_inference_ms": round(avg_ms, 2),
            "fps": round(fps, 2),
            "inference_throughput_fps": round(throughput_fps, 2),
            "target_inference_fps": self._config.max_inference_fps,
            "output_fps": self._config.output_fps,
            "avg_event_interval_ms": round(avg_event_interval_ms, 2),
            "min_event_interval_ms": round(min_event_interval_ms, 2),
            "max_event_interval_ms": round(max_event_interval_ms, 2),
            "read_failures_total": self._read_failures_total,
            "max_consecutive_read_failures": self._max_consecutive_read_failures,
            "reconnect_count": self._reconnect_count,
            "missed_slots_total": self._missed_slots_total,
            "dropped_events_total": self._dropped_events_total,
            "stage_timings_ms": stage_timings,
            "model": self._config.model_name,
            "accelerator": self._config.accelerator,
            "runtime": self._config.runtime,
            "dtype": self._config.dtype,
            "providers": self._config.providers or [],
            "task_type": self._config.task_type,
            "running": self.is_running(),
        }

    # ------------------------------------------------------------------ #
    # Private: main loop (runs in dedicated thread)
    # ------------------------------------------------------------------ #

    def _run_loop(self) -> None:
        """Entry point for the worker thread."""
        try:
            self._pipeline = self._build_pipeline()
            self._engine = getattr(self._pipeline, "_engine", None)
            self._annotated_writer = AnnotatedStreamWriter(
                stream_name=self._config.stream_name,
                mediamtx_rtsp_url=self._config.mediamtx_rtsp_base,
                width=self._config.width,
                height=self._config.height,
                fps=self._config.output_fps,
                encoder_mode=self._config.encoder_mode,
            )
        except Exception as exc:
            logger.error("Worker init failed for stream %d: %s", self._config.stream_id, exc)
            return

        min_frame_interval = 1.0 / max(self._config.max_inference_fps, 1)
        logger.info("Connecting to RTSP source: %s", self._config.rtsp_url)

        while not self._stop_event.is_set():
            cap = self._open_capture()
            if cap is None:
                self._reconnect_count += 1
                if not self._stop_event.wait(timeout=3.0):
                    continue
                break

            try:
                self._capture_loop(cap, min_frame_interval)
            finally:
                cap.release()

            if self._stop_event.is_set():
                break
            # Brief pause before reconnect
            self._reconnect_count += 1
            self._stop_event.wait(timeout=2.0)

    def _open_capture(self) -> cv2.VideoCapture | None:
        """Open OpenCV VideoCapture; return None on failure."""
        cap = cv2.VideoCapture(self._config.rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            logger.warning("Could not open RTSP source '%s', will retry", self._config.rtsp_url)
            return None
        return cap

    def _capture_loop(self, cap: cv2.VideoCapture, min_interval: float) -> None:
        """Frame read → infer → annotate → broadcast loop."""
        consecutive_read_failures = 0
        max_consecutive_read_failures = 25
        next_inference_at = time.monotonic()

        while not self._stop_event.is_set():
            loop_started = time.perf_counter()
            read_started = time.perf_counter()
            ret, frame = cap.read()
            read_ms = (time.perf_counter() - read_started) * 1000.0
            if not ret or frame is None:
                consecutive_read_failures += 1
                self._read_failures_total += 1
                if consecutive_read_failures > self._max_consecutive_read_failures:
                    self._max_consecutive_read_failures = consecutive_read_failures
                if consecutive_read_failures >= max_consecutive_read_failures:
                    logger.debug(
                        "Frame read failed repeatedly for stream %d (%d failures)",
                        self._config.stream_id,
                        consecutive_read_failures,
                    )
                    break
                self._stop_event.wait(timeout=0.04)
                continue

            consecutive_read_failures = 0
            self._record_stage_timing("read", read_ms)

            now = time.monotonic()
            run_inference = now >= next_inference_at

            try:
                if run_inference:
                    inference_started = time.perf_counter()
                    detections, inference_ms = self._run_inference(frame)
                    inference_total_ms = (time.perf_counter() - inference_started) * 1000.0
                    self._last_detections = detections
                    self._record_stage_timing("inference_total", inference_total_ms)
                    self._record_stage_timing("inference_engine", inference_ms)
                    self._frame_count += 1
                    self._total_inference_ms += inference_ms
                    # Advance the inference cadence clock
                    next_inference_at += min_interval
                    if time.monotonic() > next_inference_at:
                        missed_slots = int((time.monotonic() - next_inference_at) / min_interval) + 1
                        self._missed_slots_total += missed_slots
                        next_inference_at += missed_slots * min_interval
                else:
                    inference_ms = 0.0
            except Exception as exc:
                logger.error("Inference error for stream %d: %s", self._config.stream_id, exc)
                next_inference_at = time.monotonic() + min_interval
                inference_ms = 0.0

            # Annotate every frame with the last known detections (keeps stream fluent).
            # When there are no active detections skip frame.copy() — nothing to draw.
            annotated = None
            annotate_ms = 0.0
            resize_ms = 0.0
            if self._annotated_writer:
                needs_resize = frame.shape[1] != self._config.width or frame.shape[0] != self._config.height
                if self._last_detections:
                    annotate_started = time.perf_counter()
                    annotated = frame.copy()
                    self._annotate(annotated, self._last_detections)
                    annotate_ms = (time.perf_counter() - annotate_started) * 1000.0
                else:
                    # No detections — use the raw frame (no copy, no draw)
                    annotated = frame

                if needs_resize:
                    resize_started = time.perf_counter()
                    annotated = cv2.resize(
                        annotated,
                        (self._config.width, self._config.height),
                        interpolation=cv2.INTER_LINEAR,
                    )
                    resize_ms = (time.perf_counter() - resize_started) * 1000.0

            self._record_stage_timing("annotate", annotate_ms)
            self._record_stage_timing("resize", resize_ms)

            # Push annotated frame to MediaMTX (every frame, not just inferred ones)
            publish_ms = 0.0
            if self._annotated_writer and annotated is not None:
                try:
                    publish_started = time.perf_counter()
                    self._annotated_writer.push_frame(annotated)
                    publish_ms = (time.perf_counter() - publish_started) * 1000.0
                except Exception as exc:
                    logger.warning(
                        "Annotated stream publish disabled for stream %d: %s",
                        self._config.stream_id,
                        exc,
                    )
                    try:
                        self._annotated_writer.stop()
                    except Exception:
                        pass
                    self._annotated_writer = None
            self._record_stage_timing("publish_annotated", publish_ms)

            # Broadcast detection events and fire alarm callbacks only on inference frames.
            broadcast_ms = 0.0
            alarm_ms = 0.0
            if run_inference and inference_ms > 0.0:
                event_fps = min(
                    1000 / inference_ms if inference_ms > 0 else 0.0,
                    float(self._config.max_inference_fps),
                )
                event = DetectionEvent(
                    stream_id=self._config.stream_id,
                    stream_name=self._config.stream_name,
                    timestamp=time.time(),
                    task_type=self._config.task_type,
                    model_name=self._config.model_name,
                    detections=self._last_detections,
                    inference_time_ms=inference_ms,
                    fps=event_fps,
                )

                event_tick = time.monotonic()
                if self._last_event_time is not None:
                    self._event_intervals_ms.append((event_tick - self._last_event_time) * 1000.0)
                self._last_event_time = event_tick

                broadcast_started = time.perf_counter()
                dropped_events = self._broadcast(event)
                broadcast_ms = (time.perf_counter() - broadcast_started) * 1000.0
                self._dropped_events_total += dropped_events

                if self._alarm_callback:
                    try:
                        alarm_started = time.perf_counter()
                        self._alarm_callback(event)
                        alarm_ms = (time.perf_counter() - alarm_started) * 1000.0
                    except Exception as exc:
                        logger.error("Alarm callback error for stream %d: %s", self._config.stream_id, exc)

            self._record_stage_timing("broadcast", broadcast_ms)
            self._record_stage_timing("alarm_callback", alarm_ms)

            loop_total_ms = (time.perf_counter() - loop_started) * 1000.0
            self._record_stage_timing("loop_total", loop_total_ms)

    # ------------------------------------------------------------------ #
    # Inference strategy
    # ------------------------------------------------------------------ #

    def _run_inference(self, frame: np.ndarray) -> tuple[list[dict[str, Any]], float]:
        """
        Run inference and return (detections, inference_time_ms).

        Selects the right engine call based on task_type.
        """
        assert self._pipeline is not None

        if self._config.task_type == TASK_TYPE_POSE and self._engine is not None:
            result = self._engine.infer(frame, classes=self._config.classes_filter)
            detections = self._parse_pose_result(result)
            return detections, result.inference_time_ms

        if self._config.task_type == TASK_TYPE_SEGMENT and self._engine is not None:
            result = self._engine.infer(frame, classes=self._config.classes_filter)
            detections = self._parse_segment_result(result)
            return detections, result.inference_time_ms

        # Default: TASK_TYPE_DETECT (prefer engine tracking if available).
        if self._engine is not None and hasattr(self._engine, "track"):
            result = self._engine.track(frame, persist=True)
            return result.detections, result.inference_time_ms

        result: DetectionResult = self._pipeline(
            frame,
            classes=self._config.classes_filter,
            confidence=self._config.confidence,
        )
        detections = [self._sdk_detection_to_legacy(det) for det in result.detections]
        return detections, result.latency_ms

    @staticmethod
    def _sdk_detection_to_legacy(det: Detection) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "bbox": det.bbox.to_list(),
            "confidence": det.score,
            "class_name": det.label,
            "class_id": det.class_id,
        }
        if det.track_id is not None:
            payload["track_id"] = det.track_id
        if det.keypoints is not None:
            payload["keypoints"] = det.keypoints
        if det.mask is not None:
            payload["mask"] = det.mask
        if det.extra:
            payload.update(det.extra)
        return payload

    @staticmethod
    def _parse_pose_result(result: Any) -> list[dict[str, Any]]:
        """Extract keypoints from a raw YOLOEngine InferenceResult."""
        detections = list(result.detections)
        raw = result.raw_output
        if raw is None:
            return detections

        try:
            yolo_result = raw
            if not hasattr(yolo_result, "keypoints") or yolo_result.keypoints is None:
                return detections
            kpts_data = yolo_result.keypoints.data.cpu().numpy()  # (N, 17, 3)
            for i, det in enumerate(detections):
                if i < len(kpts_data):
                    det["keypoints"] = kpts_data[i].tolist()
        except Exception as exc:
            logger.debug("Could not parse keypoints: %s", exc)
        return detections

    @staticmethod
    def _parse_segment_result(result: Any) -> list[dict[str, Any]]:
        """Extract mask polygons from a raw YOLOEngine InferenceResult."""
        detections = list(result.detections)
        raw = result.raw_output
        if raw is None:
            return detections

        try:
            yolo_result = raw
            if not hasattr(yolo_result, "masks") or yolo_result.masks is None:
                return detections
            # xy is a list of (N_pts, 2) tensors
            for _i, (det, xy) in enumerate(zip(detections, yolo_result.masks.xy, strict=False)):
                det["mask_polygon"] = xy.tolist()
        except Exception as exc:
            logger.debug("Could not parse masks: %s", exc)
        return detections

    def _annotate(self, frame: np.ndarray, detections: list[dict[str, Any]]) -> None:
        """Dispatch to the correct FrameAnnotator method based on task_type."""
        if self._config.task_type == TASK_TYPE_POSE:
            FrameAnnotator.draw_pose(frame, detections)
        elif self._config.task_type == TASK_TYPE_SEGMENT:
            FrameAnnotator.draw_segmentation(frame, detections)
        else:
            FrameAnnotator.draw_detections(frame, detections)

    # ------------------------------------------------------------------ #
    # Observer broadcast
    # ------------------------------------------------------------------ #

    def _broadcast(self, event: DetectionEvent) -> int:
        """Put the event into every registered subscriber queue."""
        dropped = 0
        with self._subscribers_lock:
            if not self._subscribers:
                return dropped

            payload = event.to_dict()
            dead: set[asyncio.Queue] = set()
            for queue in self._subscribers:
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    dropped += 1  # slow consumer — drop frame
                except Exception:
                    dead.add(queue)
            self._subscribers -= dead
        return dropped

    def _record_stage_timing(self, stage: str, value_ms: float) -> None:
        timings = self._stage_timings_ms.get(stage)
        if timings is not None:
            timings.append(value_ms)

    def _stage_timing_snapshot(self) -> dict[str, dict[str, float]]:
        snapshot: dict[str, dict[str, float]] = {}
        for stage, samples in self._stage_timings_ms.items():
            values = list(samples)
            if not values:
                snapshot[stage] = {
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "last": 0.0,
                    "p50": 0.0,
                    "p95": 0.0,
                    "p99": 0.0,
                }
                continue

            snapshot[stage] = {
                "avg": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "last": round(values[-1], 2),
                "p50": round(self._percentile(values, 50), 2),
                "p95": round(self._percentile(values, 95), 2),
                "p99": round(self._percentile(values, 99), 2),
            }
        return snapshot

    @staticmethod
    def _percentile(values: list[float], percentile: float) -> float:
        if not values:
            return 0.0
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return sorted_values[0]

        rank = (len(sorted_values) - 1) * (percentile / 100.0)
        low = int(rank)
        high = min(low + 1, len(sorted_values) - 1)
        fraction = rank - low
        return sorted_values[low] * (1.0 - fraction) + sorted_values[high] * fraction

    # ------------------------------------------------------------------ #
    # Builder helpers
    # ------------------------------------------------------------------ #

    def _build_pipeline(self) -> BaseTaskPipeline:
        """Build and warm-up the SDK pipeline for this worker."""

        task_map = {
            TASK_TYPE_DETECT: "object-detection",
            TASK_TYPE_POSE: "pose-estimation",
            TASK_TYPE_SEGMENT: "instance-segmentation",
        }
        task = task_map.get(self._config.task_type, "object-detection")

        accelerator = HardwareAccelerator.CPU
        try:
            accelerator = HardwareAccelerator(self._config.accelerator)
        except Exception:
            pass

        model_candidates = [self._config.model_name, settings.DEFAULT_MODEL, "yolov8n", "yolov8n.pt"]

        # Add stem candidates to handle names like "yolov8n.pt" -> "yolov8n".
        extra_candidates: list[str] = []
        for candidate in model_candidates:
            if not isinstance(candidate, str):
                continue
            stem, ext = os.path.splitext(candidate)
            if ext.lower() in {".pt", ".onnx", ".engine", ".trt"} and stem:
                extra_candidates.append(stem)
        model_candidates.extend(extra_candidates)

        # De-duplicate while preserving order.
        ordered_candidates: list[str] = []
        for candidate in model_candidates:
            if candidate and candidate not in ordered_candidates:
                ordered_candidates.append(candidate)

        last_error: Exception | None = None
        for candidate in ordered_candidates:
            try:
                sdk_pipe = build_sdk_pipeline(
                    task=task,
                    model=candidate,
                    device=accelerator.value,
                    runtime=self._config.runtime,
                    dtype=self._config.dtype,
                    providers=self._config.providers,
                    confidence=self._config.confidence,
                )

                info = sdk_pipe.info()
                logger.info(
                    "Loaded model '%s' (task=%s, accel=%s, runtime=%s, dtype=%s) for stream %d",
                    candidate,
                    self._config.task_type,
                    info.get("accelerator", self._config.accelerator),
                    info.get("runtime", self._config.runtime),
                    info.get("dtype", self._config.dtype),
                    self._config.stream_id,
                )
                return sdk_pipe
            except ModelNotFoundError as exc:
                last_error = exc
                logger.warning(
                    "Model candidate '%s' unavailable for stream %d; trying next fallback",
                    candidate,
                    self._config.stream_id,
                )

        raise RuntimeError(
            f"Failed to load any model candidate for stream {self._config.stream_id}: {ordered_candidates}"
        ) from last_error
