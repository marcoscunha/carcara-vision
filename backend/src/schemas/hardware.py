"""
Hardware Detection Schemas.

Pydantic models for hardware detection API responses.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CPUArchitecture(str, Enum):
    """CPU architecture types."""

    X86_64 = "x86_64"
    X86 = "x86"
    ARM64 = "arm64"
    ARMV7 = "armv7"
    ARMV8 = "armv8"
    UNKNOWN = "unknown"


class PlatformVendor(str, Enum):
    """Platform/Board vendor types."""

    INTEL = "intel"
    AMD = "amd"
    NVIDIA_JETSON = "nvidia_jetson"
    RASPBERRY_PI = "raspberry_pi"
    ORANGE_PI = "orange_pi"
    AETINA = "aetina"
    ROCK_PI = "rock_pi"
    KHADAS = "khadas"
    GENERIC_ARM = "generic_arm"
    GENERIC_X86 = "generic_x86"
    UNKNOWN = "unknown"


class AcceleratorType(str, Enum):
    """Hardware accelerator types."""

    # NVIDIA
    NVIDIA_GPU = "nvidia_gpu"
    NVIDIA_TENSORRT = "nvidia_tensorrt"
    NVIDIA_JETSON = "nvidia_jetson"

    # Google
    GOOGLE_CORAL_USB = "google_coral_usb"
    GOOGLE_CORAL_PCIE = "google_coral_pcie"
    GOOGLE_CORAL_M2 = "google_coral_m2"

    # Hailo
    HAILO_8 = "hailo_8"
    HAILO_8L = "hailo_8l"
    HAILO_10 = "hailo_10"

    # Intel
    INTEL_OPENVINO = "intel_openvino"
    INTEL_MOVIDIUS = "intel_movidius"

    # Axelera
    AXELERA_M2 = "axelera_m2"

    # AMD
    AMD_ROCM = "amd_rocm"

    # CPU fallback
    CPU = "cpu"


class AcceleratorStatus(str, Enum):
    """Accelerator detection status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DRIVER_MISSING = "driver_missing"
    NOT_DETECTED = "not_detected"
    ERROR = "error"


class CPUInfo(BaseModel):
    """CPU information."""

    architecture: CPUArchitecture
    model_name: str = Field(default="Unknown")
    vendor: str = Field(default="Unknown")
    cores: int = Field(default=0)
    threads: int = Field(default=0)
    max_frequency_mhz: float | None = None
    features: list[str] = Field(default_factory=list)


class MemoryInfo(BaseModel):
    """System memory information."""

    total_gb: float
    available_gb: float
    used_percent: float


class PlatformInfo(BaseModel):
    """Platform/Board information."""

    vendor: PlatformVendor
    board_name: str = Field(default="Unknown")
    board_model: str | None = None
    serial_number: str | None = None
    os_name: str = Field(default="Unknown")
    os_version: str = Field(default="Unknown")
    kernel_version: str = Field(default="Unknown")


class AcceleratorInfo(BaseModel):
    """Individual accelerator information."""

    type: AcceleratorType
    name: str
    status: AcceleratorStatus
    driver_version: str | None = None
    firmware_version: str | None = None
    memory_mb: int | None = None
    compute_capability: str | None = None
    device_path: str | None = None
    pcie_address: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class HardwareDetectionResult(BaseModel):
    """Complete hardware detection result."""

    cpu: CPUInfo
    memory: MemoryInfo
    platform: PlatformInfo
    accelerators: list[AcceleratorInfo]
    recommended_accelerator: AcceleratorType | None = None
    detection_timestamp: str
    detection_duration_ms: float

    class Config:
        json_schema_extra = {
            "example": {
                "cpu": {
                    "architecture": "x86_64",
                    "model_name": "Intel(R) Core(TM) i7-10700K",
                    "vendor": "GenuineIntel",
                    "cores": 8,
                    "threads": 16,
                    "features": ["avx", "avx2", "sse4_2"],
                },
                "memory": {"total_gb": 32.0, "available_gb": 24.5, "used_percent": 23.4},
                "platform": {
                    "vendor": "intel",
                    "board_name": "Generic x86_64",
                    "os_name": "Ubuntu",
                    "os_version": "22.04",
                    "kernel_version": "5.15.0-generic",
                },
                "accelerators": [
                    {
                        "type": "nvidia_gpu",
                        "name": "NVIDIA GeForce RTX 3080",
                        "status": "available",
                        "driver_version": "535.104.05",
                        "memory_mb": 10240,
                    }
                ],
                "recommended_accelerator": "nvidia_gpu",
                "detection_timestamp": "2026-01-27T10:30:00Z",
                "detection_duration_ms": 1523.5,
            }
        }
