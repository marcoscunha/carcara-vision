"""
CPU Backend - Fallback accelerator using standard CPU inference.
"""

import logging
import os
import platform

from ..base import HardwareAccelerator
from .base import AcceleratorBackend, DeviceInfo

logger = logging.getLogger(__name__)


class CPUBackend(AcceleratorBackend):
    """
    CPU backend for inference.

    This is the fallback backend that works on all systems.
    Supports multi-threading optimization for better performance.
    """

    accelerator_type = HardwareAccelerator.CPU

    def is_available(self) -> bool:
        """CPU is always available."""
        return True

    def get_device_info(self) -> DeviceInfo:
        """Get CPU information."""
        try:
            import psutil

            memory_total = psutil.virtual_memory().total // (1024 * 1024)
            memory_available = psutil.virtual_memory().available // (1024 * 1024)
        except ImportError:
            memory_total = 0
            memory_available = 0

        cpu_count = os.cpu_count() or 1

        return DeviceInfo(
            name=platform.processor() or "CPU",
            accelerator_type=HardwareAccelerator.CPU,
            memory_total_mb=memory_total,
            memory_available_mb=memory_available,
            is_available=True,
            metadata={
                "cpu_count": cpu_count,
                "architecture": platform.machine(),
            },
        )

    def get_device_count(self) -> int:
        """Return 1 for CPU."""
        return 1

    def setup_environment(self) -> None:
        """Set up optimal CPU threading."""
        cpu_count = os.cpu_count() or 1

        # Set OpenMP threads
        os.environ.setdefault("OMP_NUM_THREADS", str(cpu_count))

        # Set MKL threads (Intel)
        os.environ.setdefault("MKL_NUM_THREADS", str(cpu_count))

        # Set number of inter-op parallelism threads
        try:
            import torch

            torch.set_num_threads(cpu_count)
        except ImportError:
            pass

        logger.info(f"CPU backend configured with {cpu_count} threads")

    def optimize_model(self, model_path: str, output_path: str, quantize: bool = False, **kwargs) -> str | None:
        """
        Optimize model for CPU inference.

        Args:
            model_path: Path to the original model
            output_path: Path to save optimized model
            quantize: Apply INT8 quantization

        Returns:
            Path to optimized model
        """
        if quantize:
            try:
                # For ONNX models, apply quantization
                if model_path.endswith(".onnx"):
                    from onnxruntime.quantization import QuantType, quantize_dynamic

                    quantize_dynamic(model_path, output_path, weight_type=QuantType.QInt8)
                    logger.info(f"Quantized model saved to {output_path}")
                    return output_path
            except Exception as e:
                logger.warning(f"Quantization failed: {e}")

        return None

        return None
