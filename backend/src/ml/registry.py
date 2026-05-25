"""
Model Registry - Central management for ML models.

Provides model discovery, caching, and lifecycle management.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import BaseInferenceEngine
from .base import HardwareAccelerator
from .base import ModelConfig
from .base import ModelType

logger = logging.getLogger(__name__)

# Supported YOLO task types.
TASK_TYPE_DETECT = "detect"
TASK_TYPE_POSE = "pose"
TASK_TYPE_SEGMENT = "segment"


@dataclass
class ModelInfo:
    """Information about a registered model."""

    name: str
    model_type: ModelType
    path: str
    task_type: str = TASK_TYPE_DETECT  # detect | pose | segment
    version: str = "1.0.0"
    description: str = ""
    supported_accelerators: list[HardwareAccelerator] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    input_size: tuple = (640, 640)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    file_hash: str | None = None
    is_downloaded: bool = True
    is_enabled: bool = False
    download_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model_type": self.model_type.value,
            "path": self.path,
            "task_type": self.task_type,
            "version": self.version,
            "description": self.description,
            "supported_accelerators": [a.value for a in self.supported_accelerators],
            "classes": self.classes,
            "input_size": self.input_size,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "file_hash": self.file_hash,
            "is_downloaded": self.is_downloaded,
            "is_enabled": self.is_enabled,
            "download_url": self.download_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelInfo":
        return cls(
            name=data["name"],
            model_type=ModelType(data["model_type"]),
            path=data["path"],
            task_type=data.get("task_type", TASK_TYPE_DETECT),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            supported_accelerators=[HardwareAccelerator(a) for a in data.get("supported_accelerators", [])],
            classes=data.get("classes", []),
            input_size=tuple(data.get("input_size", (640, 640))),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            file_hash=data.get("file_hash"),
            is_downloaded=data.get("is_downloaded", True),
            is_enabled=data.get("is_enabled", data.get("is_downloaded", False)),
            download_url=data.get("download_url"),
        )


def _all_accelerators() -> list[HardwareAccelerator]:
    return [
        HardwareAccelerator.CPU,
        HardwareAccelerator.CUDA,
        HardwareAccelerator.TENSORRT,
        HardwareAccelerator.JETSON,
    ]


def _gpu_accelerators() -> list[HardwareAccelerator]:
    return [HardwareAccelerator.CPU, HardwareAccelerator.CUDA, HardwareAccelerator.TENSORRT]


def _make_yolo_models(family: str, version_str: str, sizes: dict[str, str]) -> dict[str, "ModelInfo"]:
    """
    Generate ModelInfo entries for a YOLO family across detect/pose/segment tasks.

    Args:
        family: Model family prefix, e.g. "yolov8", "yolo11", "yolo12"
        version_str: Semantic version string, e.g. "8.0.0"
        sizes: Mapping of size key → human description, e.g. {"n": "Nano", "s": "Small"}
    """
    models: dict[str, ModelInfo] = {}
    for size_key, size_label in sizes.items():
        accelerators = _all_accelerators() if size_key in ("n", "s") else _gpu_accelerators()
        for task_type, task_label, suffix in [
            (TASK_TYPE_DETECT, "Object Detection", ""),
            (TASK_TYPE_POSE, "Pose Estimation", "-pose"),
            (TASK_TYPE_SEGMENT, "Segmentation", "-seg"),
        ]:
            name = f"{family}{size_key}{suffix}"
            models[name] = ModelInfo(
                name=name,
                model_type=ModelType.YOLO,
                path=f"{name}.pt",
                task_type=task_type,
                version=version_str,
                description=f"{family.upper()}{size_key.upper()} {size_label} — {task_label}",
                supported_accelerators=accelerators,
                input_size=(640, 640),
            )
    return models


class ModelRegistry:
    """
    Central registry for managing ML models.

    Features:
    - Model discovery and registration
    - Model caching and versioning
    - Automatic model availability via ultralytics auto-download
    - Model optimization for different accelerators

    Design:
    - Single source of truth for available models; consumers must call
      ``ensure_model_available(name)`` before running inference.
    - Ultralytics handles disk caching transparently; ``is_downloaded``
      reflects whether the file is cached locally.
    """

    # Default models: YOLOv8, YOLO11, YOLO12 x detect / pose / segment x n / m
    DEFAULT_MODELS: dict[str, "ModelInfo"] = {
        **_make_yolo_models("yolov8", "8.0.0", {"n": "Nano", "m": "Medium", "l": "Large"}),
        **_make_yolo_models("yolo11", "11.0.0", {"n": "Nano", "m": "Medium", "l": "Large"}),
        **_make_yolo_models("yolo12", "12.0.0", {"n": "Nano", "m": "Medium"}),
    }

    def __init__(self, models_dir: str = "./models", cache_dir: str = "./.model_cache"):
        self.models_dir = Path(models_dir)
        self.cache_dir = Path(cache_dir)
        self._registry: dict[str, ModelInfo] = {}
        self._engine_classes: dict[ModelType, type[BaseInferenceEngine]] = {}

        # Create directories
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load registry state
        self._load_registry()

        # Register default models
        self._register_defaults()

        # Reconcile persisted state with real on-disk artifacts.
        self.reconcile_registry_state()

    def _get_registry_path(self) -> Path:
        return self.cache_dir / "registry.json"

    def _load_registry(self) -> None:
        """Load registry state from disk."""
        registry_path = self._get_registry_path()
        if registry_path.exists():
            try:
                with open(registry_path) as f:
                    data = json.load(f)
                    for name, model_data in data.items():
                        self._registry[name] = ModelInfo.from_dict(model_data)
                logger.info(f"Loaded {len(self._registry)} models from registry")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")

    def _save_registry(self) -> None:
        """Save registry state to disk."""
        registry_path = self._get_registry_path()
        try:
            data = {name: info.to_dict() for name, info in self._registry.items()}
            with open(registry_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def _register_defaults(self) -> None:
        """Register default models."""
        for name, info in self.DEFAULT_MODELS.items():
            if name not in self._registry:
                # Check if model file exists
                model_path = self.models_dir / info.path
                if model_path.exists():
                    info.path = str(model_path)
                    info.is_downloaded = True
                    info.is_enabled = True
                else:
                    info.is_downloaded = False
                    info.is_enabled = False
                self._registry[name] = info

    def _artifact_candidates(self, info: ModelInfo) -> list[Path]:
        """Return likely filesystem locations for a model artifact."""
        explicit_path = Path(info.path)
        model_filename = explicit_path.name if explicit_path.suffix else f"{info.name}.pt"

        candidates: list[Path] = []
        if explicit_path.is_absolute():
            candidates.append(explicit_path)
        else:
            candidates.extend(
                [
                    (self.models_dir / explicit_path).resolve(),
                    (self.models_dir / model_filename).resolve(),
                    (Path.cwd() / explicit_path).resolve(),
                    (Path.cwd() / model_filename).resolve(),
                ]
            )

        # Common backend container working directory.
        candidates.append((Path("/app") / model_filename).resolve())
        return candidates

    def _resolve_existing_artifact(self, info: ModelInfo) -> Path | None:
        """Find the first existing artifact path for a model, if any."""
        for candidate in self._artifact_candidates(info):
            if candidate.exists() and candidate.is_file():
                return candidate

        explicit_path = Path(info.path)
        model_filename = explicit_path.name if explicit_path.suffix else f"{info.name}.pt"
        cache_root = Path.home() / ".cache" / "ultralytics"
        if cache_root.exists():
            for candidate in cache_root.rglob(model_filename):
                if candidate.exists() and candidate.is_file():
                    return candidate.resolve()

        return None

    def reconcile_model_state(self, name: str) -> bool:
        """Refresh a model's downloaded/path state from filesystem truth."""
        info = self._registry.get(name)
        if info is None:
            return False

        existing = self._resolve_existing_artifact(info)
        new_downloaded = existing is not None
        new_path = str(existing) if existing is not None else info.path

        changed = info.is_downloaded != new_downloaded or info.path != new_path
        if changed:
            info.is_downloaded = new_downloaded
            info.path = new_path

            # Keep enabled state meaningful when artifact is absent.
            if not new_downloaded:
                info.is_enabled = False

            self._registry[name] = info
        return changed

    def reconcile_registry_state(self) -> None:
        """Refresh registry downloaded/path state based on current filesystem."""
        changed = False
        for name in list(self._registry.keys()):
            if self.reconcile_model_state(name):
                changed = True

        if changed:
            self._save_registry()

    def register_engine(self, model_type: ModelType, engine_class: type[BaseInferenceEngine]) -> None:
        """Register an inference engine class for a model type."""
        self._engine_classes[model_type] = engine_class
        logger.info(f"Registered engine {engine_class.__name__} for {model_type.value}")

    def register_model(self, model_info: ModelInfo) -> None:
        """Register a new model."""
        self._registry[model_info.name] = model_info
        self._save_registry()
        logger.info(f"Registered model: {model_info.name}")

    def unregister_model(self, name: str) -> bool:
        """Unregister a model."""
        if name in self._registry:
            del self._registry[name]
            self._save_registry()
            logger.info(f"Unregistered model: {name}")
            return True
        return False

    def get_model(self, name: str) -> ModelInfo | None:
        """Get model info by name."""
        self.reconcile_model_state(name)
        return self._registry.get(name)

    def list_models(
        self,
        model_type: ModelType | None = None,
        task_type: str | None = None,
        accelerator: HardwareAccelerator | None = None,
        downloaded_only: bool = False,
    ) -> list[ModelInfo]:
        """
        List registered models with optional filtering.

        Args:
            model_type: Filter by model type (YOLO, ONNX, …)
            task_type: Filter by task (detect, pose, segment)
            accelerator: Filter by supported accelerator
            downloaded_only: Only show models whose file is available on disk
        """
        models = list(self._registry.values())

        if model_type:
            models = [m for m in models if m.model_type == model_type]

        if task_type:
            models = [m for m in models if m.task_type == task_type]

        if accelerator:
            models = [m for m in models if accelerator in m.supported_accelerators]

        if downloaded_only:
            models = [m for m in models if m.is_downloaded]

        return models

    def download_model(self, name: str, force: bool = False) -> bool:
        """
        Download a model from its URL.

        Args:
            name: Model name
            force: Force re-download even if exists

        Returns:
            True if download successful
        """
        model_info = self._registry.get(name)
        if not model_info:
            logger.error(f"Model {name} not found in registry")
            return False

        if model_info.is_downloaded and not force:
            if not model_info.is_enabled:
                model_info.is_enabled = True
                self._save_registry()
            logger.info(f"Model {name} already downloaded")
            return True

        if not model_info.download_url:
            logger.error(f"No download URL for model {name}")
            return False

        try:
            import urllib.request

            target_path = self.models_dir / model_info.path
            logger.info(f"Downloading {name} from {model_info.download_url}")

            urllib.request.urlretrieve(model_info.download_url, target_path)

            # Verify hash if provided
            if model_info.file_hash:
                actual_hash = self._compute_file_hash(target_path)
                if actual_hash != model_info.file_hash:
                    logger.error(f"Hash mismatch for {name}")
                    os.remove(target_path)
                    return False

            model_info.is_downloaded = True
            model_info.is_enabled = True
            model_info.path = str(target_path)
            self._save_registry()

            logger.info(f"Successfully downloaded {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to download {name}: {e}")
            return False

    def _compute_file_hash(self, path: Path) -> str:
        """Compute SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def ensure_model_available(self, name: str) -> bool:
        """
        Ensure a model is available for inference.

        For Ultralytics YOLO models the library auto-downloads the weights on
        the first call to ``YOLO(name)`` and stores them in its own cache.
        This method triggers that process so the next inference call is instant.

        Returns:
            True if the model is ready; False if it could not be prepared.
        """
        model_info = self._registry.get(name)
        if not model_info:
            logger.error("Model '%s' not found in registry", name)
            return False

        # If already confirmed available, skip
        if model_info.is_downloaded:
            if not model_info.is_enabled:
                model_info.is_enabled = True
                self._save_registry()
            return True

        if model_info.model_type == ModelType.YOLO:
            try:
                from ultralytics import YOLO

                logger.info("Triggering ultralytics auto-download for '%s'", name)
                # YOLO(name) downloads weights once; raises on failure
                YOLO(name)
                model_info.is_downloaded = True
                model_info.is_enabled = True
                self._save_registry()
                logger.info("Model '%s' is now available", name)
                return True
            except Exception as exc:
                logger.error("Failed to ensure model '%s': %s", name, exc)
                return False

        # For non-YOLO models fall back to explicit URL download
        return self.download_model(name)

    def create_engine(
        self, model_name: str, accelerator: HardwareAccelerator | None = None, **config_overrides
    ) -> BaseInferenceEngine | None:
        """
        Create an inference engine for a model.

        Args:
            model_name: Name of the registered model
            accelerator: Preferred hardware accelerator
            **config_overrides: Override default model config

        Returns:
            Configured inference engine instance
        """
        model_info = self._registry.get(model_name)
        if not model_info:
            logger.error(f"Model {model_name} not found")
            return None

        if not model_info.is_downloaded:
            logger.error(f"Model {model_name} not downloaded")
            return None

        engine_class = self._engine_classes.get(model_info.model_type)
        if not engine_class:
            logger.error(f"No engine registered for {model_info.model_type}")
            return None

        # Build config
        config = ModelConfig(
            model_path=model_info.path,
            model_type=model_info.model_type,
            model_name=model_info.name,
            input_size=model_info.input_size,
            preferred_accelerator=accelerator or HardwareAccelerator.CPU,
            **config_overrides,
        )

        return engine_class(config)

    def discover_models(self, directory: str | None = None) -> list[ModelInfo]:
        """
        Discover models in a directory.

        Args:
            directory: Directory to scan (defaults to models_dir)

        Returns:
            List of discovered models
        """
        scan_dir = Path(directory) if directory else self.models_dir
        discovered = []

        # Supported extensions by model type
        extensions = {
            ".pt": ModelType.YOLO,
            ".onnx": ModelType.ONNX,
            ".engine": ModelType.TENSORRT,
            ".trt": ModelType.TENSORRT,
        }

        for file_path in scan_dir.glob("**/*"):
            if file_path.suffix in extensions:
                model_type = extensions[file_path.suffix]
                name = file_path.stem

                if name not in self._registry:
                    info = ModelInfo(
                        name=name,
                        model_type=model_type,
                        path=str(file_path),
                        is_downloaded=True,
                    )
                    discovered.append(info)
                    self.register_model(info)

        return discovered


# ---------------------------------------------------------------------------
# Module-level singleton — import and use model_registry throughout the app
# ---------------------------------------------------------------------------
model_registry = ModelRegistry()  # ---------------------------------------------------------------------------
# Module-level singleton — import and use model_registry throughout the app
# ---------------------------------------------------------------------------
model_registry = ModelRegistry()
