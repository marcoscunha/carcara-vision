import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


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

    # Object Detection
    DEFAULT_MODEL: str = "yolov8n.pt"
    CONFIDENCE_THRESHOLD: float = 0.5
    SUPPORTED_MODELS: list[str] = [
        "yolov8n.pt",
        "yolov8s.pt",
        "yolov8m.pt",
        "yolov8l.pt",
        "yolov8x.pt",
    ]

    # Hardware Acceleration
    CUDA_VISIBLE_DEVICES: str | None = os.getenv("CUDA_VISIBLE_DEVICES", None)
    USE_GPU: bool = os.getenv("USE_GPU", "False").lower() == "true"

    # GStreamer Configuration (replaces go2rtc)
    GSTREAMER_API_URL: str = os.getenv("GSTREAMER_API_URL", "http://gstreamer:8085")

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.SQLALCHEMY_DATABASE_URI = (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )


settings = Settings()
