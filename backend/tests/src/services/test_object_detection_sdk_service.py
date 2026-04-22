from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
from src.ml.base import HardwareAccelerator
from src.ml.sdk.types import BBox
from src.ml.sdk.types import Detection
from src.ml.sdk.types import DetectionBatchResult
from src.ml.sdk.types import DetectionResult
from src.ml.sdk.types import RuntimeInfo
from src.services.object_detection import ObjectDetectionService


class FakeDetectionPipeline:
    def __init__(self):
        self._engine = SimpleNamespace(
            is_loaded=True,
            current_accelerator=HardwareAccelerator.CPU,
            config=SimpleNamespace(confidence_threshold=0.5),
            unload=MagicMock(),
        )

    def __call__(self, frame, **kwargs):
        return DetectionResult(
            detections=[
                Detection(
                    bbox=BBox(10, 20, 30, 40),
                    score=0.8,
                    label="person",
                    class_id=0,
                )
            ],
            latency_ms=12.5,
            runtime_info=RuntimeInfo(runtime="yolo", device="cpu", dtype="fp32", providers=[], model_path="m.pt"),
        )

    def batch(self, frames, **kwargs):
        item = DetectionResult(
            detections=[
                Detection(
                    bbox=BBox(1, 2, 3, 4),
                    score=0.9,
                    label="car",
                    class_id=2,
                )
            ],
            latency_ms=4.0,
            runtime_info=RuntimeInfo(runtime="yolo", device="cpu", dtype="fp32", providers=[], model_path="m.pt"),
        )
        return DetectionBatchResult(
            items=[item for _ in frames],
            total_latency_ms=4.0 * len(frames),
            throughput_fps=100.0,
            runtime_info=item.runtime_info,
        )

    def close(self):
        self._engine.unload()


def test_detect_uses_sdk_pipeline_and_returns_legacy_shape(monkeypatch):
    monkeypatch.setattr(
        "src.services.object_detection.build_pipeline",
        lambda **kwargs: FakeDetectionPipeline(),
    )

    service = ObjectDetectionService(model_name="fake.pt")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    detections = service.detect(frame)

    assert len(detections) == 1
    assert detections[0]["bbox"] == [10, 20, 30, 40]
    assert detections[0]["confidence"] == 0.8
    assert detections[0]["class_name"] == "person"
    assert detections[0]["class_id"] == 0


def test_detect_applies_roi_offset_with_sdk_output(monkeypatch):
    monkeypatch.setattr(
        "src.services.object_detection.build_pipeline",
        lambda **kwargs: FakeDetectionPipeline(),
    )

    service = ObjectDetectionService(model_name="fake.pt")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    detections = service.detect(frame, roi={"x": 5, "y": 7, "width": 50, "height": 50})

    assert detections[0]["bbox"] == [15, 27, 35, 47]


def test_detect_batch_uses_pipeline_batch_and_keeps_contract(monkeypatch):
    monkeypatch.setattr(
        "src.services.object_detection.build_pipeline",
        lambda **kwargs: FakeDetectionPipeline(),
    )

    service = ObjectDetectionService(model_name="fake.pt")
    frames = [np.zeros((32, 32, 3), dtype=np.uint8) for _ in range(3)]

    results = service.detect_batch(frames)

    assert len(results) == 3
    assert results[0][0]["bbox"] == [1, 2, 3, 4]
    assert results[0][0]["class_name"] == "car"


def test_engine_property_still_exposes_underlying_engine(monkeypatch):
    monkeypatch.setattr(
        "src.services.object_detection.build_pipeline",
        lambda **kwargs: FakeDetectionPipeline(),
    )

    service = ObjectDetectionService(model_name="fake.pt")

    assert service.engine is not None
    assert service.engine.is_loaded is True
