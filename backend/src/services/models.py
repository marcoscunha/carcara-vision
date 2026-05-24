"""
Model service — thin delegation layer over ModelRegistry.

All consumers should use these functions rather than addressing the registry
directly, keeping the import surface small and testable.
"""

from pathlib import Path
from typing import Any

from ..ml.registry import ModelInfo
from ..ml.registry import model_registry
from ..ml.base import ModelType


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


def register_yolo_model(
    name: str,
    *,
    task_type: str = "detect",
    description: str = "",
    version: str = "custom",
) -> dict[str, Any]:
    """Register a custom YOLO model entry into the model registry."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Model name cannot be empty")

    valid_task_types = {"detect", "pose", "segment"}
    if task_type not in valid_task_types:
        raise ValueError(f"Invalid task_type '{task_type}'. Expected one of: detect, pose, segment")

    model_path = Path(model_registry.models_dir) / f"{normalized_name}.pt"

    model_info = ModelInfo(
        name=normalized_name,
        model_type=ModelType.YOLO,
        path=str(model_path),
        task_type=task_type,
        version=version,
        description=description or f"Custom YOLO model ({task_type})",
        is_downloaded=model_path.exists(),
    )
    model_registry.register_model(model_info)
    return _model_to_dict(model_info)


def _model_to_dict(info: ModelInfo) -> dict[str, Any]:
    """Serialise a ModelInfo to the public API shape."""
    storage_path = info.path
    if storage_path and not Path(storage_path).is_absolute():
        storage_path = str((Path(model_registry.models_dir) / storage_path).resolve())

    return {
        "name": info.name,
        "description": info.description,
        "model_type": info.model_type.value,
        "task_type": info.task_type,
        "version": info.version,
        "is_available": info.is_downloaded,
        "is_downloaded": info.is_downloaded,
        "storage_path": storage_path,
        "storage_root": str(Path(model_registry.models_dir).resolve()),
        "supported_accelerators": [a.value for a in info.supported_accelerators],
        "input_size": list(info.input_size),
    }
