"""
Jetson Backend - NVIDIA Jetson platform acceleration.

Supports Jetson Nano, Jetson Xavier, and Jetson Orin devices
with TensorRT and DeepStream integration.
"""

import logging
import os
import subprocess
from typing import Dict
from typing import Optional

from ..base import HardwareAccelerator
from .base import AcceleratorBackend
from .base import DeviceInfo

logger = logging.getLogger(__name__)


class JetsonBackend(AcceleratorBackend):
    """
    Backend for NVIDIA Jetson platforms.

    Features:
    - Automatic Jetson device detection
    - TensorRT optimization for Jetson GPUs
    - Power mode configuration
    - DeepStream integration support
    - NVDLA support for Xavier/Orin
    """

    accelerator_type = HardwareAccelerator.JETSON

    # Jetson device types
    DEVICE_TYPES = {
        "nano": {"max_power": 10, "dla_cores": 0, "gpu_arch": "maxwell"},
        "tx2": {"max_power": 15, "dla_cores": 0, "gpu_arch": "pascal"},
        "xavier_nx": {"max_power": 20, "dla_cores": 2, "gpu_arch": "volta"},
        "xavier_agx": {"max_power": 30, "dla_cores": 2, "gpu_arch": "volta"},
        "orin_nano": {"max_power": 15, "dla_cores": 1, "gpu_arch": "ampere"},
        "orin_nx": {"max_power": 25, "dla_cores": 2, "gpu_arch": "ampere"},
        "orin_agx": {"max_power": 60, "dla_cores": 2, "gpu_arch": "ampere"},
    }

    def __init__(self):
        self._jetson_type: Optional[str] = None
        self._is_jetson: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if running on a Jetson platform."""
        if self._is_jetson is not None:
            return self._is_jetson

        try:
            # Check for Jetson-specific indicators
            if os.path.exists("/etc/nv_tegra_release"):
                self._is_jetson = True
                self._detect_jetson_type()
                return True

            # Check device tree
            if os.path.exists("/proc/device-tree/compatible"):
                with open("/proc/device-tree/compatible", "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore").lower()
                    if "nvidia,tegra" in content:
                        self._is_jetson = True
                        self._detect_jetson_type()
                        return True

            # Check for jtop
            result = subprocess.run(
                ["which", "jtop"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                self._is_jetson = True
                self._detect_jetson_type()
                return True

        except Exception as e:
            logger.warning(f"Jetson detection failed: {e}")

        self._is_jetson = False
        return False

    def _detect_jetson_type(self) -> None:
        """Detect specific Jetson device type."""
        try:
            # Try reading from device tree
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()

                    if "orin" in model:
                        if "nano" in model:
                            self._jetson_type = "orin_nano"
                        elif "nx" in model:
                            self._jetson_type = "orin_nx"
                        else:
                            self._jetson_type = "orin_agx"
                    elif "xavier" in model:
                        if "nx" in model:
                            self._jetson_type = "xavier_nx"
                        else:
                            self._jetson_type = "xavier_agx"
                    elif "nano" in model:
                        self._jetson_type = "nano"
                    elif "tx2" in model:
                        self._jetson_type = "tx2"

                    logger.info(f"Detected Jetson type: {self._jetson_type}")
                    return

            # Fallback: try jtop
            result = subprocess.run(
                ["jtop", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                # jtop is available, device type detection requires parsing
                self._jetson_type = "nano"  # Default fallback

        except Exception as e:
            logger.warning(f"Could not determine Jetson type: {e}")
            self._jetson_type = "nano"  # Default to Nano

    def get_device_info(self) -> DeviceInfo:
        """Get Jetson device information."""
        if not self.is_available():
            return DeviceInfo(
                name="Jetson (unavailable)",
                accelerator_type=HardwareAccelerator.JETSON,
                is_available=False
            )

        device_specs = self.DEVICE_TYPES.get(
            self._jetson_type or "nano",
            self.DEVICE_TYPES["nano"]
        )

        # Get memory info
        memory_total, memory_available = self._get_memory_info()

        return DeviceInfo(
            name=f"Jetson {self._jetson_type or 'Unknown'}",
            accelerator_type=HardwareAccelerator.JETSON,
            memory_total_mb=memory_total,
            memory_available_mb=memory_available,
            compute_capability=device_specs["gpu_arch"],
            driver_version=self._get_jetpack_version(),
            is_available=True,
            metadata={
                "jetson_type": self._jetson_type,
                "max_power_watts": device_specs["max_power"],
                "dla_cores": device_specs["dla_cores"],
                "gpu_architecture": device_specs["gpu_arch"],
                "power_mode": self._get_power_mode(),
            }
        )

    def get_device_count(self) -> int:
        """Jetson has integrated GPU."""
        return 1 if self.is_available() else 0

    def _get_memory_info(self) -> tuple:
        """Get GPU memory information."""
        try:
            import torch
            if torch.cuda.is_available():
                device = torch.cuda.get_device_properties(0)
                total = device.total_memory // (1024 * 1024)
                allocated = torch.cuda.memory_allocated(0) // (1024 * 1024)
                return total, total - allocated
        except Exception:
            pass

        # Fallback: read from tegrastats
        try:
            result = subprocess.run(
                ["tegrastats", "--once"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            # Parse tegrastats output for RAM info
            # Format varies by Jetson version
        except Exception:
            pass

        return 0, 0

    def _get_jetpack_version(self) -> Optional[str]:
        """Get JetPack version."""
        try:
            if os.path.exists("/etc/nv_tegra_release"):
                with open("/etc/nv_tegra_release", "r") as f:
                    return f.read().strip().split(",")[0].replace("# R", "")
        except Exception:
            pass
        return None

    def _get_power_mode(self) -> Optional[str]:
        """Get current power mode."""
        try:
            result = subprocess.run(
                ["nvpmodel", "-q"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "NV Power Mode" in line:
                        return line.split(":")[1].strip()
        except Exception:
            pass
        return None

    def set_power_mode(self, mode: int) -> bool:
        """
        Set Jetson power mode.

        Args:
            mode: Power mode ID (0 = max performance, higher = power saving)

        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                ["sudo", "nvpmodel", "-m", str(mode)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                logger.info(f"Set Jetson power mode to {mode}")
                return True
        except Exception as e:
            logger.error(f"Failed to set power mode: {e}")
        return False

    def setup_environment(self) -> None:
        """Set up Jetson-optimized environment."""
        # Enable max clocks for inference
        try:
            subprocess.run(
                ["sudo", "jetson_clocks"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info("Enabled Jetson max clocks")
        except Exception:
            pass

        # Set CUDA environment
        os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"

        # TensorRT settings for Jetson
        os.environ.setdefault("TRT_MAX_WORKSPACE_SIZE", str(1 << 29))  # 512MB

        logger.info("Jetson environment configured")

    def optimize_model(
        self,
        model_path: str,
        output_path: str,
        use_fp16: bool = True,
        use_dla: bool = False,
        **kwargs
    ) -> Optional[str]:
        """
        Optimize model for Jetson using TensorRT.

        Args:
            model_path: Path to ONNX or PyTorch model
            output_path: Path to save TensorRT engine
            use_fp16: Use FP16 precision (recommended for Jetson)
            use_dla: Use DLA cores (Xavier/Orin only)

        Returns:
            Path to optimized engine
        """
        device_specs = self.DEVICE_TYPES.get(
            self._jetson_type or "nano",
            self.DEVICE_TYPES["nano"]
        )

        # Check DLA availability
        if use_dla and device_specs["dla_cores"] == 0:
            logger.warning(f"DLA not available on {self._jetson_type}, using GPU")
            use_dla = False

        try:
            import tensorrt as trt

            # For Jetson, use trtexec for best optimization
            if model_path.endswith(".onnx"):
                return self._build_engine_trtexec(
                    model_path, output_path, use_fp16, use_dla
                )
            elif model_path.endswith(".pt"):
                # Export YOLO to engine directly
                return self._export_yolo_tensorrt(
                    model_path, output_path, use_fp16
                )

        except ImportError:
            logger.error("TensorRT not available")
        except Exception as e:
            logger.error(f"Jetson model optimization failed: {e}")

        return None

    def _build_engine_trtexec(
        self,
        onnx_path: str,
        engine_path: str,
        use_fp16: bool,
        use_dla: bool
    ) -> Optional[str]:
        """Build TensorRT engine using trtexec."""
        cmd = [
            "trtexec",
            f"--onnx={onnx_path}",
            f"--saveEngine={engine_path}",
            "--workspace=512",
        ]

        if use_fp16:
            cmd.append("--fp16")

        if use_dla:
            cmd.extend(["--useDLACore=0", "--allowGPUFallback"])

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode == 0:
                logger.info(f"TensorRT engine saved to {engine_path}")
                return engine_path
            else:
                logger.error(f"trtexec failed: {result.stderr}")
        except Exception as e:
            logger.error(f"trtexec execution failed: {e}")

        return None

    def _export_yolo_tensorrt(
        self,
        pt_path: str,
        engine_path: str,
        use_fp16: bool
    ) -> Optional[str]:
        """Export YOLO model directly to TensorRT."""
        try:
            from ultralytics import YOLO

            model = YOLO(pt_path)

            # Ultralytics handles Jetson TensorRT export
            model.export(
                format="engine",
                half=use_fp16,
                device=0,
                workspace=4,  # GB for Jetson
            )

            # The exported file is in the same directory
            expected_path = pt_path.replace(".pt", ".engine")
            if os.path.exists(expected_path):
                if expected_path != engine_path:
                    os.rename(expected_path, engine_path)
                logger.info(f"YOLO TensorRT engine saved to {engine_path}")
                return engine_path

        except Exception as e:
            logger.error(f"YOLO TensorRT export failed: {e}")

        return None

        return None
