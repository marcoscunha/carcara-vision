"""
CUDA Backend - NVIDIA GPU acceleration using CUDA.
"""

import logging
import os
import subprocess

from ..base import HardwareAccelerator
from .base import AcceleratorBackend, DeviceInfo

logger = logging.getLogger(__name__)


class CUDABackend(AcceleratorBackend):
    """
    CUDA backend for NVIDIA GPU inference.

    Supports:
    - CUDA-enabled inference with PyTorch
    - Automatic device selection
    - Memory management
    - TensorRT optimization (optional)
    """

    accelerator_type = HardwareAccelerator.CUDA

    def __init__(self, device_id: int = 0):
        self.device_id = device_id
        self._cuda_available: bool | None = None

    def is_available(self) -> bool:
        """Check if CUDA is available."""
        if self._cuda_available is not None:
            return self._cuda_available

        try:
            # Check nvidia-smi
            result = subprocess.run(["nvidia-smi"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                self._cuda_available = False
                return False

            # Check PyTorch CUDA
            import torch

            self._cuda_available = torch.cuda.is_available()
            return self._cuda_available

        except Exception as e:
            logger.warning(f"CUDA check failed: {e}")
            self._cuda_available = False
            return False

    def get_device_info(self) -> DeviceInfo:
        """Get CUDA device information."""
        if not self.is_available():
            return DeviceInfo(
                name="CUDA (unavailable)",
                accelerator_type=HardwareAccelerator.CUDA,
                is_available=False,
            )

        try:
            import torch

            device = torch.cuda.get_device_properties(self.device_id)
            memory_total = device.total_memory // (1024 * 1024)
            memory_allocated = torch.cuda.memory_allocated(self.device_id) // (1024 * 1024)
            memory_available = memory_total - memory_allocated

            return DeviceInfo(
                name=device.name,
                accelerator_type=HardwareAccelerator.CUDA,
                memory_total_mb=memory_total,
                memory_available_mb=memory_available,
                compute_capability=f"{device.major}.{device.minor}",
                driver_version=self._get_driver_version(),
                is_available=True,
                metadata={
                    "device_id": self.device_id,
                    "multi_processor_count": device.multi_processor_count,
                    "cuda_version": torch.version.cuda,
                },
            )
        except Exception as e:
            logger.error(f"Error getting CUDA device info: {e}")
            return DeviceInfo(name="CUDA (error)", accelerator_type=HardwareAccelerator.CUDA, is_available=False)

    def get_device_count(self) -> int:
        """Get number of CUDA devices."""
        if not self.is_available():
            return 0

        try:
            import torch

            return torch.cuda.device_count()
        except Exception:
            return 0

    def _get_driver_version(self) -> str | None:
        """Get NVIDIA driver version."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return None

    def setup_environment(self) -> None:
        """Set up CUDA environment."""
        # Set CUDA device
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        os.environ["CUDA_VISIBLE_DEVICES"] = str(self.device_id)

        # Enable TF32 for Ampere+ GPUs
        try:
            import torch

            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            torch.backends.cudnn.benchmark = True
        except Exception:
            pass

        logger.info(f"CUDA backend configured for device {self.device_id}")

    def optimize_model(self, model_path: str, output_path: str, use_fp16: bool = True, **kwargs) -> str | None:
        """
        Optimize model for CUDA inference using TensorRT.

        Args:
            model_path: Path to ONNX or PyTorch model
            output_path: Path to save TensorRT engine
            use_fp16: Use FP16 precision

        Returns:
            Path to optimized engine
        """
        try:
            # Check for TensorRT
            import tensorrt as trt  # noqa: F401

            if model_path.endswith(".onnx"):
                return self._build_tensorrt_engine(model_path, output_path, use_fp16)
            elif model_path.endswith(".pt"):
                # Export to ONNX first, then build TensorRT
                onnx_path = model_path.replace(".pt", ".onnx")
                self._export_to_onnx(model_path, onnx_path)
                return self._build_tensorrt_engine(onnx_path, output_path, use_fp16)

        except ImportError:
            logger.warning("TensorRT not available for optimization")
        except Exception as e:
            logger.error(f"Model optimization failed: {e}")

        return None

    def _export_to_onnx(self, pt_path: str, onnx_path: str) -> None:
        """Export PyTorch model to ONNX."""
        try:
            from ultralytics import YOLO

            model = YOLO(pt_path)
            model.export(format="onnx", opset=12)
            logger.info(f"Exported model to {onnx_path}")
        except Exception as e:
            logger.error(f"ONNX export failed: {e}")
            raise

    def _build_tensorrt_engine(self, onnx_path: str, engine_path: str, use_fp16: bool) -> str | None:
        """Build TensorRT engine from ONNX model."""
        try:
            import tensorrt as trt

            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)
            builder = trt.Builder(TRT_LOGGER)
            network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
            parser = trt.OnnxParser(network, TRT_LOGGER)

            with open(onnx_path, "rb") as f:
                if not parser.parse(f.read()):
                    for error in range(parser.num_errors):
                        logger.error(parser.get_error(error))
                    return None

            config = builder.create_builder_config()
            config.max_workspace_size = 1 << 30  # 1GB

            if use_fp16 and builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)

            engine = builder.build_engine(network, config)

            if engine:
                with open(engine_path, "wb") as f:
                    f.write(engine.serialize())
                logger.info(f"TensorRT engine saved to {engine_path}")
                return engine_path

        except Exception as e:
            logger.error(f"TensorRT build failed: {e}")

        return None

    def clear_memory(self) -> None:
        """Clear CUDA memory cache."""
        try:
            import torch

            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.info("CUDA memory cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear CUDA memory: {e}")
            logger.warning(f"Failed to clear CUDA memory: {e}")
            logger.warning(f"Failed to clear CUDA memory: {e}")
