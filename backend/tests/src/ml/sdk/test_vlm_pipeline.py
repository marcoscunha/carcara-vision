"""
Contract tests for VLMPipeline.

Ensures prompt/kwargs passthrough and stable VLMResult schema.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
from src.ml.base import HardwareAccelerator
from src.ml.base import InferenceResult
from src.ml.base import ModelType
from src.ml.sdk.config import PipelineConfig
from src.ml.sdk.resolver import ResolvedPlan
from src.ml.sdk.tasks import VLMPipeline
from src.ml.sdk.types import VLMResult


def _make_plan() -> ResolvedPlan:
    cfg = PipelineConfig(task="image-text-to-text", model="llava", runtime="ollama_vlm")
    return ResolvedPlan(
        config=cfg,
        model_path="llava",
        model_type=ModelType.VLM,
        accelerator=HardwareAccelerator.CPU,
        runtime="ollama_vlm",
        dtype="fp32",
        providers=[],
        extra={"vlm_backend": "ollama"},
    )


def _raw(text: str, metadata: dict | None = None) -> InferenceResult:
    return InferenceResult(
        model_name="llava",
        inference_time_ms=8.0,
        hardware_used=HardwareAccelerator.CPU,
        text_response=text,
        metadata=metadata or {},
    )


def test_vlm_pipeline_returns_vlm_result():
    engine = MagicMock()
    engine.infer.return_value = _raw("a person on a bike")
    pipe = VLMPipeline(engine=engine, plan=_make_plan())

    result = pipe(np.zeros((32, 32, 3), dtype=np.uint8))

    assert isinstance(result, VLMResult)
    assert result.text == "a person on a bike"
    assert result.runtime_info.runtime == "ollama_vlm"


def test_vlm_pipeline_forwards_prompt_and_kwargs_to_engine():
    engine = MagicMock()
    engine.infer.return_value = _raw("ok")
    pipe = VLMPipeline(engine=engine, plan=_make_plan())

    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    pipe(frame, prompt="describe image", temperature=0.2)

    engine.infer.assert_called_once()
    args, kwargs = engine.infer.call_args
    assert args[0] is frame
    assert kwargs["prompt"] == "describe image"
    assert kwargs["temperature"] == 0.2


def test_vlm_pipeline_extracts_tokens_used_from_metadata():
    engine = MagicMock()
    engine.infer.return_value = _raw("result", metadata={"tokens_used": 321})
    pipe = VLMPipeline(engine=engine, plan=_make_plan())

    result = pipe(np.zeros((8, 8, 3), dtype=np.uint8))

    assert result.tokens_used == 321


def test_vlm_pipeline_uses_total_tokens_fallback():
    engine = MagicMock()
    engine.infer.return_value = _raw("result", metadata={"total_tokens": 77})
    pipe = VLMPipeline(engine=engine, plan=_make_plan())

    result = pipe(np.zeros((8, 8, 3), dtype=np.uint8))

    assert result.tokens_used == 77
