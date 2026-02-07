"""
Raspberry Pi Backend - Acceleration for Raspberry Pi with optional AI accelerators.

Supports:
- Raspberry Pi 4/5 with CPU inference
- Google Coral Edge TPU (USB or M.2)
- Hailo-8 AI accelerator
- Raspberry Pi AI Kit (Hailo-8L)
"""

import logging
import os
import subprocess

from ..base import HardwareAccelerator
from .base import AcceleratorBackend, DeviceInfo

logger = logging.getLogger(__name__)


class RaspberryPiBackend(AcceleratorBackend):
    """
    Backend for Raspberry Pi platforms.

    Features:
    - Automatic Pi model detection
    - Coral Edge TPU support
    - Hailo-8/8L accelerator support
    - ARM NEON optimization
    - TensorFlow Lite inference
    """

    accelerator_type = HardwareAccelerator.RPI

    # Raspberry Pi models
    PI_MODELS = {
        "pi3": {"cores": 4, "freq_mhz": 1200, "ram_gb": 1},
        "pi4": {"cores": 4, "freq_mhz": 1500, "ram_gb": 8},
        "pi5": {"cores": 4, "freq_mhz": 2400, "ram_gb": 8},
        "cm4": {"cores": 4, "freq_mhz": 1500, "ram_gb": 8},
    }

    def __init__(self):
        self._is_rpi: bool | None = None
        self._pi_model: str | None = None
        self._has_coral: bool | None = None
        self._has_hailo: bool | None = None

    def is_available(self) -> bool:
        """Check if running on Raspberry Pi."""
        if self._is_rpi is not None:
            return self._is_rpi

        try:
            # Check device tree model
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    model = f.read().lower()
                    if "raspberry pi" in model:
                        self._is_rpi = True
                        self._detect_pi_model(model)
                        return True

            # Check cpuinfo
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo") as f:
                    content = f.read().lower()
                    if "raspberry" in content or "bcm2" in content:
                        self._is_rpi = True
                        return True

        except Exception as e:
            logger.warning(f"Raspberry Pi detection failed: {e}")

        self._is_rpi = False
        return False

    def _detect_pi_model(self, model_str: str) -> None:
        """Detect specific Raspberry Pi model."""
        model_str = model_str.lower()

        if "raspberry pi 5" in model_str:
            self._pi_model = "pi5"
        elif "raspberry pi 4" in model_str or "bcm2711" in model_str:
            self._pi_model = "pi4"
        elif "compute module 4" in model_str:
            self._pi_model = "cm4"
        elif "raspberry pi 3" in model_str or "bcm2837" in model_str:
            self._pi_model = "pi3"
        else:
            self._pi_model = "pi4"  # Default fallback

        logger.info(f"Detected Raspberry Pi model: {self._pi_model}")

    def get_device_info(self) -> DeviceInfo:
        """Get Raspberry Pi device information."""
        if not self.is_available():
            return DeviceInfo(
                name="Raspberry Pi (unavailable)",
                accelerator_type=HardwareAccelerator.RPI,
                is_available=False,
            )

        pi_specs = self.PI_MODELS.get(self._pi_model or "pi4", self.PI_MODELS["pi4"])

        # Get actual memory info
        memory_total, memory_available = self._get_memory_info()

        # Detect accelerators
        accelerators = self._detect_accelerators()

        return DeviceInfo(
            name=f"Raspberry Pi {self._pi_model or 'Unknown'}",
            accelerator_type=HardwareAccelerator.RPI,
            memory_total_mb=memory_total,
            memory_available_mb=memory_available,
            is_available=True,
            metadata={
                "pi_model": self._pi_model,
                "cpu_cores": pi_specs["cores"],
                "cpu_freq_mhz": pi_specs["freq_mhz"],
                "has_coral_tpu": accelerators.get("coral", False),
                "has_hailo": accelerators.get("hailo", False),
                "accelerators": list(accelerators.keys()),
            },
        )

    def get_device_count(self) -> int:
        """Return 1 for Raspberry Pi."""
        return 1 if self.is_available() else 0

    def _get_memory_info(self) -> tuple:
        """Get system memory information."""
        try:
            with open("/proc/meminfo") as f:
                content = f.read()
                total = 0
                available = 0
                for line in content.split("\n"):
                    if line.startswith("MemTotal:"):
                        total = int(line.split()[1]) // 1024  # Convert KB to MB
                    elif line.startswith("MemAvailable:"):
                        available = int(line.split()[1]) // 1024
                return total, available
        except Exception:
            pass
        return 0, 0

    def _detect_accelerators(self) -> dict[str, bool]:
        """Detect available AI accelerators."""
        accelerators = {}

        # Check for Coral TPU
        if self._has_coral is None:
            self._has_coral = self._detect_coral_tpu()
        accelerators["coral"] = self._has_coral

        # Check for Hailo
        if self._has_hailo is None:
            self._has_hailo = self._detect_hailo()
        accelerators["hailo"] = self._has_hailo

        return accelerators

    def _detect_coral_tpu(self) -> bool:
        """Detect Google Coral Edge TPU."""
        try:
            # Check for Edge TPU USB device
            result = subprocess.run(["lsusb"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "18d1:9302" in result.stdout or "google" in result.stdout.lower():
                return True

            # Check for Edge TPU runtime
            result = subprocess.run(["dpkg", "-l", "libedgetpu1-std"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                return True

        except Exception:
            pass
        return False

    def _detect_hailo(self) -> bool:
        """Detect Hailo AI accelerator."""
        try:
            # Check for Hailo device
            result = subprocess.run(
                ["hailortcli", "fw-control", "identify"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                return True

            # Check for Hailo PCIe device
            if os.path.exists("/dev/hailo0"):
                return True

        except Exception:
            pass
        return False

    def has_coral_tpu(self) -> bool:
        """Check if Coral TPU is available."""
        if self._has_coral is None:
            self._has_coral = self._detect_coral_tpu()
        return self._has_coral

    def has_hailo(self) -> bool:
        """Check if Hailo accelerator is available."""
        if self._has_hailo is None:
            self._has_hailo = self._detect_hailo()
        return self._has_hailo

    def setup_environment(self) -> None:
        """Set up Raspberry Pi optimized environment."""
        # Set optimal thread count
        cpu_count = os.cpu_count() or 4
        os.environ.setdefault("OMP_NUM_THREADS", str(cpu_count))
        os.environ.setdefault("OPENBLAS_NUM_THREADS", str(cpu_count))

        # Enable ARM NEON if available
        os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "1")

        # Set up Edge TPU environment if available
        if self.has_coral_tpu():
            os.environ.setdefault("CORAL_VISIBLE_DEVICES", "0")

        logger.info("Raspberry Pi environment configured")

    def optimize_model(
        self,
        model_path: str,
        output_path: str,
        target: str = "tflite",
        quantize: bool = True,
        **kwargs,
    ) -> str | None:
        """
        Optimize model for Raspberry Pi.

        Args:
            model_path: Path to original model
            output_path: Path to save optimized model
            target: Target format ("tflite", "edgetpu", "hailo")
            quantize: Apply INT8 quantization

        Returns:
            Path to optimized model
        """
        if target == "tflite":
            return self._convert_to_tflite(model_path, output_path, quantize)
        elif target == "edgetpu" and self.has_coral_tpu():
            return self._convert_for_edgetpu(model_path, output_path)
        elif target == "hailo" and self.has_hailo():
            return self._convert_for_hailo(model_path, output_path)

        return None

    def _convert_to_tflite(self, model_path: str, output_path: str, quantize: bool) -> str | None:
        """Convert model to TensorFlow Lite format."""
        try:
            if model_path.endswith(".pt"):
                # YOLO to TFLite
                from ultralytics import YOLO

                model = YOLO(model_path)
                model.export(format="tflite", int8=quantize)

                expected_path = model_path.replace(".pt", ".tflite")
                if os.path.exists(expected_path):
                    if expected_path != output_path:
                        os.rename(expected_path, output_path)
                    return output_path

            elif model_path.endswith((".pb", ".h5", ".keras")):
                # TensorFlow model to TFLite
                import tensorflow as tf

                converter = tf.lite.TFLiteConverter.from_saved_model(model_path)

                if quantize:
                    converter.optimizations = [tf.lite.Optimize.DEFAULT]
                    converter.target_spec.supported_types = [tf.int8]

                tflite_model = converter.convert()

                with open(output_path, "wb") as f:
                    f.write(tflite_model)

                return output_path

        except Exception as e:
            logger.error(f"TFLite conversion failed: {e}")

        return None

    def _convert_for_edgetpu(self, model_path: str, output_path: str) -> str | None:
        """Compile model for Edge TPU."""
        try:
            # First convert to TFLite with full integer quantization
            tflite_path = output_path.replace("_edgetpu.tflite", ".tflite")
            if not tflite_path.endswith(".tflite"):
                tflite_path = output_path.replace(".tflite", "_full.tflite")

            self._convert_to_tflite(model_path, tflite_path, quantize=True)

            # Compile with Edge TPU compiler
            result = subprocess.run(
                ["edgetpu_compiler", "-s", "-o", os.path.dirname(output_path), tflite_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode == 0:
                compiled_path = tflite_path.replace(".tflite", "_edgetpu.tflite")
                if os.path.exists(compiled_path):
                    if compiled_path != output_path:
                        os.rename(compiled_path, output_path)
                    return output_path
            else:
                logger.error(f"Edge TPU compilation failed: {result.stderr}")

        except Exception as e:
            logger.error(f"Edge TPU compilation failed: {e}")

        return None

    def _convert_for_hailo(self, model_path: str, output_path: str) -> str | None:
        """Compile model for Hailo accelerator."""
        try:
            # Hailo compilation requires their Dataflow Compiler (DFC)
            # This is typically done offline, but we can attempt it

            if model_path.endswith(".onnx"):
                # Use Hailo Model Zoo or custom compilation
                result = subprocess.run(
                    [
                        "hailo",
                        "compiler",
                        model_path,
                        "--output",
                        output_path,
                        "--target",
                        "hailo8",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                if result.returncode == 0:
                    return output_path
                else:
                    logger.error(f"Hailo compilation failed: {result.stderr}")
            else:
                logger.warning("Hailo compilation requires ONNX model")

        except Exception as e:
            logger.error(f"Hailo compilation failed: {e}")

        return None


class CoralTPUBackend(AcceleratorBackend):
    """
    Backend specifically for Google Coral Edge TPU.

    Can be used standalone or with Raspberry Pi.
    """

    accelerator_type = HardwareAccelerator.CORAL_TPU

    def is_available(self) -> bool:
        """Check if Coral TPU is available."""
        try:
            # Check USB device
            result = subprocess.run(["lsusb"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "18d1:9302" in result.stdout:
                return True

            # Check runtime
            try:
                from pycoral.utils import edgetpu

                devices = edgetpu.list_edge_tpus()
                return len(devices) > 0
            except ImportError:
                pass

        except Exception:
            pass
        return False

    def get_device_info(self) -> DeviceInfo:
        """Get Coral TPU device information."""
        if not self.is_available():
            return DeviceInfo(
                name="Coral TPU (unavailable)",
                accelerator_type=HardwareAccelerator.CORAL_TPU,
                is_available=False,
            )

        try:
            from pycoral.utils import edgetpu

            devices = edgetpu.list_edge_tpus()
            device_type = devices[0] if devices else "unknown"
        except Exception:
            device_type = "Edge TPU"

        return DeviceInfo(
            name=f"Google Coral {device_type}",
            accelerator_type=HardwareAccelerator.CORAL_TPU,
            is_available=True,
            metadata={
                "type": device_type,
                "runtime": "pycoral",
            },
        )

    def get_device_count(self) -> int:
        """Get number of Coral TPU devices."""
        try:
            from pycoral.utils import edgetpu

            return len(edgetpu.list_edge_tpus())
        except Exception:
            return 0


class HailoBackend(AcceleratorBackend):
    """
    Backend for Hailo AI accelerators (Hailo-8, Hailo-8L).
    """

    accelerator_type = HardwareAccelerator.HAILO

    def is_available(self) -> bool:
        """Check if Hailo accelerator is available."""
        try:
            result = subprocess.run(
                ["hailortcli", "fw-control", "identify"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return result.returncode == 0
        except Exception:
            pass

        return os.path.exists("/dev/hailo0")

    def get_device_info(self) -> DeviceInfo:
        """Get Hailo device information."""
        if not self.is_available():
            return DeviceInfo(
                name="Hailo (unavailable)",
                accelerator_type=HardwareAccelerator.HAILO,
                is_available=False,
            )

        try:
            result = subprocess.run(
                ["hailortcli", "fw-control", "identify"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            device_name = "Hailo-8"
            if "hailo8l" in result.stdout.lower():
                device_name = "Hailo-8L"
        except Exception:
            device_name = "Hailo"

        return DeviceInfo(
            name=device_name,
            accelerator_type=HardwareAccelerator.HAILO,
            is_available=True,
            metadata={
                "driver": "hailort",
            },
        )

    def get_device_count(self) -> int:
        """Get number of Hailo devices."""
        count = 0
        for i in range(4):  # Check up to 4 devices
            if os.path.exists(f"/dev/hailo{i}"):
                count += 1
        return count
        if os.path.exists(f"/dev/hailo{i}"):
            count += 1
        return count
