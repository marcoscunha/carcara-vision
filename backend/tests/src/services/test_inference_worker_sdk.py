from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from src.ml.base import HardwareAccelerator
from src.ml.sdk.types import BBox
from src.ml.sdk.types import Detection
from src.ml.sdk.types import DetectionResult
from src.ml.sdk.types import RuntimeInfo
from src.services.inference_worker import InferenceWorker
from src.services.inference_worker import WorkerConfig


class _FakePipeline:
    def __init__(self, result: DetectionResult):
        self._result = result
        self._engine = SimpleNamespace()
        self.calls = []

    def __call__(self, frame, **kwargs):
        self.calls.append((frame, kwargs))
        return self._result

    def info(self):
        return {
            "accelerator": "cpu",
            "runtime": "yolo",
            "dtype": "fp32",
        }

    def close(self):
        return None


def _config(task_type: str = "detect") -> WorkerConfig:
    return WorkerConfig(
        stream_id=1,
        stream_name="cam1",
        rtsp_url="rtsp://example/cam1",
        mediamtx_rtsp_base="rtsp://mediamtx:8554",
        model_name="yolov8n.pt",
        task_type=task_type,
        runtime="auto",
        dtype="auto",
        confidence=0.5,
        accelerator="cpu",
    )


def test_build_pipeline_uses_sdk_constructor(monkeypatch):
    expected = DetectionResult(
        detections=[],
        latency_ms=1.0,
        runtime_info=RuntimeInfo(runtime="yolo", device="cpu", dtype="fp32", providers=[], model_path="m.pt"),
    )
    calls = {}

    def _fake_build(**kwargs):
        calls.update(kwargs)
        return _FakePipeline(expected)

    monkeypatch.setattr("src.services.inference_worker.build_sdk_pipeline", _fake_build)

    worker = InferenceWorker(_config(task_type="detect"))
    pipe = worker._build_pipeline()

    assert pipe is not None
    assert calls["task"] == "object-detection"
    assert calls["model"] == "yolov8n.pt"
    assert calls["device"] == HardwareAccelerator.CPU.value


def test_run_inference_falls_back_to_pipeline_when_track_unavailable():
    result = DetectionResult(
        detections=[
            Detection(
                bbox=BBox(1, 2, 3, 4),
                score=0.87,
                label="person",
                class_id=0,
            )
        ],
        latency_ms=6.5,
        runtime_info=RuntimeInfo(runtime="yolo", device="cpu", dtype="fp32", providers=[], model_path="m.pt"),
    )
    worker = InferenceWorker(_config(task_type="detect"))
    pipe = _FakePipeline(result)
    # Engine without a `track` method forces the SDK call path.
    pipe._engine = SimpleNamespace(infer=lambda *_args, **_kwargs: None)
    worker._pipeline = pipe
    worker._engine = pipe._engine

    detections, inference_ms = worker._run_inference(np.zeros((10, 10, 3), dtype=np.uint8))

    assert inference_ms == 6.5
    assert detections[0]["bbox"] == [1, 2, 3, 4]
    assert detections[0]["confidence"] == 0.87
    assert detections[0]["class_name"] == "person"


def test_run_inference_uses_engine_track_when_available():
    class _TrackResult:
        detections = [{"bbox": [0, 0, 1, 1], "confidence": 0.99, "class_name": "car", "class_id": 2}]
        inference_time_ms = 4.2

    worker = InferenceWorker(_config(task_type="detect"))
    worker._pipeline = _FakePipeline(
        DetectionResult(
            detections=[],
            latency_ms=0.0,
            runtime_info=RuntimeInfo(
                runtime="yolo",
                device="cpu",
                dtype="fp32",
                providers=[],
                model_path="m.pt",
            ),
        )
    )
    worker._engine = SimpleNamespace(track=lambda frame, persist=True: _TrackResult())

    detections, inference_ms = worker._run_inference(np.zeros((10, 10, 3), dtype=np.uint8))

    assert inference_ms == 4.2
    assert detections[0]["class_name"] == "car"
