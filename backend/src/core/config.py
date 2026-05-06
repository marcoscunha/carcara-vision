import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings(BaseSettings):
    PROJECT_NAME: str = "Carcara NVC Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "carcara_nvc")
    SQLALCHEMY_DATABASE_URI: str | None = None

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    AUTH_ENABLED: bool = _env_bool("AUTH_ENABLED", True)

    # Object Detection
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "yolov8n")
    CONFIDENCE_THRESHOLD: float = 0.5
    SUPPORTED_MODELS: list[str] = [
        "yolov8n",
        "yolov8s",
        "yolov8m",
        "yolov8l",
        "yolov8x",
    ]

    # Hardware Acceleration
    CUDA_VISIBLE_DEVICES: str | None = os.getenv("CUDA_VISIBLE_DEVICES", None)
    USE_GPU: bool = os.getenv("USE_GPU", "False").lower() == "true"
    ACCEL_PREPROCESS_MODE: str = os.getenv("ACCEL_PREPROCESS_MODE", "auto")
    ACCEL_POSTPROCESS_MODE: str = os.getenv("ACCEL_POSTPROCESS_MODE", "auto")
    ACCEL_ANNOTATE_MODE: str = os.getenv("ACCEL_ANNOTATE_MODE", "auto")
    ACCEL_ENCODER_MODE: str = os.getenv("ACCEL_ENCODER_MODE", "auto")
    ACCEL_STRICT: bool = _env_bool("ACCEL_STRICT", False)

    # GStreamer Configuration (replaces go2rtc)
    GSTREAMER_API_URL: str = os.getenv("GSTREAMER_API_URL", "http://gstreamer:8085")
    GSTREAMER_SELF_HEAL_ENABLED: bool = _env_bool("GSTREAMER_SELF_HEAL_ENABLED", True)
    GSTREAMER_SELF_HEAL_INTERVAL_SECONDS: int = int(os.getenv("GSTREAMER_SELF_HEAL_INTERVAL_SECONDS", "15"))
    GSTREAMER_AUTO_RECREATE: bool = _env_bool("GSTREAMER_AUTO_RECREATE", True)
    GSTREAMER_CONTAINER_NAME: str = os.getenv("GSTREAMER_CONTAINER_NAME", "gstreamer")

    # MediaMTX Configuration (media server for RTSP/WebRTC/HLS)
    MEDIAMTX_API_URL: str = os.getenv("MEDIAMTX_API_URL", "http://mediamtx:9997")
    MEDIAMTX_RTSP_HOST: str = os.getenv("MEDIAMTX_RTSP_HOST", "localhost")
    MEDIAMTX_RTSP_PORT: int = int(os.getenv("MEDIAMTX_RTSP_PORT", "8554"))
    MEDIAMTX_WEBRTC_PORT: int = int(os.getenv("MEDIAMTX_WEBRTC_PORT", "8889"))
    MEDIAMTX_HLS_PORT: int = int(os.getenv("MEDIAMTX_HLS_PORT", "8888"))

    # Legacy go2rtc Configuration (deprecated - kept for backward compatibility)
    GO2RTC_URL: str = os.getenv("GO2RTC_URL", "http://go2rtc:1984")
    GO2RTC_RTSP_PORT: int = int(os.getenv("GO2RTC_RTSP_PORT", "8554"))
    GO2RTC_RTSP_HOST: str = os.getenv("GO2RTC_RTSP_HOST", "localhost")

    # Model path
    MODEL_PATH: str = os.getenv("MODEL_PATH", "yolov8n.pt")

    # Keycloak / OAuth2 Configuration
    KEYCLOAK_INTERNAL_URL: str = os.getenv("KEYCLOAK_INTERNAL_URL", os.getenv("KEYCLOAK_URL", "http://keycloak:8080"))
    KEYCLOAK_ISSUER_URL: str = os.getenv("KEYCLOAK_ISSUER_URL", "http://localhost:8280")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "carcara")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "carcara-backend")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )


settings = Settings()
