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
from datetime import UTC, datetime

from ..schemas.hardware import (
    AcceleratorInfo,
    AcceleratorStatus,
    AcceleratorType,
    CPUArchitecture,
    CPUInfo,
    HardwareDetectionResult,
    MemoryInfo,
    PlatformInfo,
    PlatformVendor,
)

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
        self._cache: HardwareDetectionResult | None = None
        self._cache_time: float | None = None
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
            detection_timestamp=datetime.now(UTC).isoformat(),
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
        features: list[str] = []
        max_freq: float | None = None
        cpu_implementer: str | None = None
        cpu_part: str | None = None

        try:
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo") as f:
                    content = f.read()

                # Model name (x86 / some ARM kernels)
                match = re.search(r"model name\s*:\s*(.+)", content)
                if match:
                    model_name = match.group(1).strip()

                # Vendor (x86)
                match = re.search(r"vendor_id\s*:\s*(.+)", content)
                if match:
                    vendor = match.group(1).strip()

                # ARM-specific fields (no vendor_id on aarch64)
                impl_match = re.search(r"CPU implementer\s*:\s*(0x[0-9a-fA-F]+)", content)
                if impl_match:
                    cpu_implementer = impl_match.group(1).lower()
                part_match = re.search(r"CPU part\s*:\s*(0x[0-9a-fA-F]+)", content)
                if part_match:
                    cpu_part = part_match.group(1).lower()

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

        # ----- ARM / Jetson vendor & model resolution -----
        # On ARM there is no vendor_id; resolve via CPU implementer/part codes
        # and refine with Jetson-specific SoC info when applicable.
        if architecture in (CPUArchitecture.ARM64, CPUArchitecture.ARMV7, CPUArchitecture.ARMV8):
            arm_vendor, arm_core = self._resolve_arm_cpu(cpu_implementer, cpu_part)
            if vendor == "Unknown" and arm_vendor:
                vendor = arm_vendor
            if model_name == "Unknown" and arm_core:
                model_name = arm_core

            # If we're on a Jetson, the SoC is designed and integrated by
            # NVIDIA even when the ARM cores carry an "Arm Limited" implementer
            # code (0x41). Report NVIDIA as the vendor and annotate the model
            # with the SoC + Jetson module name.
            if self._is_jetson():
                vendor = "NVIDIA"
                soc = self._get_jetson_soc()  # e.g. "Tegra T234 (Orin)"
                jetson_model = self._get_jetson_model()
                parts = [p for p in [arm_core, soc, jetson_model] if p]
                if parts:
                    # Example: "8x Arm Cortex-A78AE • NVIDIA Tegra T234 (Orin) • NVIDIA Jetson Orin Nano"
                    core_label = f"{threads}x {arm_core}" if arm_core and threads else arm_core
                    pieces: list[str] = []
                    if core_label:
                        pieces.append(core_label)
                    if soc:
                        pieces.append(soc)
                    if jetson_model and (not soc or jetson_model.lower() not in soc.lower()):
                        pieces.append(jetson_model)
                    model_name = " • ".join(pieces)

        # Try to get max frequency
        try:
            freq_path = "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq"
            if os.path.exists(freq_path):
                with open(freq_path) as f:
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
    # ARM CPU resolution helpers
    # =========================================================================

    # CPU implementer codes (from Linux arch/arm64/include/asm/cputype.h)
    _ARM_IMPLEMENTERS: dict[str, str] = {
        "0x41": "Arm Limited",
        "0x42": "Broadcom",
        "0x43": "Cavium",
        "0x44": "DEC",
        "0x46": "Fujitsu",
        "0x48": "HiSilicon",
        "0x49": "Infineon",
        "0x4d": "Motorola/Freescale",
        "0x4e": "NVIDIA",
        "0x50": "Applied Micro (APM)",
        "0x51": "Qualcomm",
        "0x53": "Samsung",
        "0x56": "Marvell",
        "0x61": "Apple",
        "0x66": "Faraday",
        "0x69": "Intel",
        "0x70": "Phytium",
        "0xc0": "Ampere Computing",
    }

    # CPU part codes for ARM Limited implementer (0x41) — common cores.
    _ARM_PARTS_ARM: dict[str, str] = {
        "0xd03": "Arm Cortex-A53",
        "0xd05": "Arm Cortex-A55",
        "0xd07": "Arm Cortex-A57",
        "0xd08": "Arm Cortex-A72",
        "0xd09": "Arm Cortex-A73",
        "0xd0a": "Arm Cortex-A75",
        "0xd0b": "Arm Cortex-A76",
        "0xd0c": "Arm Neoverse-N1",
        "0xd0d": "Arm Cortex-A77",
        "0xd40": "Arm Neoverse-V1",
        "0xd41": "Arm Cortex-A78",
        "0xd42": "Arm Cortex-A78AE",   # Jetson Orin
        "0xd44": "Arm Cortex-X1",
        "0xd46": "Arm Cortex-A510",
        "0xd47": "Arm Cortex-A710",
        "0xd48": "Arm Cortex-X2",
        "0xd49": "Arm Neoverse-N2",
        "0xd4a": "Arm Neoverse-E1",
        "0xd4b": "Arm Cortex-A78C",
    }

    # NVIDIA custom ARM cores (implementer 0x4e).
    _ARM_PARTS_NVIDIA: dict[str, str] = {
        "0x000": "NVIDIA Denver",
        "0x003": "NVIDIA Denver 2",
        "0x004": "NVIDIA Carmel",      # Jetson Xavier
    }

    def _resolve_arm_cpu(
        self, implementer: str | None, part: str | None
    ) -> tuple[str | None, str | None]:
        """Resolve ARM CPU implementer + part codes to human-readable strings."""
        vendor = self._ARM_IMPLEMENTERS.get(implementer) if implementer else None
        core: str | None = None
        if part:
            if implementer == "0x4e":
                core = self._ARM_PARTS_NVIDIA.get(part)
            else:
                core = self._ARM_PARTS_ARM.get(part)
            if not core:
                core = f"ARM core {part}"
        return vendor, core

    def _get_jetson_soc(self) -> str | None:
        """
        Identify the Tegra SoC powering a Jetson board.

        Sources (in order):
        - /sys/devices/soc0/family + /sys/devices/soc0/machine
        - /proc/device-tree/compatible (e.g. "nvidia,tegra234")
        """
        try:
            family = None
            for p in ("/sys/devices/soc0/family", "/sys/devices/soc0/soc_id"):
                if os.path.exists(p):
                    with open(p) as f:
                        family = f.read().strip().rstrip("\x00")
                    if family:
                        break
            if family and family.lower().startswith("tegra"):
                # family is usually like "tegra234"
                code = family.lower().replace("tegra", "").strip()
                soc_map = {
                    "186": "Tegra T186 (Parker)",   # TX2
                    "194": "Tegra T194 (Xavier)",   # Xavier NX / AGX
                    "234": "Tegra T234 (Orin)",     # Orin Nano / NX / AGX
                    "210": "Tegra T210 (Erista)",   # Nano / TX1
                }
                return f"NVIDIA {soc_map.get(code, family.capitalize())}"

            if os.path.exists("/proc/device-tree/compatible"):
                with open("/proc/device-tree/compatible", "rb") as f:
                    compat = f.read().decode("utf-8", errors="ignore").lower()
                if "tegra234" in compat:
                    return "NVIDIA Tegra T234 (Orin)"
                if "tegra194" in compat:
                    return "NVIDIA Tegra T194 (Xavier)"
                if "tegra186" in compat:
                    return "NVIDIA Tegra T186 (Parker)"
                if "tegra210" in compat:
                    return "NVIDIA Tegra T210 (Erista)"
        except Exception:
            pass
        return None

    # =========================================================================
    # Memory Detection
    # =========================================================================

    def _detect_memory(self) -> MemoryInfo:
        """Detect system memory information."""
        total_gb = 0.0
        available_gb = 0.0

        try:
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo") as f:
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

        kernel_version = platform.release()

        # Detect container vs host OS separately so the UI can show both.
        container_os_name, container_os_version = self._read_os_release("/etc/os-release")
        host_os_name, host_os_version = self._read_os_release("/host/etc/os-release")

        is_containerized = self._is_running_in_container()
        # If the host-mounted file is missing but we are clearly not in a
        # container, the "container" OS *is* the host OS.
        if not host_os_name and not is_containerized:
            host_os_name = container_os_name
            host_os_version = container_os_version
            container_os_name = None
            container_os_version = None

        # L4T (Linux for Tegra) info — only meaningful on Jetson hosts.
        l4t_version: str | None = None
        try:
            for path in ("/host/etc/nv_tegra_release", "/etc/nv_tegra_release"):
                if os.path.exists(path):
                    with open(path) as f:
                        tegra_line = f.readline().strip()
                    # Example: "# R36 (release), REVISION: 4.0, GCID: ..."
                    rev_match = re.search(r"R(\d+).*REVISION:\s*([\d.]+)", tegra_line)
                    if rev_match:
                        l4t_version = f"{rev_match.group(1)}.{rev_match.group(2)}"
                    break
        except Exception:
            pass

        # Pick the "primary" OS shown in os_name/os_version: prefer the host
        # OS when available, otherwise the container OS. On Jetson, annotate
        # with the L4T release.
        primary_name = host_os_name or container_os_name or "Unknown"
        primary_version = host_os_version or container_os_version or "Unknown"
        if l4t_version:
            if "ubuntu" not in primary_name.lower() and host_os_name is None:
                # No host info available; L4T implies Ubuntu-based host.
                primary_name = "Ubuntu (NVIDIA L4T)"
            else:
                primary_name = f"{primary_name} (NVIDIA L4T)"
            primary_version = (
                f"{primary_version} / L4T {l4t_version}"
                if primary_version != "Unknown"
                else f"L4T {l4t_version}"
            )

        # Detect specific platforms
        vendor, board_name, board_model = self._identify_platform_vendor()

        # Try to get serial number
        try:
            if os.path.exists("/proc/device-tree/serial-number"):
                with open("/proc/device-tree/serial-number") as f:
                    serial_number = f.read().strip().rstrip("\x00")
            elif os.path.exists("/sys/class/dmi/id/product_serial"):
                with open("/sys/class/dmi/id/product_serial") as f:
                    serial_number = f.read().strip()
        except Exception:
            pass

        return PlatformInfo(
            vendor=vendor,
            board_name=board_name,
            board_model=board_model,
            serial_number=serial_number,
            os_name=primary_name,
            os_version=primary_version,
            kernel_version=kernel_version,
            host_os_name=host_os_name,
            host_os_version=host_os_version,
            container_os_name=container_os_name if is_containerized else None,
            container_os_version=container_os_version if is_containerized else None,
            is_containerized=is_containerized,
            l4t_version=l4t_version,
        )

    def _read_os_release(self, path: str) -> tuple[str | None, str | None]:
        """Parse an os-release file. Returns (name, version) or (None, None)."""
        try:
            if not os.path.exists(path):
                return None, None
            with open(path) as f:
                content = f.read()
            name_match = re.search(r'^NAME="?([^"\n]+?)"?$', content, re.MULTILINE)
            ver_match = re.search(r'^VERSION_ID="?([^"\n]+?)"?$', content, re.MULTILINE)
            name = name_match.group(1) if name_match else None
            version = ver_match.group(1) if ver_match else None
            return name, version
        except Exception:
            return None, None

    def _is_running_in_container(self) -> bool:
        """Best-effort detection of whether we are inside a container."""
        try:
            if os.path.exists("/.dockerenv"):
                return True
            if os.path.exists("/run/.containerenv"):
                return True
            if os.path.exists("/proc/1/cgroup"):
                with open("/proc/1/cgroup") as f:
                    cg = f.read()
                if "docker" in cg or "containerd" in cg or "kubepods" in cg:
                    return True
        except Exception:
            pass
        return False

    def _identify_platform_vendor(self) -> tuple[PlatformVendor, str, str | None]:
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
                with open("/proc/cpuinfo") as f:
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
                with open("/proc/device-tree/model") as f:
                    model = f.read().lower()
                    if "raspberry pi" in model:
                        return True
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo") as f:
                    content = f.read().lower()
                    if "raspberry" in content or "bcm2" in content:
                        return True
        except Exception:
            pass
        return False

    def _get_raspberry_pi_model(self) -> str | None:
        """Get Raspberry Pi model name."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    return f.read().strip().rstrip("\x00")
        except Exception:
            pass
        return None

    def _is_jetson(self) -> bool:
        """Check if running on NVIDIA Jetson."""
        try:
            if os.path.exists("/etc/nv_tegra_release") or os.path.exists("/host/etc/nv_tegra_release"):
                return True
            if os.path.exists("/proc/device-tree/compatible"):
                with open("/proc/device-tree/compatible", "rb") as f:
                    content = f.read().decode("utf-8", errors="ignore")
                    if "nvidia,tegra" in content.lower():
                        return True
        except Exception:
            pass
        return False

    def _get_jetson_model(self) -> str | None:
        """Get Jetson model name."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    return f.read().strip().rstrip("\x00")
        except Exception:
            pass
        return None

    def _get_jetson_gpu_architecture(self, model: str | None) -> str | None:
        """
        Map a Jetson module/board name to its GPU microarchitecture.

        References (NVIDIA Jetson product briefs):
        - Orin (Nano / NX / AGX)          -> Ampere
        - Xavier (NX / AGX)               -> Volta
        - TX2 / TX2 NX                    -> Pascal
        - TX1 / Nano (original) / Nano 2GB -> Maxwell
        """
        if not model:
            return None
        m = model.lower()
        if "orin" in m:
            return "Ampere"
        if "xavier" in m:
            return "Volta"
        if "tx2" in m:
            return "Pascal"
        if "tx1" in m or "nano" in m:
            return "Maxwell"
        return None

    def _is_orange_pi(self) -> bool:
        """Check if running on Orange Pi."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    model = f.read().lower()
                    if "orange pi" in model or "orangepi" in model:
                        return True
            # Check for Allwinner/Rockchip with Orange Pi branding
            if os.path.exists("/etc/orangepi-release"):
                return True
        except Exception:
            pass
        return False

    def _get_orange_pi_model(self) -> str | None:
        """Get Orange Pi model name."""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model") as f:
                    return f.read().strip().rstrip("\x00")
        except Exception:
            pass
        return None

    def _is_aetina(self) -> bool:
        """Check if running on Aetina platform."""
        try:
            # Aetina often uses Jetson modules with custom carriers
            result = subprocess.run(
                ["dmidecode", "-s", "system-manufacturer"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if "aetina" in result.stdout.lower():
                return True
            # Check for Aetina-specific files
            if os.path.exists("/etc/aetina-release"):
                return True
        except Exception:
            pass
        return False

    def _get_aetina_model(self) -> str | None:
        """Get Aetina model name."""
        try:
            result = subprocess.run(
                ["dmidecode", "-s", "system-product-name"],
                capture_output=True,
                text=True,
                timeout=5,
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
                with open("/proc/device-tree/model") as f:
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
                with open("/proc/device-tree/model") as f:
                    model = f.read().lower()
                    if "khadas" in model:
                        return True
        except Exception:
            pass
        return False

    # =========================================================================
    # Accelerator Detection
    # =========================================================================

    def _detect_accelerators(self) -> list[AcceleratorInfo]:
        """Detect all available hardware accelerators."""
        accelerators: list[AcceleratorInfo] = []

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
        accelerators.append(
            AcceleratorInfo(
                type=AcceleratorType.CPU,
                name="CPU",
                status=AcceleratorStatus.AVAILABLE,
                details={"info": "Default CPU inference backend"},
            )
        )

        return accelerators

    def _detect_nvidia_gpu(self) -> list[AcceleratorInfo]:
        """Detect NVIDIA GPUs using multiple methods."""
        gpus: list[AcceleratorInfo] = []

        # Method 1: nvidia-smi (most reliable when available)
        gpus = self._detect_nvidia_via_smi()
        if gpus:
            return self._refine_nvidia_for_jetson(gpus)

        # Method 2: Check via lspci for NVIDIA devices
        gpus = self._detect_nvidia_via_lspci()
        if gpus:
            return self._refine_nvidia_for_jetson(gpus)

        # Method 3: Check CUDA availability via Python
        gpus = self._detect_nvidia_via_cuda()
        if gpus:
            return self._refine_nvidia_for_jetson(gpus)

        # Method 4: Check /proc/driver/nvidia
        gpus = self._detect_nvidia_via_proc()
        if gpus:
            return self._refine_nvidia_for_jetson(gpus)

        return gpus

    def _refine_nvidia_for_jetson(self, gpus: list[AcceleratorInfo]) -> list[AcceleratorInfo]:
        """
        On NVIDIA Jetson, retag generic ``NVIDIA_GPU`` entries as
        ``NVIDIA_JETSON`` and produce a more descriptive name that includes
        the GPU microarchitecture (e.g. ``Ampere iGPU (Jetson Orin Nano)``)
        rather than the generic ``NVIDIA GPU`` reported by some probes.
        """
        if not self._is_jetson():
            return gpus

        model = self._get_jetson_model()
        arch = self._get_jetson_gpu_architecture(model)

        refined: list[AcceleratorInfo] = []
        for acc in gpus:
            if acc.type != AcceleratorType.NVIDIA_GPU:
                refined.append(acc)
                continue

            # Build a human-friendly name.
            arch_label = f"{arch} iGPU" if arch else "Integrated GPU"
            if model:
                friendly = f"{arch_label} ({model})"
            else:
                friendly = arch_label

            details = dict(acc.details or {})
            if arch:
                details["gpu_architecture"] = arch
            if model:
                details["jetson_model"] = model
            details["integrated"] = True

            refined.append(
                acc.model_copy(
                    update={
                        "type": AcceleratorType.NVIDIA_JETSON,
                        "name": friendly,
                        "details": details,
                    }
                )
            )
        return refined

    def _detect_nvidia_via_smi(self) -> list[AcceleratorInfo]:
        """Detect NVIDIA GPUs via nvidia-smi."""
        gpus: list[AcceleratorInfo] = []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version,pci.bus_id,compute_cap",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = [p.strip() for p in line.split(",")]
                        if len(parts) >= 5:
                            name, memory, driver, pcie, compute_cap = parts[:5]

                            # Check if TensorRT is available
                            tensorrt_available = self._check_tensorrt()

                            gpus.append(
                                AcceleratorInfo(
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
                                )
                            )

                            # Add TensorRT as separate accelerator if available
                            if tensorrt_available:
                                gpus.append(
                                    AcceleratorInfo(
                                        type=AcceleratorType.NVIDIA_TENSORRT,
                                        name=f"TensorRT on {name}",
                                        status=AcceleratorStatus.AVAILABLE,
                                        driver_version=driver,
                                        memory_mb=int(float(memory)) if memory else None,
                                        details={"gpu_name": name},
                                    )
                                )

        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"nvidia-smi detection failed: {e}")

        return gpus

    def _detect_nvidia_via_lspci(self) -> list[AcceleratorInfo]:
        """Detect NVIDIA GPUs via lspci."""
        gpus: list[AcceleratorInfo] = []

        try:
            result = subprocess.run(["lspci", "-nn"], capture_output=True, text=True, timeout=10)

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

                        gpus.append(
                            AcceleratorInfo(
                                type=AcceleratorType.NVIDIA_GPU,
                                name=name,
                                status=AcceleratorStatus.AVAILABLE
                                if driver_loaded
                                else AcceleratorStatus.DRIVER_MISSING,
                                pcie_address=pcie_addr,
                                details={
                                    "detection_method": "lspci",
                                    "driver_loaded": driver_loaded,
                                    "raw_info": line.strip(),
                                },
                            )
                        )

        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"lspci NVIDIA detection failed: {e}")

        return gpus

    def _detect_nvidia_via_cuda(self) -> list[AcceleratorInfo]:
        """Detect NVIDIA GPUs via CUDA Python bindings."""
        gpus: list[AcceleratorInfo] = []

        # Try torch first (commonly available)
        try:
            import torch

            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    gpus.append(
                        AcceleratorInfo(
                            type=AcceleratorType.NVIDIA_GPU,
                            name=props.name,
                            status=AcceleratorStatus.AVAILABLE,
                            memory_mb=props.total_memory // (1024 * 1024),
                            compute_capability=f"{props.major}.{props.minor}",
                            details={
                                "detection_method": "torch.cuda",
                                "multi_processor_count": props.multi_processor_count,
                            },
                        )
                    )
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
                gpus.append(
                    AcceleratorInfo(
                        type=AcceleratorType.NVIDIA_GPU,
                        name=dev.name(),
                        status=AcceleratorStatus.AVAILABLE,
                        memory_mb=dev.total_memory() // (1024 * 1024),
                        compute_capability=f"{dev.compute_capability()[0]}.{dev.compute_capability()[1]}",
                        details={
                            "detection_method": "pycuda",
                        },
                    )
                )
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pycuda detection failed: {e}")

        return gpus

    def _detect_nvidia_via_proc(self) -> list[AcceleratorInfo]:
        """Detect NVIDIA GPUs via /proc filesystem."""
        gpus: list[AcceleratorInfo] = []

        # Check /proc/driver/nvidia/gpus/
        nvidia_gpus_path = "/proc/driver/nvidia/gpus"
        if os.path.exists(nvidia_gpus_path):
            try:
                for gpu_dir in os.listdir(nvidia_gpus_path):
                    info_path = os.path.join(nvidia_gpus_path, gpu_dir, "information")
                    if os.path.exists(info_path):
                        with open(info_path) as f:
                            content = f.read()

                        name = "NVIDIA GPU"
                        for line in content.split("\n"):
                            if line.startswith("Model:"):
                                name = line.split(":", 1)[1].strip()
                                break

                        gpus.append(
                            AcceleratorInfo(
                                type=AcceleratorType.NVIDIA_GPU,
                                name=name,
                                status=AcceleratorStatus.AVAILABLE,
                                pcie_address=gpu_dir,
                                details={
                                    "detection_method": "/proc/driver/nvidia",
                                },
                            )
                        )
            except Exception as e:
                logger.debug(f"/proc NVIDIA detection failed: {e}")

        # Also check /dev/nvidia* devices
        if not gpus:
            nvidia_devices = [
                d for d in os.listdir("/dev") if d.startswith("nvidia") and d != "nvidiactl" and d != "nvidia-uvm"
            ]
            for dev in nvidia_devices:
                if dev.startswith("nvidia") and dev[6:].isdigit():
                    gpus.append(
                        AcceleratorInfo(
                            type=AcceleratorType.NVIDIA_GPU,
                            name=f"NVIDIA GPU {dev[6:]}",
                            status=AcceleratorStatus.AVAILABLE,
                            device_path=f"/dev/{dev}",
                            details={
                                "detection_method": "/dev device",
                            },
                        )
                    )

        return gpus

    def _check_nvidia_driver_loaded(self) -> bool:
        """Check if NVIDIA driver is loaded in kernel."""
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return "nvidia" in result.stdout.lower()
        except Exception:
            pass

        # Also check /proc/modules
        try:
            with open("/proc/modules") as f:
                content = f.read().lower()
                return "nvidia" in content
        except Exception:
            pass

        return False

    def _check_tensorrt(self) -> bool:
        """Check if TensorRT is available."""
        try:
            import tensorrt  # noqa: F401

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

    def _detect_hailo(self) -> list[AcceleratorInfo]:
        """Detect Hailo AI accelerators (Hailo-8, Hailo-8L, Hailo-10)."""
        devices: list[AcceleratorInfo] = []

        try:
            # Try hailortcli
            result = subprocess.run(
                ["hailortcli", "fw-control", "identify"], capture_output=True, text=True, timeout=10
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

                devices.append(
                    AcceleratorInfo(
                        type=device_type,
                        name=name,
                        status=AcceleratorStatus.AVAILABLE,
                        firmware_version=fw_version,
                        details={"raw_output": output[:500]},
                    )
                )
        except FileNotFoundError:
            # hailortcli not installed - check for PCIe devices
            try:
                result = subprocess.run(
                    ["lspci", "-d", "1e60:"],  # Hailo vendor ID
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    devices.append(
                        AcceleratorInfo(
                            type=AcceleratorType.HAILO_8,
                            name="Hailo Device (driver not installed)",
                            status=AcceleratorStatus.DRIVER_MISSING,
                            details={"pcie_info": result.stdout.strip()},
                        )
                    )
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error detecting Hailo: {e}")

        return devices

    def _detect_coral(self) -> list[AcceleratorInfo]:
        """Detect Google Coral Edge TPU devices."""
        devices: list[AcceleratorInfo] = []

        # Check for USB Coral
        try:
            result = subprocess.run(
                ["lsusb", "-d", "1a6e:089a"],  # Coral USB Accelerator
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                devices.append(
                    AcceleratorInfo(
                        type=AcceleratorType.GOOGLE_CORAL_USB,
                        name="Google Coral USB Accelerator",
                        status=AcceleratorStatus.AVAILABLE,
                        details={"usb_info": result.stdout.strip()},
                    )
                )
        except Exception:
            pass

        # Check for PCIe/M.2 Coral
        try:
            result = subprocess.run(
                ["lspci", "-d", "1ac1:089a"],  # Coral PCIe
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                devices.append(
                    AcceleratorInfo(
                        type=AcceleratorType.GOOGLE_CORAL_PCIE,
                        name="Google Coral PCIe/M.2 Accelerator",
                        status=AcceleratorStatus.AVAILABLE,
                        details={"pcie_info": result.stdout.strip()},
                    )
                )
        except Exception:
            pass

        # Verify Edge TPU runtime is installed
        if devices:
            try:
                result = subprocess.run(["dpkg", "-l", "libedgetpu1-std"], capture_output=True, text=True, timeout=5)
                runtime_installed = result.returncode == 0
                for device in devices:
                    device.details["runtime_installed"] = runtime_installed
                    if not runtime_installed:
                        device.status = AcceleratorStatus.DRIVER_MISSING
            except Exception:
                pass

        return devices

    def _detect_axelera(self) -> list[AcceleratorInfo]:
        """Detect Axelera AI accelerators."""
        devices: list[AcceleratorInfo] = []

        try:
            # Check for Axelera PCIe device (Metis)
            result = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Look for Axelera in output
                if "axelera" in result.stdout.lower() or "metis" in result.stdout.lower():
                    devices.append(
                        AcceleratorInfo(
                            type=AcceleratorType.AXELERA_M2,
                            name="Axelera Metis AI Accelerator",
                            status=AcceleratorStatus.AVAILABLE,
                        )
                    )

            # Check for axelera-runtime
            result = subprocess.run(["which", "axelera-info"], capture_output=True, timeout=5)
            if result.returncode == 0:
                # Get device info
                info_result = subprocess.run(["axelera-info"], capture_output=True, text=True, timeout=10)
                if info_result.returncode == 0:
                    devices.append(
                        AcceleratorInfo(
                            type=AcceleratorType.AXELERA_M2,
                            name="Axelera AI Accelerator",
                            status=AcceleratorStatus.AVAILABLE,
                            details={"info": info_result.stdout[:500]},
                        )
                    )
        except Exception as e:
            logger.warning(f"Error detecting Axelera: {e}")

        return devices

    def _detect_openvino(self) -> AcceleratorInfo | None:
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
                capture_output=True,
                text=True,
                timeout=10,
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

    def _detect_amd_rocm(self) -> list[AcceleratorInfo]:
        """Detect AMD GPUs with ROCm support."""
        gpus: list[AcceleratorInfo] = []

        try:
            result = subprocess.run(["rocm-smi", "--showproductname"], capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse ROCm output
                for line in result.stdout.split("\n"):
                    if "GPU" in line and ":" in line:
                        name = line.split(":")[-1].strip()
                        gpus.append(
                            AcceleratorInfo(
                                type=AcceleratorType.AMD_ROCM,
                                name=f"AMD {name}",
                                status=AcceleratorStatus.AVAILABLE,
                            )
                        )
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Error detecting AMD ROCm: {e}")

        return gpus

    # =========================================================================
    # Recommendation Logic
    # =========================================================================

    def _get_recommended_accelerator(self, accelerators: list[AcceleratorInfo]) -> AcceleratorType | None:
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

        available_types = {acc.type for acc in accelerators if acc.status == AcceleratorStatus.AVAILABLE}

        for acc_type in priority:
            if acc_type in available_types:
                return acc_type

        return AcceleratorType.CPU


# Global service instance
hardware_detection_service = HardwareDetectionService()
