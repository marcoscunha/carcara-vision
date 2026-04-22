"""
Contract tests for ObjectDetectionPipeline.

Tests that the adapter correctly translates InferenceResult dicts into
SDK Detection/DetectionResult/DetectionBatchResult types.  No real model
or hardware is required - the engine is fully mocked.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
from src.ml.base import HardwareAccelerator
from src.ml.base import InferenceResult
from src.ml.base import ModelType
from src.ml.sdk.config import PipelineConfig
from src.ml.sdk.resolver import ResolvedPlan
from src.ml.sdk.tasks import ObjectDetectionPipeline
from src.ml.sdk.types import BBox
from src.ml.sdk.types import Detection
from src.ml.sdk.types import DetectionBatchResult
from src.ml.sdk.types import DetectionResult

# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _make_plan(confidence: float = 0.5) -> ResolvedPlan:
    """Return a minimal ResolvedPlan with a real PipelineConfig."""
    config = PipelineConfig(
        task="object-detection",
        model="yolov8n.pt",
        confidence=confidence,
    )
    return ResolvedPlan(
        config=config,
        model_path="/fake/yolov8n.pt",
        model_type=ModelType.YOLO,
        accelerator=HardwareAccelerator.CPU,
        runtime="yolo",
        dtype="fp32",
        providers=[],
        extra={},
    )


def _make_raw_result(*detections: dict) -> InferenceResult:
    """Build an InferenceResult populated with the given detection dicts."""
    result = InferenceResult(
        model_name="yolov8n",
        inference_time_ms=10.0,
        hardware_used=HardwareAccelerator.CPU,
    )
    for d in detections:
        result.detections.append(d)
    return result


def _det(bbox=(10.0, 20.0, 50.0, 80.0), score=0.9, label="person", class_id=0, track_id=None) -> dict:
    """Helper: build an engine detection dict."""
    d = {"bbox": list(bbox), "confidence": score, "class_name": label, "class_id": class_id}
    if track_id is not None:
        d["track_id"] = track_id
    return d


def _make_pipeline(confidence: float = 0.5) -> tuple[ObjectDetectionPipeline, MagicMock]:
    plan = _make_plan(confidence=confidence)
    engine = MagicMock()
    pipe = ObjectDetectionPipeline(engine=engine, plan=plan)
    return pipe, engine


# --------------------------------------------------------------------------- #
# _infer_one output schema                                                     #
# --------------------------------------------------------------------------- #


class TestObjectDetectionPipelineInferOne:
    def test_returns_detection_result_type(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        assert isinstance(result, DetectionResult)

    def test_detection_count(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det(), _det(label="car", class_id=1))

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        assert result.count == 2

    def test_bbox_coordinates_preserved(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det(bbox=(5.0, 10.0, 100.0, 200.0)))

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        bbox = result.detections[0].bbox
        assert isinstance(bbox, BBox)
        assert bbox.x1 == 5.0
        assert bbox.y1 == 10.0
        assert bbox.x2 == 100.0
        assert bbox.y2 == 200.0

    def test_detection_fields_mapped(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det(score=0.85, label="dog", class_id=3, track_id=42))

        det: Detection = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8)).detections[0]

        assert det.score == 0.85
        assert det.label == "dog"
        assert det.class_id == 3
        assert det.track_id == 42

    def test_latency_ms_is_positive(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        assert result.latency_ms >= 0

    def test_runtime_info_populated(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        assert result.runtime_info.runtime == "yolo"
        assert result.runtime_info.device == "cpu"
        assert result.runtime_info.dtype == "fp32"


# --------------------------------------------------------------------------- #
# Confidence filtering                                                         #
# --------------------------------------------------------------------------- #


class TestConfidenceFiltering:
    def test_low_confidence_detections_filtered_out(self):
        pipe, engine = _make_pipeline(confidence=0.7)
        engine.infer.return_value = _make_raw_result(
            _det(score=0.9),  # kept
            _det(score=0.5),  # filtered
            _det(score=0.7),  # kept (equal to threshold)
        )

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        assert result.count == 2
        assert all(d.score >= 0.7 for d in result.detections)

    def test_per_call_confidence_override(self):
        pipe, engine = _make_pipeline(confidence=0.5)
        engine.infer.return_value = _make_raw_result(
            _det(score=0.6),  # would pass at 0.5, filtered at 0.8
            _det(score=0.9),  # passes at 0.8
        )

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8), confidence=0.8)

        assert result.count == 1
        assert result.detections[0].score == 0.9

    def test_empty_detections_returns_empty_result(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result()

        result = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8))

        assert result.count == 0
        assert result.detections == []


# --------------------------------------------------------------------------- #
# __call__ dispatch                                                            #
# --------------------------------------------------------------------------- #


class TestCallDispatch:
    def test_single_frame_returns_detection_result(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        result = pipe(np.zeros((640, 640, 3), dtype=np.uint8))

        assert isinstance(result, DetectionResult)

    def test_list_of_frames_returns_batch_result(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        frames = [np.zeros((640, 640, 3), dtype=np.uint8) for _ in range(3)]
        result = pipe(frames)

        assert isinstance(result, DetectionBatchResult)
        assert len(result.items) == 3

    def test_tuple_of_frames_returns_batch_result(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        frames = tuple(np.zeros((640, 640, 3), dtype=np.uint8) for _ in range(2))
        result = pipe(frames)

        assert isinstance(result, DetectionBatchResult)


# --------------------------------------------------------------------------- #
# DetectionBatchResult schema                                                  #
# --------------------------------------------------------------------------- #


class TestBatchResult:
    def test_batch_result_total_latency_is_sum(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        frames = [np.zeros((640, 640, 3), dtype=np.uint8) for _ in range(4)]
        result = pipe.batch(frames)

        assert isinstance(result, DetectionBatchResult)
        assert result.total_latency_ms >= 0

    def test_batch_result_throughput_fps_is_positive(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        frames = [np.zeros((640, 640, 3), dtype=np.uint8) for _ in range(2)]
        result = pipe.batch(frames)

        assert result.throughput_fps > 0

    def test_batch_result_items_count(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        frames = [np.zeros((640, 640, 3), dtype=np.uint8) for _ in range(5)]
        result = pipe.batch(frames)

        assert len(result.items) == 5


# --------------------------------------------------------------------------- #
# to_dict contract                                                             #
# --------------------------------------------------------------------------- #


class TestToDictContract:
    def test_detection_result_to_dict_has_required_keys(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        d = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8)).to_dict()

        assert "detections" in d
        assert "latency_ms" in d
        assert "runtime_info" in d

    def test_detection_to_dict_has_bbox(self):
        pipe, engine = _make_pipeline()
        engine.infer.return_value = _make_raw_result(_det())

        det_dict = pipe._infer_one(np.zeros((640, 640, 3), dtype=np.uint8)).detections[0].to_dict()

        assert "bbox" in det_dict
        assert "score" in det_dict
        assert "label" in det_dict


# --------------------------------------------------------------------------- #
# info() and close()                                                           #
# --------------------------------------------------------------------------- #


class TestInfoAndClose:
    def test_info_contains_task_and_model(self):
        pipe, engine = _make_pipeline()
        info = pipe.info()

        assert info["task"] == "object-detection"
        assert "model" in info
        assert "runtime" in info

    def test_close_calls_engine_unload(self):
        pipe, engine = _make_pipeline()
        pipe.close()

        engine.unload.assert_called_once()
