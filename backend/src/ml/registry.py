"""
Model Registry - Central management for ML models.

Provides model discovery, caching, and lifecycle management.
"""

import hashlib
import json
import logging
import os
import shutil
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from urllib.parse import urlparse

from .base import BaseInferenceEngine
from .base import HardwareAccelerator
from .base import ModelConfig
from .base import ModelType

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a registered model."""
    name: str
    model_type: ModelType
    path: str
    version: str = "1.0.0"
    description: str = ""
    supported_accelerators: List[HardwareAccelerator] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    input_size: tuple = (640, 640)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    file_hash: Optional[str] = None
    is_downloaded: bool = True
    download_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "model_type": self.model_type.value,
            "path": self.path,
            "version": self.version,
            "description": self.description,
            "supported_accelerators": [a.value for a in self.supported_accelerators],
            "classes": self.classes,
            "input_size": self.input_size,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "file_hash": self.file_hash,
            "is_downloaded": self.is_downloaded,
            "download_url": self.download_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        return cls(
            name=data["name"],
            model_type=ModelType(data["model_type"]),
            path=data["path"],
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            supported_accelerators=[
                HardwareAccelerator(a) for a in data.get("supported_accelerators", [])
            ],
            classes=data.get("classes", []),
            input_size=tuple(data.get("input_size", (640, 640))),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            file_hash=data.get("file_hash"),
            is_downloaded=data.get("is_downloaded", True),
            download_url=data.get("download_url"),
        )


class ModelRegistry:
    """
    Central registry for managing ML models.

    Features:
    - Model discovery and registration
    - Model caching and versioning
    - Automatic model download from URLs
    - Model optimization for different accelerators
    """

    # Default models shipped with Carcara NVC
    DEFAULT_MODELS = {
        "yolov8n": ModelInfo(
            name="yolov8n",
            model_type=ModelType.YOLO,
            path="yolov8n.pt",
            version="8.0.0",
            description="YOLOv8 Nano - Fastest, smallest model",
            supported_accelerators=[
                HardwareAccelerator.CPU,
                HardwareAccelerator.CUDA,
                HardwareAccelerator.TENSORRT,
                HardwareAccelerator.JETSON,
            ],
            input_size=(640, 640),
        ),
        "yolov8s": ModelInfo(
            name="yolov8s",
            model_type=ModelType.YOLO,
            path="yolov8s.pt",
            version="8.0.0",
            description="YOLOv8 Small - Good balance of speed and accuracy",
            supported_accelerators=[
                HardwareAccelerator.CPU,
                HardwareAccelerator.CUDA,
                HardwareAccelerator.TENSORRT,
                HardwareAccelerator.JETSON,
            ],
            input_size=(640, 640),
        ),
        "yolov8m": ModelInfo(
            name="yolov8m",
            model_type=ModelType.YOLO,
            path="yolov8m.pt",
            version="8.0.0",
            description="YOLOv8 Medium - Higher accuracy",
            supported_accelerators=[
                HardwareAccelerator.CPU,
                HardwareAccelerator.CUDA,
                HardwareAccelerator.TENSORRT,
            ],
            input_size=(640, 640),
        ),
        "yolov8l": ModelInfo(
            name="yolov8l",
            model_type=ModelType.YOLO,
            path="yolov8l.pt",
            version="8.0.0",
            description="YOLOv8 Large - High accuracy, slower",
            supported_accelerators=[
                HardwareAccelerator.CPU,
                HardwareAccelerator.CUDA,
                HardwareAccelerator.TENSORRT,
            ],
            input_size=(640, 640),
        ),
        "yolov8x": ModelInfo(
            name="yolov8x",
            model_type=ModelType.YOLO,
            path="yolov8x.pt",
            version="8.0.0",
            description="YOLOv8 Extra Large - Maximum accuracy",
            supported_accelerators=[
                HardwareAccelerator.CPU,
                HardwareAccelerator.CUDA,
                HardwareAccelerator.TENSORRT,
            ],
            input_size=(640, 640),
        ),
    }

    def __init__(self, models_dir: str = "./models", cache_dir: str = "./.model_cache"):
        self.models_dir = Path(models_dir)
        self.cache_dir = Path(cache_dir)
        self._registry: Dict[str, ModelInfo] = {}
        self._engine_classes: Dict[ModelType, Type[BaseInferenceEngine]] = {}

        # Create directories
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load registry state
        self._load_registry()

        # Register default models
        self._register_defaults()

    def _get_registry_path(self) -> Path:
        return self.cache_dir / "registry.json"

    def _load_registry(self) -> None:
        """Load registry state from disk."""
        registry_path = self._get_registry_path()
        if registry_path.exists():
            try:
                with open(registry_path, "r") as f:
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
                else:
                    info.is_downloaded = False
                self._registry[name] = info

    def register_engine(
        self,
        model_type: ModelType,
        engine_class: Type[BaseInferenceEngine]
    ) -> None:
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

    def get_model(self, name: str) -> Optional[ModelInfo]:
        """Get model info by name."""
        return self._registry.get(name)

    def list_models(
        self,
        model_type: Optional[ModelType] = None,
        accelerator: Optional[HardwareAccelerator] = None,
        downloaded_only: bool = False
    ) -> List[ModelInfo]:
        """
        List registered models with optional filtering.

        Args:
            model_type: Filter by model type
            accelerator: Filter by supported accelerator
            downloaded_only: Only show downloaded models
        """
        models = list(self._registry.values())

        if model_type:
            models = [m for m in models if m.model_type == model_type]

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

    def create_engine(
        self,
        model_name: str,
        accelerator: Optional[HardwareAccelerator] = None,
        **config_overrides
    ) -> Optional[BaseInferenceEngine]:
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
            **config_overrides
        )

        return engine_class(config)

    def discover_models(self, directory: Optional[str] = None) -> List[ModelInfo]:
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
                        model_type = model_type,
                        path = str(file_path),
                        is_downloaded = True,
                    )
                    discovered.append(info)
                    self.register_model(info)

        return discovered
