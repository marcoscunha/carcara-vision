"""
Hardware Detection Service.

Comprehensive hardware detection for CPU, platform, and AI accelerators.
"""

import logging
import os
import platform
import re
import subprocess
import time
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from ..schemas.hardware import AcceleratorInfo
from ..schemas.hardware import AcceleratorStatus
from ..schemas.hardware import AcceleratorType
from ..schemas.hardware import CPUArchitecture
from ..schemas.hardware import CPUInfo
from ..schemas.hardware import HardwareDetectionResult
from ..schemas.hardware import MemoryInfo
from ..schemas.hardware import PlatformInfo
from ..schemas.hardware import PlatformVendor

logger = logging.getLogger(__name__)


class HardwareDetectionService:
    """
    Comprehensive hardware detection service.

    Detects:
    - CPU architecture and capabilities
    - Platform/board vendor (Intel, AMD, Raspberry Pi, Orange Pi, Aetina, etc.)
    - AI accelerators (NVIDIA, Hailo, Coral, Axelera, etc.)
    """

    def __init__(self):
        self._cache: Optional[HardwareDetectionResult] = None
        self._cache_time: Optional[float] = None
        self._cache_ttl = 300  # 5 minutes

    def detect_all(self, force_refresh: bool = False) -> HardwareDetectionResult:
        """
        Run complete hardware detection.

        Args:
            force_refresh: Bypass cache and force re-detection

        Returns:
            HardwareDetectionResult with all hardware information
        """
        # Check cache
        if not force_refresh and self._cache and self._cache_time:
            if time.time() - self._cache_time < self._cache_ttl:
                return self._cache

        start_time = time.time()

        cpu_info = self._detect_cpu()
        memory_info = self._detect_memory()
        platform_info = self._detect_platform()
        accelerators = self._detect_accelerators()

        # Determine recommended accelerator
        recommended = self._get_recommended_accelerator(accelerators)

        detection_duration = (time.time() - start_time) * 1000

        result = HardwareDetectionResult(
            cpu=cpu_info,
            memory=memory_info,
            platform=platform_info,
            accelerators=accelerators,
            recommended_accelerator=recommended,
            detection_timestamp=datetime.now(timezone.utc).isoformat(),
            detection_duration_ms=round(detection_duration, 2),
        )

        # Update cache
        self._cache = result
        self._cache_time = time.time()

        return result

    # =========================================================================
    # CPU Detection
    # =========================================================================

    def _detect_cpu(self) -> CPUInfo:
        """Detect CPU information."""
        machine = platform.machine().lower()

        # Determine architecture
        arch_map = {
            "x86_64": CPUArchitecture.X86_64,
            "amd64": CPUArchitecture.X86_64,
            "i386": CPUArchitecture.X86,
            "i686": CPUArchitecture.X86,
            "aarch64": CPUArchitecture.ARM64,
            "arm64": CPUArchitecture.ARM64,
            "armv7l": CPUArchitecture.ARMV7,
            "armv8l": CPUArchitecture.ARMV8,
        }
        architecture = arch_map.get(machine, CPUArchitecture.UNKNOWN)

        # Get detailed CPU info from /proc/cpuinfo (Linux)
        model_name = "Unknown"
        vendor = "Unknown"
        cores = os.cpu_count() or 0
        threads = cores
        features: List[str] = []
        max_freq: Optional[float] = None

        try:
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    content = f.read()

                # Model name
                match = re.search(r"model name\s*:\s*(.+)", content)
                if match:
                    model_name = match.group(1).strip()

                # Vendor
                match = re.search(r"vendor_id\s*:\s*(.+)", content)
                if match:
                    vendor = match.group(1).strip()
                elif "Hardware" in content:
                    # ARM devices often have Hardware field
                    match = re.search(r"Hardware\s*:\s*(.+)", content)
                    if match:
                        vendor = match.group(1).strip()

                # CPU cores (physical)
                physical_cores = len(re.findall(r"^processor\s*:", content, re.MULTILINE))
                if physical_cores > 0:
                    threads = physical_cores

                # Core ids for actual core count
                core_ids = set(re.findall(r"core id\s*:\s*(\d+)", content))
                if core_ids:
                    cpu_ids = set(re.findall(r"physical id\s*:\s*(\d+)", content))
                    cores = len(core_ids) * max(len(cpu_ids), 1)
                else:
                    cores = threads

                # CPU features/flags
                match = re.search(r"flags\s*:\s*(.+)", content)
                if match:
                    features = match.group(1).strip().split()
                elif "Features" in content:
                    # ARM uses "Features"
                    match = re.search(r"Features\s*:\s*(.+)", content)
                    if match:
                        features = match.group(1).strip().split()

        except Exception as e:
            logger.warning(f"Error reading /proc/cpuinfo: {e}")

        # Try to get max frequency
        try:
            freq_path = "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
            if os.path.exists(freq_path):
                with open(freq_path, "r") as f:
                    max_freq = float(f.read().strip()) / 1000  # Convert kHz to MHz
        except Exception:
            pass

        return CPUInfo(
            architecture=architecture,
            model_name=model_name,
            vendor=vendor,
            cores=cores,
            threads=threads,
            max_frequency_mhz=max_freq,
            features=features[:50],  # Limit to 50 most relevant features
        )

    # =========================================================================
    # Memory Detection
    # =========================================================================

    def _detect_memory(self) -> MemoryInfo:
        """Detect system memory information."""
        total_gb = 0.0
        available_gb = 0.0

        try:
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo", "r") as f:
                    content = f.read()

                match = re.search(r"MemTotal:\s*(\d+)\s*kB", content)
                if match:
                    total_gb = int(match.group(1)) / (1024 * 1024)

                match = re.search(r"MemAvailable:\s*(\d+)\s*kB", content)
                if match:
                    available_gb = int(match.group(1)) / (1024 * 1024)

        except Exception as e:
            logger.warning(f"Error reading memory info: {e}")

        used_percent = ((total_gb - available_gb) / total_gb * 100) if total_gb > 0 else 0

        return MemoryInfo(
            total_gb=round(total_gb, 2),
            available_gb=round(available_gb, 2),
            used_percent=round(used_percent, 1),
        )

    # =========================================================================
    # Platform Detection
    # =========================================================================

    def _detect_platform(self) -> PlatformInfo:
        """Detect platform/board vendor and information."""
        vendor = PlatformVendor.UNKNOWN
        board_name = "Unknown"
        board_model = None
        serial_number = None

        # OS information
        os_name = "Unknown"
        os_version = "Unknown"
        kernel_version = platform.release()

        try:
            # Try to get OS info
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    content = f.read()
                match = re.search(r'NAME="?([^"\n]+)"?', content)
                if match:
                    os_name = match.group(1)
                match = re.search(r'VERSION_ID="?([^"\n]+)"?', content)
                if match:
                    os_version = match.group(1)
        except Exception:
            pass

        # Detect specific platforms
        vendor, board_name, board_model = self._identify_platform_vendor()

        # Try to get serial number
        try:
            if os.path.exists("/proc/device-tree/serial-number"):
                with open("/proc/device-tree/serial-number", "r") as f:
                    serial_number = f.read().strip().rstrip('\x00')
            elif os.path.exists("/sys/class/dmi/id/product_serial"):
                with open("/sys/class/dmi/id/product_serial", "r") as f:
                    serial_number = f.read().strip()
        except Exception:
            pass

        return PlatformInfo(
            vendor=vendor,
            board_name=board_name,
            board_model=board_model,
            serial_number=serial_number,
            os_name=os_name,
            os_version=os_version,
            kernel_version=kernel_version,
        )

    def _identify_platform_vendor(self) -> Tuple[PlatformVendor, str, Optional[str]]:
        """Identify the platform vendor and board information."""

        # Check for Raspberry Pi
        if self._is_raspberry_pi():
            model = self._get_raspberry_pi_model()
            return PlatformVendor.RASPBERRY_PI, model or "Raspberry Pi", model

        # Check for NVIDIA Jetson
        if self._is_jetson():
            model = self._get_jetson_model()
            return PlatformVendor.NVIDIA_JETSON, model or "NVIDIA Jetson", model

        # Check for Orange Pi
        if self._is_orange_pi():
            model = self._get_orange_pi_model()
            return PlatformVendor.ORANGE_PI, model or "Orange Pi", model

        # Check for Aetina
        if self._is_aetina():
            model = self._get_aetina_model()
            return PlatformVendor.AETINA, model or "Aetina", model

        # Check for Rock Pi
        if self._is_rock_pi():
            return PlatformVendor.ROCK_PI, "Rock Pi", None

        # Check for Khadas
        if self._is_khadas():
            return PlatformVendor.KHADAS, "Khadas", None

        # Check CPU vendor for x86 systems
        try:
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    content = f.read().lower()

                if "genuineintel" in content:
                    return PlatformVendor.INTEL, "Intel x86_64", None
                elif "authenticamd" in content or "amd" in content:
                    return PlatformVendor.AMD, "AMD x86_64", None
        except Exception:
            pass

        # Check architecture for generic classification
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64", "i386", "i686"):
            return PlatformVendor.GENERIC_X86, "Generic x86", None
        elif "arm" in machine or "aarch" in machine:
            return PlatformVendor.GENERIC_ARM, "Generic ARM", None

        return PlatformVendor.UNKNOWN, "Unknown Platform", None

    def _is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                    if "raspberry pi" in model:
                        return True
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    content = f.read().lower()
                    if "raspberry" in content or "bcm2" in content:
                        return True
        except Exception:
            pass
        return False

    def _get_raspberry_pi_model(self) -> Optional[str]:
        """Get Raspberry Pi model name."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    return f.read().strip().rstrip('\x00')
        except Exception:
            pass
        return None

    def _is_jetson(self) -> bool:
        """Check if running on NVIDIA Jetson."""
        try:
            if os.path.exists("/etc/nv_tegra_release"):
                return True
            if os.path.exists("/proc/device-tree/compatible"):
                with open("/proc/device-tree/compatible", "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    if "nvidia,tegra" in content.lower():
                        return True
        except Exception:
            pass
        return False

    def _get_jetson_model(self) -> Optional[str]:
        """Get Jetson model name."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    return f.read().strip().rstrip('\x00')
        except Exception:
            pass
        return None

    def _is_orange_pi(self) -> bool:
        """Check if running on Orange Pi."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                    if "orange pi" in model or "orangepi" in model:
                        return True
            # Check for Allwinner/Rockchip with Orange Pi branding
            if os.path.exists("/etc/orangepi-release"):
                return True
        except Exception:
            pass
        return False

    def _get_orange_pi_model(self) -> Optional[str]:
        """Get Orange Pi model name."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    return f.read().strip().rstrip('\x00')
        except Exception:
            pass
        return None

    def _is_aetina(self) -> bool:
        """Check if running on Aetina platform."""
        try:
            # Aetina often uses Jetson modules with custom carriers
            result = subprocess.run(
                ["dmidecode", "-s", "system-manufacturer"],
                capture_output=True, text=True, timeout=5
            )
            if "aetina" in result.stdout.lower():
                return True
            # Check for Aetina-specific files
            if os.path.exists("/etc/aetina-release"):
                return True
        except Exception:
            pass
        return False

    def _get_aetina_model(self) -> Optional[str]:
        """Get Aetina model name."""
        try:
            result = subprocess.run(
                ["dmidecode", "-s", "system-product-name"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _is_rock_pi(self) -> bool:
        """Check if running on Rock Pi."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                    if "rock pi" in model or "rockpi" in model:
                        return True
        except Exception:
            pass
        return False

    def _is_khadas(self) -> bool:
        """Check if running on Khadas board."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    model = f.read().lower()
                    if "khadas" in model:
                        return True
        except Exception:
            pass
        return False

    # =========================================================================
    # Accelerator Detection
    # =========================================================================

    def _detect_accelerators(self) -> List[AcceleratorInfo]:
        """Detect all available hardware accelerators."""
        accelerators: List[AcceleratorInfo] = []

        # NVIDIA GPU detection
        nvidia_gpus = self._detect_nvidia_gpu()
        accelerators.extend(nvidia_gpus)

        # Hailo detection
        hailo_devices = self._detect_hailo()
        accelerators.extend(hailo_devices)

        # Google Coral detection
        coral_devices = self._detect_coral()
        accelerators.extend(coral_devices)

        # Axelera detection
        axelera_devices = self._detect_axelera()
        accelerators.extend(axelera_devices)

        # Intel OpenVINO detection
        openvino = self._detect_openvino()
        if openvino:
            accelerators.append(openvino)

        # AMD ROCm detection
        amd_gpus = self._detect_amd_rocm()
        accelerators.extend(amd_gpus)

        # Always add CPU as fallback
        accelerators.append(AcceleratorInfo(
            type=AcceleratorType.CPU,
            name="CPU",
            status=AcceleratorStatus.AVAILABLE,
            details={"info": "Default CPU inference backend"},
        ))

        return accelerators

    def _detect_nvidia_gpu(self) -> List[AcceleratorInfo]:
        """Detect NVIDIA GPUs using multiple methods."""
        gpus: List[AcceleratorInfo] = []

        # Method 1: nvidia-smi (most reliable when available)
        gpus = self._detect_nvidia_via_smi()
        if gpus:
            return gpus

        # Method 2: Check via lspci for NVIDIA devices
        gpus = self._detect_nvidia_via_lspci()
        if gpus:
            return gpus

        # Method 3: Check CUDA availability via Python
        gpus = self._detect_nvidia_via_cuda()
        if gpus:
            return gpus

        # Method 4: Check /proc/driver/nvidia
        gpus = self._detect_nvidia_via_proc()
        if gpus:
            return gpus

        return gpus

    def _detect_nvidia_via_smi(self) -> List[AcceleratorInfo]:
        """Detect NVIDIA GPUs via nvidia-smi."""
        gpus: List[AcceleratorInfo] = []

        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,pci.bus_id,compute_cap",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 5:
                            name, memory, driver, pcie, compute_cap = parts[:5]

                            # Check if TensorRT is available
                            tensorrt_available = self._check_tensorrt()

                            gpus.append(AcceleratorInfo(
                                type=AcceleratorType.NVIDIA_GPU,
                                name=name,
                                status=AcceleratorStatus.AVAILABLE,
                                driver_version=driver,
                                memory_mb=int(float(memory)) if memory else None,
                                compute_capability=compute_cap,
                                pcie_address=pcie,
                                details={
                                    "tensorrt_available": tensorrt_available,
                                    "detection_method": "nvidia-smi",
                                },
                            ))

                            # Add TensorRT as separate accelerator if available
                            if tensorrt_available:
                                gpus.append(AcceleratorInfo(
                                    type=AcceleratorType.NVIDIA_TENSORRT,
                                    name=f"TensorRT on {name}",
                                    status=AcceleratorStatus.AVAILABLE,
                                    driver_version=driver,
                                    memory_mb=int(float(memory)) if memory else None,
                                    details={"gpu_name": name},
                                ))

        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"nvidia-smi detection failed: {e}")

        return gpus

    def _detect_nvidia_via_lspci(self) -> List[AcceleratorInfo]:
        """Detect NVIDIA GPUs via lspci."""
        gpus: List[AcceleratorInfo] = []

        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    # Look for NVIDIA VGA or 3D controllers
                    if "nvidia" in line.lower() and ("vga" in line.lower() or "3d" in line.lower()):
                        # Extract PCI address and device name
                        parts = line.split(" ", 1)
                        pcie_addr = parts[0] if parts else None

                        # Extract GPU name from between brackets or from description
                        name_match = re.search(r"NVIDIA[^[]*\[([^\]]+)\]", line, re.IGNORECASE)
                        if name_match:
                            name = f"NVIDIA {name_match.group(1)}"
                        else:
                            name_match = re.search(r"NVIDIA\s+([^[]+)", line, re.IGNORECASE)
                            name = f"NVIDIA {name_match.group(1).strip()}" if name_match else "NVIDIA GPU"

                        # Check if driver is loaded
                        driver_loaded = self._check_nvidia_driver_loaded()

                        gpus.append(AcceleratorInfo(
                            type=AcceleratorType.NVIDIA_GPU,
                            name=name,
                            status=AcceleratorStatus.AVAILABLE if driver_loaded else AcceleratorStatus.DRIVER_MISSING,
                            pcie_address=pcie_addr,
                            details={
                                "detection_method": "lspci",
                                "driver_loaded": driver_loaded,
                                "raw_info": line.strip(),
                            },
                        ))

        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"lspci NVIDIA detection failed: {e}")

        return gpus

    def _detect_nvidia_via_cuda(self) -> List[AcceleratorInfo]:
        """Detect NVIDIA GPUs via CUDA Python bindings."""
        gpus: List[AcceleratorInfo] = []

        # Try torch first (commonly available)
        try:
            import torch
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpus.append(AcceleratorInfo(
                        type=AcceleratorType.NVIDIA_GPU,
                        name=props.name,
                        status=AcceleratorStatus.AVAILABLE,
                        memory_mb=props.total_memory // (1024 * 1024),
                        compute_capability=f"{props.major}.{props.minor}",
                        details={
                            "detection_method": "torch.cuda",
                            "multi_processor_count": props.multi_processor_count,
                        },
                    ))
                if gpus:
                    return gpus
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"torch.cuda detection failed: {e}")

        # Try pycuda
        try:
            import pycuda.autoinit  # noqa: F401
            import pycuda.driver as cuda
            for i in range(cuda.Device.count()):
                dev = cuda.Device(i)
                gpus.append(AcceleratorInfo(
                    type=AcceleratorType.NVIDIA_GPU,
                    name=dev.name(),
                    status=AcceleratorStatus.AVAILABLE,
                    memory_mb=dev.total_memory() // (1024 * 1024),
                    compute_capability=f"{dev.compute_capability()[0]}.{dev.compute_capability()[1]}",
                    details={
                        "detection_method": "pycuda",
                    },
                ))
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pycuda detection failed: {e}")

        return gpus

    def _detect_nvidia_via_proc(self) -> List[AcceleratorInfo]:
        """Detect NVIDIA GPUs via /proc filesystem."""
        gpus: List[AcceleratorInfo] = []

        # Check /proc/driver/nvidia/gpus/
        nvidia_gpus_path = "/proc/driver/nvidia/gpus"
        if os.path.exists(nvidia_gpus_path):
            try:
                for gpu_dir in os.listdir(nvidia_gpus_path):
                    info_path = os.path.join(nvidia_gpus_path, gpu_dir, "information")
                    if os.path.exists(info_path):
                        with open(info_path, "r") as f:
                            content = f.read()

                        name = "NVIDIA GPU"
                        for line in content.split("\n"):
                            if line.startswith("Model:"):
                                name = line.split(":", 1)[1].strip()
                                break

                        gpus.append(AcceleratorInfo(
                            type=AcceleratorType.NVIDIA_GPU,
                            name=name,
                            status=AcceleratorStatus.AVAILABLE,
                            pcie_address=gpu_dir,
                            details={
                                "detection_method": "/proc/driver/nvidia",
                            },
                        ))
            except Exception as e:
                logger.debug(f"/proc NVIDIA detection failed: {e}")

        # Also check /dev/nvidia* devices
        if not gpus:
            nvidia_devices = [d for d in os.listdir("/dev") if d.startswith("nvidia")
                              and d != "nvidiactl" and d != "nvidia-uvm"]
            for dev in nvidia_devices:
                if dev.startswith("nvidia") and dev[6:].isdigit():
                    gpus.append(AcceleratorInfo(
                        type=AcceleratorType.NVIDIA_GPU,
                        name=f"NVIDIA GPU {dev[6:]}",
                        status=AcceleratorStatus.AVAILABLE,
                        device_path=f"/dev/{dev}",
                        details={
                            "detection_method": "/dev device",
                        },
                    ))

        return gpus

    def _check_nvidia_driver_loaded(self) -> bool:
        """Check if NVIDIA driver is loaded in kernel."""
        try:
            result = subprocess.run(
                ["lsmod"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "nvidia" in result.stdout.lower()
        except Exception:
            pass

        # Also check /proc/modules
        try:
            with open("/proc/modules", "r") as f:
                content = f.read().lower()
                return "nvidia" in content
        except Exception:
            pass

        return False

    def _check_tensorrt(self) -> bool:
        """Check if TensorRT is available."""
        try:
            import tensorrt
            return True
        except ImportError:
            pass

        # Check for trtexec
        try:
            result = subprocess.run(["which", "trtexec"], capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            pass

        return False

    def _detect_hailo(self) -> List[AcceleratorInfo]:
        """Detect Hailo AI accelerators (Hailo-8, Hailo-8L, Hailo-10)."""
        devices: List[AcceleratorInfo] = []

        try:
            # Try hailortcli
            result = subprocess.run(
                ["hailortcli", "fw-control", "identify"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                output = result.stdout

                # Parse Hailo device info
                device_type = AcceleratorType.HAILO_8  # Default
                name = "Hailo-8"
                fw_version = None

                # Detect specific model
                if "hailo-8l" in output.lower() or "8l" in output.lower():
                    device_type = AcceleratorType.HAILO_8L
                    name = "Hailo-8L"
                elif "hailo-10" in output.lower() or "h10" in output.lower():
                    device_type = AcceleratorType.HAILO_10
                    name = "Hailo-10"

                # Extract firmware version
                match = re.search(r"firmware version[:\s]+([^\s\n]+)", output, re.IGNORECASE)
                if match:
                    fw_version = match.group(1)

                devices.append(AcceleratorInfo(
                    type=device_type,
                    name=name,
                    status=AcceleratorStatus.AVAILABLE,
                    firmware_version=fw_version,
                    details={"raw_output": output[:500]},
                ))
        except FileNotFoundError:
            # hailortcli not installed - check for PCIe devices
            try:
                result = subprocess.run(
                    ["lspci", "-d", "1e60:"],  # Hailo vendor ID
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    devices.append(AcceleratorInfo(
                        type=AcceleratorType.HAILO_8,
                        name="Hailo Device (driver not installed)",
                        status=AcceleratorStatus.DRIVER_MISSING,
                        details={"pcie_info": result.stdout.strip()},
                    ))
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error detecting Hailo: {e}")

        return devices

    def _detect_coral(self) -> List[AcceleratorInfo]:
        """Detect Google Coral Edge TPU devices."""
        devices: List[AcceleratorInfo] = []

        # Check for USB Coral
        try:
            result = subprocess.run(
                ["lsusb", "-d", "1a6e:089a"],  # Coral USB Accelerator
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                devices.append(AcceleratorInfo(
                    type=AcceleratorType.GOOGLE_CORAL_USB,
                    name="Google Coral USB Accelerator",
                    status=AcceleratorStatus.AVAILABLE,
                    details={"usb_info": result.stdout.strip()},
                ))
        except Exception:
            pass

        # Check for PCIe/M.2 Coral
        try:
            result = subprocess.run(
                ["lspci", "-d", "1ac1:089a"],  # Coral PCIe
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                devices.append(AcceleratorInfo(
                    type=AcceleratorType.GOOGLE_CORAL_PCIE,
                    name="Google Coral PCIe/M.2 Accelerator",
                    status=AcceleratorStatus.AVAILABLE,
                    details={"pcie_info": result.stdout.strip()},
                ))
        except Exception:
            pass

        # Verify Edge TPU runtime is installed
        if devices:
            try:
                result = subprocess.run(
                    ["dpkg", "-l", "libedgetpu1-std"],
                    capture_output=True, text=True, timeout=5
                )
                runtime_installed = result.returncode == 0
                for device in devices:
                    device.details["runtime_installed"] = runtime_installed
                    if not runtime_installed:
                        device.status = AcceleratorStatus.DRIVER_MISSING
            except Exception:
                pass

        return devices

    def _detect_axelera(self) -> List[AcceleratorInfo]:
        """Detect Axelera AI accelerators."""
        devices: List[AcceleratorInfo] = []

        try:
            # Check for Axelera PCIe device (Metis)
            result = subprocess.run(
                ["lspci"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Look for Axelera in output
                if "axelera" in result.stdout.lower() or "metis" in result.stdout.lower():
                    devices.append(AcceleratorInfo(
                        type=AcceleratorType.AXELERA_M2,
                        name="Axelera Metis AI Accelerator",
                        status=AcceleratorStatus.AVAILABLE,
                    ))

            # Check for axelera-runtime
            result = subprocess.run(
                ["which", "axelera-info"],
                capture_output=True, timeout=5
            )
            if result.returncode == 0:
                # Get device info
                info_result = subprocess.run(
                    ["axelera-info"],
                    capture_output=True, text=True, timeout=10
                )
                if info_result.returncode == 0:
                    devices.append(AcceleratorInfo(
                        type=AcceleratorType.AXELERA_M2,
                        name="Axelera AI Accelerator",
                        status=AcceleratorStatus.AVAILABLE,
                        details={"info": info_result.stdout[:500]},
                    ))
        except Exception as e:
            logger.warning(f"Error detecting Axelera: {e}")

        return devices

    def _detect_openvino(self) -> Optional[AcceleratorInfo]:
        """Detect Intel OpenVINO availability."""
        try:
            import openvino
            return AcceleratorInfo(
                type=AcceleratorType.INTEL_OPENVINO,
                name="Intel OpenVINO",
                status=AcceleratorStatus.AVAILABLE,
                details={"version": getattr(openvino, "__version__", "unknown")},
            )
        except ImportError:
            pass

        # Check for openvino installation
        try:
            result = subprocess.run(
                ["python3", "-c", "import openvino; print(openvino.__version__)"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return AcceleratorInfo(
                    type=AcceleratorType.INTEL_OPENVINO,
                    name="Intel OpenVINO",
                    status=AcceleratorStatus.AVAILABLE,
                    details={"version": result.stdout.strip()},
                )
        except Exception:
            pass

        return None

    def _detect_amd_rocm(self) -> List[AcceleratorInfo]:
        """Detect AMD GPUs with ROCm support."""
        gpus: List[AcceleratorInfo] = []

        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                # Parse ROCm output
                for line in result.stdout.split("\n"):
                    if "GPU" in line and ":" in line:
                        name = line.split(":")[-1].strip()
                        gpus.append(AcceleratorInfo(
                            type=AcceleratorType.AMD_ROCM,
                            name=f"AMD {name}",
                            status=AcceleratorStatus.AVAILABLE,
                        ))
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Error detecting AMD ROCm: {e}")

        return gpus

    # =========================================================================
    # Recommendation Logic
    # =========================================================================

    def _get_recommended_accelerator(
        self,
        accelerators: List[AcceleratorInfo]
    ) -> Optional[AcceleratorType]:
        """Determine the recommended accelerator based on available hardware."""

        # Priority order for recommendation
        priority = [
            AcceleratorType.NVIDIA_TENSORRT,
            AcceleratorType.NVIDIA_GPU,
            AcceleratorType.NVIDIA_JETSON,
            AcceleratorType.HAILO_10,
            AcceleratorType.HAILO_8,
            AcceleratorType.HAILO_8L,
            AcceleratorType.GOOGLE_CORAL_PCIE,
            AcceleratorType.GOOGLE_CORAL_M2,
            AcceleratorType.GOOGLE_CORAL_USB,
            AcceleratorType.AXELERA_M2,
            AcceleratorType.AMD_ROCM,
            AcceleratorType.INTEL_OPENVINO,
            AcceleratorType.CPU,
        ]

        available_types = {
            acc.type for acc in accelerators
            if acc.status == AcceleratorStatus.AVAILABLE
        }

        for acc_type in priority:
            if acc_type in available_types:
                return acc_type

        return AcceleratorType.CPU


# Global service instance
hardware_detection_service = HardwareDetectionService()
