"""
Hardware Detection Utility.

Automatically detects available hardware accelerators on the system.
"""

import logging
import os
import platform
import subprocess

from ..base import HardwareAccelerator
from .base import AcceleratorBackend
from .base import DeviceInfo
from .cuda import CUDABackend
from .jetson import JetsonBackend
from .raspberry import RaspberryPiBackend

logger = logging.getLogger(__name__)


class HardwareDetector:
    """
    Utility class for detecting available hardware accelerators.

    Supports detection of:
    - NVIDIA GPUs (CUDA/TensorRT)
    - Jetson devices (Nano, Xavier, Orin)
    - Raspberry Pi (with Coral TPU, Hailo)
    - Intel CPUs (with OpenVINO)
    - Generic CPU fallback
    """

    _backends: dict[HardwareAccelerator, type[AcceleratorBackend]] = {}
    _cached_detection: dict[HardwareAccelerator, bool] | None = None

    @classmethod
    def register_backend(cls, accelerator: HardwareAccelerator, backend_class: type[AcceleratorBackend]) -> None:
        """Register a backend class for an accelerator type."""
        cls._backends[accelerator] = backend_class

    @classmethod
    def detect_all(cls, refresh: bool = False) -> dict[HardwareAccelerator, bool]:
        """
        Detect all available hardware accelerators.

        Args:
            refresh: Force re-detection even if cached

        Returns:
            Dictionary mapping accelerator types to availability
        """
        if cls._cached_detection is not None and not refresh:
            return cls._cached_detection

        results = {}

        # Check each registered backend
        for accelerator, backend_class in cls._backends.items():
            try:
                backend = backend_class()
                results[accelerator] = backend.is_available()
            except Exception as e:
                logger.warning(f"Error checking {accelerator}: {e}")
                results[accelerator] = False

        # Always add CPU as fallback
        results[HardwareAccelerator.CPU] = True

        cls._cached_detection = results
        return results

    @classmethod
    def get_best_accelerator(
        cls,
        preferred: HardwareAccelerator | None = None,
        fallbacks: list[HardwareAccelerator] | None = None,
    ) -> HardwareAccelerator:
        """
        Get the best available accelerator.

        Args:
            preferred: Preferred accelerator to use if available
            fallbacks: List of fallback accelerators in order of preference

        Returns:
            Best available accelerator
        """
        available = cls.detect_all()

        # Check preferred first
        if preferred and available.get(preferred, False):
            return preferred

        # Check fallbacks
        if fallbacks:
            for acc in fallbacks:
                if available.get(acc, False):
                    return acc

        # Default priority order
        priority = [
            HardwareAccelerator.TENSORRT,
            HardwareAccelerator.CUDA,
            HardwareAccelerator.JETSON,
            HardwareAccelerator.CORAL_TPU,
            HardwareAccelerator.HAILO,
            HardwareAccelerator.OPENVINO,
            HardwareAccelerator.RPI,
            HardwareAccelerator.CPU,
        ]

        for acc in priority:
            if available.get(acc, False):
                return acc

        return HardwareAccelerator.CPU

    @classmethod
    def get_backend(cls, accelerator: HardwareAccelerator) -> AcceleratorBackend | None:
        """Get a backend instance for an accelerator type."""
        backend_class = cls._backends.get(accelerator)
        if backend_class:
            return backend_class()
        return None

    @classmethod
    def get_all_device_info(cls) -> dict[HardwareAccelerator, DeviceInfo]:
        """Get device info for all available accelerators."""
        info = {}
        available = cls.detect_all()

        for accelerator, is_available in available.items():
            if is_available:
                backend = cls.get_backend(accelerator)
                if backend:
                    try:
                        info[accelerator] = backend.get_device_info()
                    except Exception as e:
                        logger.warning(f"Error getting info for {accelerator}: {e}")

        return info

    @staticmethod
    def detect_platform() -> dict[str, str]:
        """Detect the current platform information."""
        return {
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        }

    @staticmethod
    def is_jetson() -> bool:
        """Check if running on NVIDIA Jetson platform."""
        try:
            # Check for Jetson-specific files
            if os.path.exists("/etc/nv_tegra_release"):
                return True

            # Check for Jetson device tree
            if os.path.exists("/proc/device-tree/compatible"):
                with open("/proc/device-tree/compatible", "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    if "nvidia,tegra" in content.lower():
                        return True

            # Check for jetson-stats
            result = subprocess.run(["which", "jtop"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                return True

        except Exception:
            pass

        return False

    @staticmethod
    def is_raspberry_pi() -> bool:
        """Check if running on Raspberry Pi."""
        try:
            # Check model file
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    model = f.read().lower()
                    if "raspberry pi" in model:
                        return True

            # Check cpuinfo
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo") as f:
                    content = f.read().lower()
                    if "raspberry" in content or "bcm" in content:
                        return True

        except Exception:
            pass

        return False

    @staticmethod
    def detect_coral_tpu() -> bool:
        """Check if Google Coral TPU is available."""
        try:
            # Check for Edge TPU runtime
            result = subprocess.run(["dpkg", "-l", "libedgetpu1-std"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                return True

            # Try importing tflite_runtime with Edge TPU
            try:
                import tflite_runtime.interpreter as tflite

                # Check for Edge TPU delegate
                delegates = tflite.load_delegate("libedgetpu.so.1")  # noqa: F841
                return True
            except Exception:
                pass

        except Exception:
            pass

        return False

    @staticmethod
    def detect_hailo() -> bool:
        """Check if Hailo AI accelerator is available."""
        try:
            # Check for Hailo runtime
            result = subprocess.run(
                ["hailortcli", "fw-control", "identify"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return result.returncode == 0
        except Exception:
            pass

        return False
        return False


# Register built-in backends on module import
HardwareDetector.register_backend(HardwareAccelerator.CUDA, CUDABackend)
HardwareDetector.register_backend(HardwareAccelerator.JETSON, JetsonBackend)
HardwareDetector.register_backend(HardwareAccelerator.RPI, RaspberryPiBackend)
HardwareDetector.register_backend(HardwareAccelerator.RPI, RaspberryPiBackend)
