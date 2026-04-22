"""
Carcara inference SDK - public surface.

from carcara_infer import pipeline
  or
from backend.src.ml.sdk import pipeline
"""

from .config import PipelineConfig
from .exceptions import DeviceUnavailableError
from .exceptions import InferenceInputError
from .exceptions import InferenceSDKError
from .exceptions import ModelNotFoundError
from .exceptions import ProviderInitializationError
from .exceptions import RuntimeNotSupportedError
from .pipeline import pipeline
from .pipeline import pipeline_from_config
from .resolver import ResolvedPlan
from .resolver import resolve
from .tasks import BaseTaskPipeline
from .tasks import ObjectDetectionPipeline
from .tasks import VLMPipeline
from .types import BBox
from .types import Detection
from .types import DetectionBatchResult
from .types import DetectionResult
from .types import RuntimeInfo
from .types import VLMResult

__all__ = [
    "BBox",
    "BaseTaskPipeline",
    "Detection",
    "DetectionBatchResult",
    "DetectionResult",
    "DeviceUnavailableError",
    "InferenceInputError",
    "InferenceSDKError",
    "ModelNotFoundError",
    "ObjectDetectionPipeline",
    "PipelineConfig",
    "ProviderInitializationError",
    "ResolvedPlan",
    "RuntimeInfo",
    "RuntimeNotSupportedError",
    "VLMPipeline",
    "VLMResult",
    "pipeline",
    "pipeline_from_config",
    "resolve",
]
