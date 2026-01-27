"""
Hardware Detection API Endpoints.

Provides REST API for hardware detection and accelerator information.
"""

from typing import Optional

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from ...schemas.hardware import AcceleratorInfo
from ...schemas.hardware import CPUInfo
from ...schemas.hardware import HardwareDetectionResult
from ...schemas.hardware import PlatformInfo
from ...services.hardware import hardware_detection_service

router = APIRouter()


@router.get(
    "/detect",
    response_model=HardwareDetectionResult,
    summary="Detect Hardware",
    description="""
    Perform comprehensive hardware detection.

    Detects:
    - **CPU**: Architecture (x86_64, ARM64, etc.), vendor, cores, features
    - **Platform**: Board vendor (Intel, AMD, Raspberry Pi, Orange Pi, Aetina, Jetson, etc.)
    - **Accelerators**: NVIDIA GPUs, Hailo-8/8L/10, Google Coral, Axelera, Intel OpenVINO, AMD ROCm

    Results are cached for 5 minutes. Use `refresh=true` to force re-detection.
    """,
)
async def detect_hardware(
    refresh: bool = Query(
        False,
        description="Force refresh detection (bypass cache)"
    )
) -> HardwareDetectionResult:
    """
    Trigger hardware auto-detection process.

    Returns complete hardware information including CPU architecture,
    platform vendor, and all detected AI accelerators.
    """
    try:
        result = hardware_detection_service.detect_all(force_refresh=refresh)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Hardware detection failed: {str(e)}"
        )


@router.get(
    "/cpu",
    response_model=CPUInfo,
    summary="Get CPU Information",
    description="Get detailed CPU information including architecture, cores, and features.",
)
async def get_cpu_info() -> CPUInfo:
    """Get CPU information only."""
    try:
        result = hardware_detection_service.detect_all()
        return result.cpu
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"CPU detection failed: {str(e)}"
        )


@router.get(
    "/platform",
    response_model=PlatformInfo,
    summary="Get Platform Information",
    description="Get platform/board information including vendor and OS details.",
)
async def get_platform_info() -> PlatformInfo:
    """Get platform information only."""
    try:
        result = hardware_detection_service.detect_all()
        return result.platform
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Platform detection failed: {str(e)}"
        )


@router.get(
    "/accelerators",
    response_model=list[AcceleratorInfo],
    summary="Get Accelerators",
    description="""
    Get list of detected AI accelerators.

    Supported accelerators:
    - NVIDIA GPUs (with TensorRT)
    - Hailo-8, Hailo-8L, Hailo-10
    - Google Coral (USB, PCIe, M.2)
    - Axelera Metis
    - Intel OpenVINO
    - AMD ROCm
    """,
)
async def get_accelerators(
    refresh: bool = Query(False, description="Force refresh detection")
) -> list[AcceleratorInfo]:
    """Get list of available hardware accelerators."""
    try:
        result = hardware_detection_service.detect_all(force_refresh=refresh)
        return result.accelerators
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Accelerator detection failed: {str(e)}"
        )


@router.get(
    "/recommended",
    response_model=dict,
    summary="Get Recommended Accelerator",
    description="Get the recommended accelerator for AI inference based on available hardware.",
)
async def get_recommended_accelerator() -> dict:
    """Get the recommended accelerator for this system."""
    try:
        result = hardware_detection_service.detect_all()
        return {
            "recommended": result.recommended_accelerator,
            "available_accelerators": [
                acc.type for acc in result.accelerators
                if acc.status.value == "available"
            ],
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Recommendation failed: {str(e)}"
        )
