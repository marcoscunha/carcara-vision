"""
SDK pipeline facade.

``pipeline(...)`` is the single public entry point that users call.
It normalises config, resolves hardware/runtime, creates the engine, and
returns a task adapter.

Usage
-----
>>> from carcara_infer import pipeline
>>> detector = pipeline(task="object-detection", model="yolov8n.pt")
>>> result = detector(frame)

>>> # Explicit hardware controls
>>> detector = pipeline(
...     task="object-detection",
...     model="models/best.onnx",
...     device="cuda",
...     runtime="onnxruntime",
...     dtype="fp16",
... )
"""

from __future__ import annotations

import logging
from typing import Any

from ..factory import InferenceEngineFactory
from .config import PipelineConfig
from .resolver import resolve
from .tasks import BaseTaskPipeline
from .tasks import get_adapter_class

logger = logging.getLogger(__name__)


def pipeline(
    task: str,
    model: str,
    device: str = "auto",
    runtime: str = "auto",
    dtype: str = "auto",
    batch_size: int = 1,
    confidence: float = 0.5,
    iou: float = 0.45,
    max_detections: int = 100,
    warmup_iterations: int = 0,
    **options: Any,
) -> BaseTaskPipeline:
    """
    Create and return a ready-to-use task pipeline.

    Parameters
    ----------
    task:
        Task identifier.  One of ``"object-detection"``,
        ``"instance-segmentation"``, ``"pose-estimation"``,
        ``"image-text-to-text"``.
    model:
        Model name in the registry *or* a file path
        (e.g. ``"yolov8n.pt"``, ``"/opt/models/best.onnx"``).
    device:
        Target device.  ``"auto"`` lets the SDK pick the best available.
        Choices: ``auto | cpu | cuda | tensorrt | jetson``.
    runtime:
        Inference runtime.  ``"auto"`` infers from the model file.
        Choices: ``auto | yolo | onnxruntime | tensorrt | openai_vlm |
        ollama_vlm | local_vlm``.
    dtype:
        Numeric precision.  ``"auto"`` selects fp16 on CUDA/TRT, fp32 on CPU.
        Choices: ``auto | fp32 | fp16 | int8``.
    batch_size:
        Default batch size used by ``adapter.batch()``.
    confidence:
        Detection confidence threshold.
    iou:
        NMS IoU threshold.
    max_detections:
        Maximum detections per frame.
    warmup_iterations:
        Run this many warm-up passes after loading.  0 skips warmup.
    **options:
        Engine-specific keyword arguments forwarded via ``PipelineConfig.options``.

    Returns
    -------
    BaseTaskPipeline
        A task adapter whose ``__call__`` accepts a numpy frame or a list
        of frames.

    Raises
    ------
    ModelNotFoundError
        When the model cannot be located.
    DeviceUnavailableError
        When the requested device is not available.
    RuntimeNotSupportedError
        When the requested runtime package is not installed.
    """
    config = PipelineConfig(
        task=task,
        model=model,
        device=device,
        runtime=runtime,
        dtype=dtype,
        batch_size=batch_size,
        confidence=confidence,
        iou=iou,
        max_detections=max_detections,
        warmup_iterations=warmup_iterations,
        options=dict(options),
    )

    return _build_pipeline(config)


def pipeline_from_config(config: PipelineConfig) -> BaseTaskPipeline:
    """Alternative entry point when you have a PipelineConfig object."""
    return _build_pipeline(config)


# --------------------------------------------------------------------------- #
# Internal                                                                     #
# --------------------------------------------------------------------------- #


def _build_pipeline(config: PipelineConfig) -> BaseTaskPipeline:
    # 1. Resolve hardware / runtime / dtype
    plan = resolve(config)

    # 2. Build ModelConfig and create engine via existing factory
    model_config = plan.build_model_config()
    engine = InferenceEngineFactory.create(model_config, auto_select_hardware=False)

    # 3. Load weights
    engine.load()
    logger.info(
        "Pipeline ready: task=%s model=%s runtime=%s device=%s",
        config.task,
        config.model,
        plan.runtime,
        plan.accelerator.value,
    )

    # 4. Wrap in task adapter
    adapter_cls = get_adapter_class(config.task)
    adapter = adapter_cls(engine, plan)

    # 5. Optional warmup
    if config.warmup_iterations > 0:
        adapter.warmup(iterations=config.warmup_iterations)

    return adapter
