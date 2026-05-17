"""
Enhanced Configuration for Carcara Vision.

Supports:
- Multiple ML model types
- Hardware acceleration options
- VLM configuration
- Edge device settings (Jetson, RPi)
"""

from enum import Enum
from typing import Any

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

load_dotenv()


class AcceleratorType(str, Enum):
    """Supported hardware accelerators."""

    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    TENSORRT = "tensorrt"
    JETSON = "jetson"
    RPI = "rpi"
    CORAL_TPU = "coral_tpu"
    HAILO = "hailo"
    OPENVINO = "openvino"


class ModelBackend(str, Enum):
    """Supported model backends."""

    PYTORCH = "pytorch"
    ONNX = "onnx"
    TENSORRT = "tensorrt"
    TFLITE = "tflite"
    OPENVINO = "openvino"


class Settings(BaseSettings):
    """
    Application settings with support for multiple deployment targets.

    Configuration can be set via environment variables or .env file.
    """

    # Project Info
    PROJECT_NAME: str = "Carcara Vision"
    PROJECT_DESCRIPTION: str = "Hardware-Accelerated ML Inference Platform"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str = Field(default="localhost", env="POSTGRES_SERVER")
    POSTGRES_USER: str = Field(default="postgres", env="POSTGRES_USER")
    POSTGRES_PASSWORD: str = Field(default="postgres", env="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field(default="carcara_vision", env="POSTGRES_DB")
    POSTGRES_PORT: int = Field(default=5432, env="POSTGRES_PORT")
    SQLALCHEMY_DATABASE_URI: str | None = None

    # Security
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # ===================
    # ML Configuration
    # ===================

    # Object Detection
    DEFAULT_MODEL: str = Field(default="yolov8n.pt", env="DEFAULT_MODEL")
    CONFIDENCE_THRESHOLD: float = Field(default=0.5, env="CONFIDENCE_THRESHOLD")
    IOU_THRESHOLD: float = Field(default=0.45, env="IOU_THRESHOLD")
    MAX_DETECTIONS: int = Field(default=100, env="MAX_DETECTIONS")

    # Supported YOLO models
    SUPPORTED_MODELS: list[str] = [
        "yolov8n.pt",  # Nano - fastest
        "yolov8s.pt",  # Small
        "yolov8m.pt",  # Medium
        "yolov8l.pt",  # Large
        "yolov8x.pt",  # Extra Large - most accurate
        "yolov5n.pt",
        "yolov5s.pt",
        "yolov5m.pt",
        "yolo11n.pt",  # YOLO11 models
        "yolo11s.pt",
    ]

    # Model paths
    MODELS_DIR: str = Field(default="./models", env="MODELS_DIR")
    MODEL_CACHE_DIR: str = Field(default="./.model_cache", env="MODEL_CACHE_DIR")

    # ===================
    # Hardware Acceleration
    # ===================

    # General GPU settings
    USE_GPU: bool = Field(default=False, env="USE_GPU")
    CUDA_VISIBLE_DEVICES: str | None = Field(default=None, env="CUDA_VISIBLE_DEVICES")
    ACCELERATOR: AcceleratorType = Field(default=AcceleratorType.AUTO, env="ACCELERATOR")
    MODEL_BACKEND: ModelBackend = Field(default=ModelBackend.PYTORCH, env="MODEL_BACKEND")

    # TensorRT settings
    TENSORRT_ENABLED: bool = Field(default=False, env="TENSORRT_ENABLED")
    TENSORRT_FP16: bool = Field(default=True, env="TENSORRT_FP16")
    TENSORRT_INT8: bool = Field(default=False, env="TENSORRT_INT8")
    TENSORRT_WORKSPACE_GB: int = Field(default=4, env="TENSORRT_WORKSPACE_GB")

    # Jetson-specific settings
    JETSON_POWER_MODE: int = Field(default=0, env="JETSON_POWER_MODE")  # 0 = max perf
    JETSON_USE_DLA: bool = Field(default=False, env="JETSON_USE_DLA")

    # Raspberry Pi settings
    RPI_USE_CORAL_TPU: bool = Field(default=False, env="RPI_USE_CORAL_TPU")
    RPI_USE_HAILO: bool = Field(default=False, env="RPI_USE_HAILO")
    RPI_CPU_THREADS: int | None = Field(default=None, env="RPI_CPU_THREADS")

    # ===================
    # VLM Configuration
    # ===================

    VLM_ENABLED: bool = Field(default=False, env="VLM_ENABLED")
    VLM_BACKEND: str = Field(default="ollama", env="VLM_BACKEND")  # ollama, openai, local
    VLM_MODEL: str = Field(default="llava", env="VLM_MODEL")
    VLM_MAX_TOKENS: int = Field(default=512, env="VLM_MAX_TOKENS")
    VLM_TEMPERATURE: float = Field(default=0.7, env="VLM_TEMPERATURE")

    # Ollama settings
    OLLAMA_HOST: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")

    # OpenAI settings (for GPT-4V)
    OPENAI_API_KEY: str | None = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4o", env="OPENAI_MODEL")

    # ===================
    # Streaming Configuration
    # ===================

    # go2rtc settings
    GO2RTC_HOST: str = Field(default="http://go2rtc:1984", env="GO2RTC_HOST")
    GO2RTC_API_URL: str = Field(default="http://localhost:1984/api", env="GO2RTC_API_URL")

    # Stream settings
    MAX_CONCURRENT_STREAMS: int = Field(default=16, env="MAX_CONCURRENT_STREAMS")
    STREAM_BUFFER_SIZE: int = Field(default=10, env="STREAM_BUFFER_SIZE")
    STREAM_RECONNECT_DELAY: int = Field(default=5, env="STREAM_RECONNECT_DELAY")

    # Recording settings
    RECORDING_ENABLED: bool = Field(default=False, env="RECORDING_ENABLED")
    RECORDING_PATH: str = Field(default="./recordings", env="RECORDING_PATH")
    RECORDING_SEGMENT_DURATION: int = Field(default=300, env="RECORDING_SEGMENT_DURATION")  # 5 min

    # ===================
    # Detection Processing
    # ===================

    # Detection interval (process every N frames)
    DETECTION_FRAME_SKIP: int = Field(default=1, env="DETECTION_FRAME_SKIP")

    # Alarm settings
    ALARM_COOLDOWN_SECONDS: int = Field(default=30, env="ALARM_COOLDOWN_SECONDS")
    ALARM_CLASSES: list[str] = Field(default=["person", "car", "truck", "dog", "cat"], env="ALARM_CLASSES")

    # ROI settings
    ROI_DEFAULT_COLOR: str = Field(default="#00FF00", env="ROI_DEFAULT_COLOR")
    ROI_LINE_WIDTH: int = Field(default=2, env="ROI_LINE_WIDTH")

    # ===================
    # Logging
    # ===================

    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", env="LOG_FORMAT")
    LOG_FILE: str | None = Field(default=None, env="LOG_FILE")

    # ===================
    # Validators
    # ===================

    @field_validator("CONFIDENCE_THRESHOLD")
    @classmethod
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        return v

    @field_validator("IOU_THRESHOLD")
    @classmethod
    def validate_iou(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError("IOU threshold must be between 0.0 and 1.0")
        return v

    @field_validator("ACCELERATOR", mode="before")
    @classmethod
    def validate_accelerator(cls, v):
        if isinstance(v, str):
            return AcceleratorType(v.lower())
        return v

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Build database URI
        self.SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    def get_accelerator_config(self) -> dict[str, Any]:
        """Get hardware accelerator configuration."""
        return {
            "type": self.ACCELERATOR.value,
            "use_gpu": self.USE_GPU,
            "cuda_devices": self.CUDA_VISIBLE_DEVICES,
            "tensorrt": {
                "enabled": self.TENSORRT_ENABLED,
                "fp16": self.TENSORRT_FP16,
                "int8": self.TENSORRT_INT8,
                "workspace_gb": self.TENSORRT_WORKSPACE_GB,
            },
            "jetson": {
                "power_mode": self.JETSON_POWER_MODE,
                "use_dla": self.JETSON_USE_DLA,
            },
            "raspberry_pi": {
                "use_coral": self.RPI_USE_CORAL_TPU,
                "use_hailo": self.RPI_USE_HAILO,
                "cpu_threads": self.RPI_CPU_THREADS,
            },
        }

    def get_vlm_config(self) -> dict[str, Any]:
        """Get VLM configuration."""
        return {
            "enabled": self.VLM_ENABLED,
            "backend": self.VLM_BACKEND,
            "model": self.VLM_MODEL,
            "max_tokens": self.VLM_MAX_TOKENS,
            "temperature": self.VLM_TEMPERATURE,
            "ollama_host": self.OLLAMA_HOST,
            "openai_model": self.OPENAI_MODEL,
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Global settings instance
settings = Settings()
