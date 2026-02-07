"""
Inference Engine Factory - Creates appropriate engines for models and hardware.
"""

import logging

from .accelerators.detector import HardwareDetector
from .base import BaseInferenceEngine, HardwareAccelerator, ModelConfig, ModelType
from .engines.onnx import ONNXEngine
from .engines.tensorrt import TensorRTEngine
from .engines.vlm import LocalVLMEngine, OllamaVLMEngine, OpenAIVLMEngine, VLMEngine
from .engines.yolo import YOLOEngine

logger = logging.getLogger(__name__)


class InferenceEngineFactory:
    """
    Factory for creating inference engines.

    Automatically selects the best engine and hardware accelerator
    based on model type and available hardware.
    """

    # Default engine mappings
    ENGINE_MAP = {
        ModelType.YOLO: YOLOEngine,
        ModelType.ONNX: ONNXEngine,
        ModelType.TENSORRT: TensorRTEngine,
    }

    # VLM backends by name
    VLM_BACKENDS = {
        "ollama": OllamaVLMEngine,
        "openai": OpenAIVLMEngine,
        "local": LocalVLMEngine,
    }

    @classmethod
    def create(
        cls,
        config: ModelConfig,
        engine_class: type[BaseInferenceEngine] | None = None,
        auto_select_hardware: bool = True,
        **kwargs,
    ) -> BaseInferenceEngine:
        """
        Create an inference engine for the given configuration.

        Args:
            config: Model configuration
            engine_class: Specific engine class to use (optional)
            auto_select_hardware: Automatically select best hardware
            **kwargs: Additional engine arguments

        Returns:
            Configured inference engine
        """
        # Auto-select hardware if requested
        if auto_select_hardware:
            config.preferred_accelerator = HardwareDetector.get_best_accelerator(
                preferred=config.preferred_accelerator, fallbacks=config.fallback_accelerators
            )
            logger.info(f"Selected accelerator: {config.preferred_accelerator}")

        # Determine engine class
        if engine_class is None:
            engine_class = cls._select_engine_class(config)

        if engine_class is None:
            raise ValueError(f"No engine available for model type: {config.model_type}")

        logger.info(f"Creating engine: {engine_class.__name__}")

        return engine_class(config, **kwargs)

    @classmethod
    def _select_engine_class(cls, config: ModelConfig) -> type[BaseInferenceEngine] | None:
        """Select the best engine class for a model."""
        # Check model file extension for automatic type detection
        model_path = config.model_path.lower()

        # TensorRT engines
        if model_path.endswith((".engine", ".trt")):
            return TensorRTEngine

        # ONNX models
        if model_path.endswith(".onnx"):
            # Use TensorRT for ONNX if CUDA available
            if config.preferred_accelerator in [
                HardwareAccelerator.CUDA,
                HardwareAccelerator.TENSORRT,
                HardwareAccelerator.JETSON,
            ]:
                try:
                    import tensorrt  # noqa: F401

                    return TensorRTEngine
                except ImportError:
                    pass
            return ONNXEngine

        # PyTorch YOLO models
        if model_path.endswith(".pt"):
            return YOLOEngine

        # VLM models
        if config.model_type == ModelType.VLM:
            return cls._select_vlm_engine(config)

        # Default based on model type
        return cls.ENGINE_MAP.get(config.model_type)

    @classmethod
    def _select_vlm_engine(cls, config: ModelConfig) -> type[VLMEngine]:
        """Select VLM engine based on configuration."""
        model_name = config.model_name.lower()

        # Check for known cloud providers
        if "gpt" in model_name or "openai" in model_name:
            return OpenAIVLMEngine

        # Check for Ollama models
        if any(name in model_name for name in ["llava", "llama", "bakllava", "moondream"]):
            return OllamaVLMEngine

        # Check options for explicit backend
        backend = config.options.get("vlm_backend", "ollama")
        return cls.VLM_BACKENDS.get(backend, OllamaVLMEngine)

    @classmethod
    def create_yolo(
        cls,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        accelerator: HardwareAccelerator | None = None,
        **kwargs,
    ) -> YOLOEngine:
        """
        Convenience method to create a YOLO engine.

        Args:
            model_path: Path to YOLO model
            confidence: Confidence threshold
            accelerator: Preferred accelerator
            **kwargs: Additional options

        Returns:
            Configured YOLOEngine
        """
        config = ModelConfig(
            model_path=model_path,
            model_type=ModelType.YOLO,
            model_name=model_path.split("/")[-1].replace(".pt", ""),
            confidence_threshold=confidence,
            preferred_accelerator=accelerator or HardwareAccelerator.CPU,
            **kwargs,
        )

        return cls.create(config, engine_class=YOLOEngine)

    @classmethod
    def create_vlm(
        cls, model_name: str = "llava", backend: str = "ollama", prompt: str | None = None, **kwargs
    ) -> VLMEngine:
        """
        Convenience method to create a VLM engine.

        Args:
            model_name: Model name
            backend: VLM backend ("ollama", "openai", "local")
            prompt: Default prompt
            **kwargs: Additional options

        Returns:
            Configured VLMEngine
        """
        config = ModelConfig(
            model_path=model_name,
            model_type=ModelType.VLM,
            model_name=model_name,
            vlm_prompt=prompt,
            options={"vlm_backend": backend},
            **kwargs,
        )

        engine_class = cls.VLM_BACKENDS.get(backend, OllamaVLMEngine)
        return cls.create(config, engine_class=engine_class)

    @classmethod
    def get_available_engines(cls) -> dict:
        """Get information about available engines."""
        engines = {}

        # Check YOLO
        try:
            from ultralytics import YOLO  # noqa: F401

            engines["yolo"] = {"available": True, "versions": ["v5", "v8", "v11"]}
        except ImportError:
            engines["yolo"] = {"available": False}

        # Check ONNX Runtime
        try:
            import onnxruntime as ort

            providers = ort.get_available_providers()
            engines["onnx"] = {"available": True, "providers": providers}
        except ImportError:
            engines["onnx"] = {"available": False}

        # Check TensorRT
        try:
            import tensorrt

            engines["tensorrt"] = {"available": True, "version": tensorrt.__version__}
        except ImportError:
            engines["tensorrt"] = {"available": False}

        # Check VLM backends
        vlm_backends = {}
        try:
            import ollama  # noqa: F401

            vlm_backends["ollama"] = True
        except ImportError:
            vlm_backends["ollama"] = False

        try:
            import openai  # noqa: F401

            vlm_backends["openai"] = True
        except ImportError:
            vlm_backends["openai"] = False

        try:
            import transformers  # noqa: F401

            vlm_backends["local"] = True
        except ImportError:
            vlm_backends["local"] = False

        engines["vlm"] = {"available": any(vlm_backends.values()), "backends": vlm_backends}

        return engines
