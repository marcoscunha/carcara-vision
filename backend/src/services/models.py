"""
Model service — thin delegation layer over ModelRegistry.

All consumers should use these functions rather than addressing the registry
directly, keeping the import surface small and testable.
"""

from typing import Any

from ..ml.registry import ModelInfo
from ..ml.registry import model_registry


def get_available_models(task_type: str | None = None) -> list[dict[str, Any]]:
    """
    Return all registered models, optionally filtered by task type.

    Each entry is a plain dict so it can be serialised directly to JSON.
    """
    models: list[ModelInfo] = model_registry.list_models(task_type=task_type)
    return [_model_to_dict(m) for m in sorted(models, key=lambda m: m.name)]


def get_model_by_name(name: str) -> dict[str, Any]:
    """
    Return a single model by name.

    Raises:
        ValueError: if the model is not registered.
    """
    info = model_registry.get_model(name)
    if info is None:
        raise ValueError(f"Model '{name}' not found")
    return _model_to_dict(info)


def ensure_model_available(name: str) -> bool:
    """Trigger ultralytics auto-download for YOLO models if needed."""
    return model_registry.ensure_model_available(name)


def _model_to_dict(info: ModelInfo) -> dict[str, Any]:
    """Serialise a ModelInfo to the public API shape."""
    return {
        "name": info.name,
        "description": info.description,
        "model_type": info.model_type.value,
        "task_type": info.task_type,
        "version": info.version,
        "is_available": info.is_downloaded,
        "supported_accelerators": [a.value for a in info.supported_accelerators],
        "input_size": list(info.input_size),
    }
