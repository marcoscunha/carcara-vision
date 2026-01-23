# Carcara NVC - Machine Learning Module
# This module provides a unified interface for ML inference with support for:
# - Multiple model types (YOLO, VLMs, custom models)
# - Hardware acceleration (CUDA, TensorRT, Jetson, Raspberry Pi, OpenVINO)
# - Model registry and lifecycle management

from .base import BaseInferenceEngine
from .base import InferenceResult
from .base import ModelConfig
from .factory import InferenceEngineFactory
from .registry import ModelRegistry

__all__ = [
    "BaseInferenceEngine",
    "InferenceResult",
    "ModelConfig",
    "ModelRegistry",
    "InferenceEngineFactory",
]
"InferenceEngineFactory",
]
