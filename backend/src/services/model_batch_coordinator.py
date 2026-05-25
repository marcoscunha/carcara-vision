"""Coordinate optional batched inference across streams that share the same model config.

Workers submit inference requests with a group key derived from model/runtime
settings. When two compatible requests are pending, one worker executes a
single batched inference call for both frames.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

import numpy as np

InferenceTuple = tuple[list[dict[str, Any]], float, float, float]
RunSingleFn = Callable[[np.ndarray], InferenceTuple]
RunBatchFn = Callable[[list[np.ndarray]], list[InferenceTuple]]


@dataclass
class _PendingRequest:
    stream_id: int
    frame: np.ndarray
    confidence: float
    classes_filter: list[int] | None
    run_single: RunSingleFn
    run_batch: RunBatchFn
    event: threading.Event
    result: InferenceTuple | None = None


class ModelBatchCoordinator:
    """Pair stream inference calls into batch-size=2 executions when possible."""

    def __init__(self, pair_wait_ms: float = 12.0) -> None:
        self._lock = threading.Lock()
        self._group_members: dict[str, set[int]] = defaultdict(set)
        self._stream_to_group: dict[int, str] = {}
        self._pending: dict[str, list[_PendingRequest]] = defaultdict(list)
        self._pair_wait_s = max(pair_wait_ms, 1.0) / 1000.0

    def register_stream(self, stream_id: int, group_key: str | None) -> None:
        if not group_key:
            return
        with self._lock:
            old_group = self._stream_to_group.get(stream_id)
            if old_group and old_group != group_key:
                self._group_members[old_group].discard(stream_id)
            self._stream_to_group[stream_id] = group_key
            self._group_members[group_key].add(stream_id)

    def unregister_stream(self, stream_id: int) -> None:
        with self._lock:
            group_key = self._stream_to_group.pop(stream_id, None)
            if not group_key:
                return
            self._group_members[group_key].discard(stream_id)
            if not self._group_members[group_key]:
                self._group_members.pop(group_key, None)

            # Remove stale pending entries for this stream.
            pending = self._pending.get(group_key, [])
            self._pending[group_key] = [p for p in pending if p.stream_id != stream_id]
            if not self._pending[group_key]:
                self._pending.pop(group_key, None)

    def infer(
        self,
        *,
        stream_id: int,
        group_key: str | None,
        frame: np.ndarray,
        confidence: float,
        classes_filter: list[int] | None,
        run_single: RunSingleFn,
        run_batch: RunBatchFn,
    ) -> InferenceTuple:
        """Run single or paired inference for this stream request."""
        if not group_key:
            return run_single(frame)

        request = _PendingRequest(
            stream_id=stream_id,
            frame=frame,
            confidence=confidence,
            classes_filter=classes_filter,
            run_single=run_single,
            run_batch=run_batch,
            event=threading.Event(),
        )

        pair: list[_PendingRequest] | None = None
        with self._lock:
            members = self._group_members.get(group_key, set())
            # Batch only when at least two streams currently share this model group.
            if len(members) < 2:
                return run_single(frame)

            self._pending[group_key].append(request)
            if len(self._pending[group_key]) >= 2:
                pair = self._pending[group_key][:2]
                del self._pending[group_key][:2]

        if pair is not None:
            self._execute_pair(pair)

        if request.event.wait(timeout=self._pair_wait_s):
            if request.result is not None:
                return request.result

        # Timeout waiting for a compatible pair: fallback to single inference.
        with self._lock:
            pending = self._pending.get(group_key, [])
            still_pending = request in pending
            if still_pending:
                pending.remove(request)

        if still_pending:
            single = run_single(frame)
            request.result = self._filter_result(single, request.confidence, request.classes_filter)
            request.event.set()

        if request.result is not None:
            return request.result
        return run_single(frame)

    def _execute_pair(self, pair: list[_PendingRequest]) -> None:
        leader = pair[0]
        try:
            batch_frames = [req.frame for req in pair]
            batch_results = leader.run_batch(batch_frames)
            if len(batch_results) != len(pair):
                raise RuntimeError("Batch inference did not return one result per frame")

            for req, raw_result in zip(pair, batch_results, strict=False):
                req.result = self._filter_result(raw_result, req.confidence, req.classes_filter)
        except Exception:
            # Degrade gracefully to independent single-frame inference for each request.
            for req in pair:
                req.result = self._filter_result(req.run_single(req.frame), req.confidence, req.classes_filter)
        finally:
            for req in pair:
                req.event.set()

    @staticmethod
    def _filter_result(
        result: InferenceTuple,
        confidence: float,
        classes_filter: list[int] | None,
    ) -> InferenceTuple:
        detections, inference_ms, preprocess_ms, postprocess_ms = result
        filtered = detections

        if classes_filter:
            allowed = set(classes_filter)
            filtered = [d for d in filtered if d.get("class_id") in allowed]

        if confidence > 0.0:
            filtered = [d for d in filtered if float(d.get("confidence", 0.0)) >= confidence]

        return filtered, inference_ms, preprocess_ms, postprocess_ms


model_batch_coordinator = ModelBatchCoordinator()
