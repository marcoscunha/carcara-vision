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
    # Pick up manually copied artifacts from the mounted models directory.
    model_registry.discover_models()
    model_registry.reconcile_registry_state()
    models: list[ModelInfo] = model_registry.list_models(task_type=task_type)
    return [_model_to_dict(m) for m in sorted(models, key=lambda m: m.name)]


def get_model_by_name(name: str) -> dict[str, Any]:
    """
    Return a single model by name.

    Raises:
        ValueError: if the model is not registered.
    """
    model_registry.reconcile_model_state(name)
    info = model_registry.get_model(name)
    if info is None:
        raise ValueError(f"Model '{name}' not found")
    return _model_to_dict(info)


def ensure_model_available(name: str) -> bool:
    """Trigger ultralytics auto-download for YOLO models if needed."""
    return model_registry.ensure_model_available(name)


def update_model_state(name: str, *, is_enabled: bool | None = None) -> dict[str, Any]:
    """
    Update mutable model state fields.

    Raises:
        ValueError: if model is not registered.
    """
    info = model_registry.get_model(name)
    if info is None:
        raise ValueError(f"Model '{name}' not found")

    if is_enabled is not None:
        info.is_enabled = bool(is_enabled)

    model_registry.register_model(info)
    return _model_to_dict(info)


def ensure_stream_models_enabled(streams: list[Any]) -> int:
    """
    Enable models currently assigned to streams.

    Returns:
        Number of models whose enabled state changed.
    """
    changed = 0
    names: set[str] = set()

    for stream in streams:
        metadata = getattr(stream, "stream_metadata", {}) or {}
        model_name = getattr(stream, "detection_model", None) or metadata.get("detection_model")
        if isinstance(model_name, str) and model_name:
            names.add(model_name)

    for name in names:
        info = model_registry.get_model(name)
        if info is None:
            continue
        if not info.is_enabled:
            info.is_enabled = True
            model_registry.register_model(info)
            changed += 1

    return changed


def remove_model_artifacts(name: str) -> dict[str, Any]:
    """
    Remove local model artifacts and mark the registry entry as not downloaded.

    The model stays in the catalog and can be downloaded again later.

    Raises:
        ValueError: if model is not registered.
    """
    info = model_registry.get_model(name)
    if info is None:
        raise ValueError(f"Model '{name}' not found")

    removed_files: list[str] = []

    # Remove the model artifact from known storage locations.
    explicit_path = Path(info.path)
    model_filename = explicit_path.name if explicit_path.suffix else f"{info.name}.pt"
    candidates = _artifact_candidates(info)

    cache_roots = [Path.home() / ".cache" / "ultralytics"]
    for root in cache_roots:
        if root.exists():
            candidates.extend(root.rglob(model_filename))

    seen: set[str] = set()
    for candidate in candidates:
        path = candidate.resolve()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists() and path.is_file():
            try:
                path.unlink()
                removed_files.append(key)
            except OSError:
                # Keep going if one artifact cannot be removed.
                continue

    info.is_downloaded = False
    info.is_enabled = False
    if not explicit_path.is_absolute():
        info.path = model_filename
    model_registry.register_model(info)

    return {
        "name": info.name,
        "removed_files": removed_files,
        "is_downloaded": info.is_downloaded,
    }


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
        is_enabled=model_path.exists(),
    )
    model_registry.register_model(model_info)
    return _model_to_dict(model_info)


def _model_to_dict(info: ModelInfo) -> dict[str, Any]:
    """Serialise a ModelInfo to the public API shape."""
    existing_candidates = [path for path in _artifact_candidates(info) if path.exists() and path.is_file()]
    if existing_candidates:
        storage_path = str(existing_candidates[0].resolve())
    elif info.path and Path(info.path).is_absolute():
        storage_path = str(Path(info.path))
    else:
        storage_path = str((Path(model_registry.models_dir) / Path(info.path)).resolve())

    return {
        "name": info.name,
        "description": info.description,
        "model_type": info.model_type.value,
        "task_type": info.task_type,
        "version": info.version,
        "is_available": info.is_downloaded,
        "is_downloaded": info.is_downloaded,
        "is_enabled": info.is_enabled,
        "storage_path": storage_path,
        "storage_root": str(Path(model_registry.models_dir).resolve()),
        "supported_accelerators": [a.value for a in info.supported_accelerators],
        "input_size": list(info.input_size),
    }


def _artifact_candidates(info: ModelInfo) -> list[Path]:
    """Return likely on-disk locations for this model artifact."""
    explicit_path = Path(info.path)
    model_filename = explicit_path.name if explicit_path.suffix else f"{info.name}.pt"

    candidates: list[Path] = []
    if explicit_path.is_absolute():
        candidates.append(explicit_path)
        candidates.append((Path(model_registry.models_dir) / model_filename).resolve())
    else:
        candidates.extend(
            [
                (Path(model_registry.models_dir) / explicit_path).resolve(),
                (Path(model_registry.models_dir) / model_filename).resolve(),
                (Path.cwd() / explicit_path).resolve(),
                (Path.cwd() / model_filename).resolve(),
            ]
        )

    # Common backend container working directory.
    candidates.append((Path("/app") / model_filename).resolve())
    return candidates
