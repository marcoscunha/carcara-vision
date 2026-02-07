"""
Tests for Hardware Detection Service.

These tests cover:
- CPU detection
- Memory detection
- Platform/vendor identification
- Accelerator detection (mocked)
- Caching behavior
- Recommendation logic
"""

import time
from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

from src.schemas.hardware import (
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
from src.services.hardware import HardwareDetectionService


class TestHardwareDetectionService(TestCase):
    """Test cases for HardwareDetectionService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = HardwareDetectionService()

    def tearDown(self):
        """Clean up after tests."""
        self.service = None


class TestCPUDetection(TestHardwareDetectionService):
    """Tests for CPU detection functionality."""

    def test_detect_cpu_returns_cpu_info(self):
        """Test that _detect_cpu returns a CPUInfo object."""
        result = self.service._detect_cpu()

        self.assertIsInstance(result, CPUInfo)
        self.assertIsInstance(result.architecture, CPUArchitecture)
        self.assertIsInstance(result.model_name, str)
        self.assertIsInstance(result.vendor, str)
        self.assertIsInstance(result.cores, int)
        self.assertIsInstance(result.threads, int)
        self.assertIsInstance(result.features, list)

    def test_detect_cpu_cores_positive(self):
        """Test that detected CPU cores is a positive number."""
        result = self.service._detect_cpu()

        self.assertGreater(result.cores, 0, "CPU cores should be greater than 0")
        self.assertGreater(result.threads, 0, "CPU threads should be greater than 0")

    @patch("platform.machine")
    def test_detect_cpu_architecture_x86_64(self, mock_machine):
        """Test CPU architecture detection for x86_64."""
        mock_machine.return_value = "x86_64"

        result = self.service._detect_cpu()

        self.assertEqual(result.architecture, CPUArchitecture.X86_64)

    @patch("platform.machine")
    def test_detect_cpu_architecture_arm64(self, mock_machine):
        """Test CPU architecture detection for ARM64."""
        mock_machine.return_value = "aarch64"

        result = self.service._detect_cpu()

        self.assertEqual(result.architecture, CPUArchitecture.ARM64)

    @patch("platform.machine")
    def test_detect_cpu_architecture_armv7(self, mock_machine):
        """Test CPU architecture detection for ARMv7."""
        mock_machine.return_value = "armv7l"

        result = self.service._detect_cpu()

        self.assertEqual(result.architecture, CPUArchitecture.ARMV7)

    @patch("platform.machine")
    def test_detect_cpu_architecture_unknown(self, mock_machine):
        """Test CPU architecture detection for unknown architecture."""
        mock_machine.return_value = "unknown_arch"

        result = self.service._detect_cpu()

        self.assertEqual(result.architecture, CPUArchitecture.UNKNOWN)

    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
processor	: 0
vendor_id	: GenuineIntel
model name	: Intel(R) Core(TM) i7-10700K CPU @ 3.80GHz
flags		: fpu vme de pse tsc msr pae mce cx8 apic sep mtrr
core id		: 0
physical id	: 0
""",
    )
    def test_detect_cpu_parses_cpuinfo(self, mock_file, mock_exists):
        """Test CPU info parsing from /proc/cpuinfo."""
        mock_exists.return_value = True

        result = self.service._detect_cpu()

        self.assertEqual(result.vendor, "GenuineIntel")
        self.assertIn("Intel", result.model_name)
        self.assertIn("fpu", result.features)

    def test_detect_cpu_features_limited_to_50(self):
        """Test that CPU features are limited to 50 items."""
        result = self.service._detect_cpu()

        self.assertLessEqual(len(result.features), 50)


class TestMemoryDetection(TestHardwareDetectionService):
    """Tests for memory detection functionality."""

    def test_detect_memory_returns_memory_info(self):
        """Test that _detect_memory returns a MemoryInfo object."""
        result = self.service._detect_memory()

        self.assertIsInstance(result, MemoryInfo)
        self.assertIsInstance(result.total_gb, float)
        self.assertIsInstance(result.available_gb, float)
        self.assertIsInstance(result.used_percent, float)

    def test_detect_memory_values_valid(self):
        """Test that memory values are within valid ranges."""
        result = self.service._detect_memory()

        self.assertGreaterEqual(result.total_gb, 0)
        self.assertGreaterEqual(result.available_gb, 0)
        self.assertGreaterEqual(result.used_percent, 0)
        self.assertLessEqual(result.used_percent, 100)

    @patch("os.path.exists")
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
MemTotal:       16384000 kB
MemFree:         2048000 kB
MemAvailable:    8192000 kB
Buffers:          512000 kB
""",
    )
    def test_detect_memory_parses_meminfo(self, mock_file, mock_exists):
        """Test memory info parsing from /proc/meminfo."""
        mock_exists.return_value = True

        result = self.service._detect_memory()

        # 16384000 kB = ~15.625 GB
        self.assertAlmostEqual(result.total_gb, 15.625, places=1)
        # 8192000 kB = ~7.8125 GB
        self.assertAlmostEqual(result.available_gb, 7.8125, places=1)

    @patch("os.path.exists")
    def test_detect_memory_handles_missing_meminfo(self, mock_exists):
        """Test memory detection handles missing /proc/meminfo."""
        mock_exists.return_value = False

        result = self.service._detect_memory()

        self.assertEqual(result.total_gb, 0.0)
        self.assertEqual(result.available_gb, 0.0)


class TestPlatformDetection(TestHardwareDetectionService):
    """Tests for platform/vendor detection functionality."""

    def test_detect_platform_returns_platform_info(self):
        """Test that _detect_platform returns a PlatformInfo object."""
        result = self.service._detect_platform()

        self.assertIsInstance(result, PlatformInfo)
        self.assertIsInstance(result.vendor, PlatformVendor)
        self.assertIsInstance(result.board_name, str)
        self.assertIsInstance(result.os_name, str)
        self.assertIsInstance(result.kernel_version, str)

    @patch.object(HardwareDetectionService, "_is_raspberry_pi")
    @patch.object(HardwareDetectionService, "_get_raspberry_pi_model")
    def test_identify_raspberry_pi(self, mock_get_model, mock_is_rpi):
        """Test Raspberry Pi identification."""
        mock_is_rpi.return_value = True
        mock_get_model.return_value = "Raspberry Pi 4 Model B Rev 1.4"

        vendor, board_name, board_model = self.service._identify_platform_vendor()

        self.assertEqual(vendor, PlatformVendor.RASPBERRY_PI)
        self.assertEqual(board_name, "Raspberry Pi 4 Model B Rev 1.4")

    @patch.object(HardwareDetectionService, "_is_raspberry_pi")
    @patch.object(HardwareDetectionService, "_is_jetson")
    @patch.object(HardwareDetectionService, "_get_jetson_model")
    def test_identify_jetson(self, mock_get_model, mock_is_jetson, mock_is_rpi):
        """Test NVIDIA Jetson identification."""
        mock_is_rpi.return_value = False
        mock_is_jetson.return_value = True
        mock_get_model.return_value = "NVIDIA Jetson Nano Developer Kit"

        vendor, board_name, board_model = self.service._identify_platform_vendor()

        self.assertEqual(vendor, PlatformVendor.NVIDIA_JETSON)
        self.assertIn("Jetson", board_name)

    @patch.object(HardwareDetectionService, "_is_raspberry_pi")
    @patch.object(HardwareDetectionService, "_is_jetson")
    @patch.object(HardwareDetectionService, "_is_orange_pi")
    @patch.object(HardwareDetectionService, "_get_orange_pi_model")
    def test_identify_orange_pi(self, mock_get_model, mock_is_orange, mock_is_jetson, mock_is_rpi):
        """Test Orange Pi identification."""
        mock_is_rpi.return_value = False
        mock_is_jetson.return_value = False
        mock_is_orange.return_value = True
        mock_get_model.return_value = "Orange Pi 5 Plus"

        vendor, board_name, board_model = self.service._identify_platform_vendor()

        self.assertEqual(vendor, PlatformVendor.ORANGE_PI)

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open, read_data="raspberry pi 4 model b")
    def test_is_raspberry_pi_from_device_tree(self, mock_file, mock_exists):
        """Test Raspberry Pi detection from device tree."""
        mock_exists.return_value = True

        result = self.service._is_raspberry_pi()

        self.assertTrue(result)

    @patch("os.path.exists")
    def test_is_raspberry_pi_false_when_no_files(self, mock_exists):
        """Test Raspberry Pi detection returns False when no identifying files."""
        mock_exists.return_value = False

        result = self.service._is_raspberry_pi()

        self.assertFalse(result)

    @patch("os.path.exists")
    def test_is_jetson_from_tegra_release(self, mock_exists):
        """Test Jetson detection from tegra release file."""

        def exists_side_effect(path):
            return path == "/etc/nv_tegra_release"

        mock_exists.side_effect = exists_side_effect

        result = self.service._is_jetson()

        self.assertTrue(result)


class TestAcceleratorDetection(TestHardwareDetectionService):
    """Tests for hardware accelerator detection."""

    def test_detect_accelerators_always_includes_cpu(self):
        """Test that CPU is always included as a fallback accelerator."""
        result = self.service._detect_accelerators()

        cpu_accelerators = [acc for acc in result if acc.type == AcceleratorType.CPU]
        self.assertEqual(len(cpu_accelerators), 1)
        self.assertEqual(cpu_accelerators[0].status, AcceleratorStatus.AVAILABLE)

    @patch("subprocess.run")
    def test_detect_nvidia_gpu_available(self, mock_run):
        """Test NVIDIA GPU detection when available."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="NVIDIA GeForce RTX 3080, 10240, 535.104.05, 00000000:01:00.0, 8.6\n",
        )

        result = self.service._detect_nvidia_gpu()

        self.assertGreater(len(result), 0)
        self.assertEqual(result[0].type, AcceleratorType.NVIDIA_GPU)
        self.assertEqual(result[0].status, AcceleratorStatus.AVAILABLE)
        self.assertIn("RTX 3080", result[0].name)

    @patch("subprocess.run")
    def test_detect_nvidia_gpu_not_available(self, mock_run):
        """Test NVIDIA GPU detection when nvidia-smi fails."""
        mock_run.side_effect = FileNotFoundError()

        result = self.service._detect_nvidia_gpu()

        self.assertEqual(len(result), 0)

    @patch("subprocess.run")
    def test_detect_hailo_available(self, mock_run):
        """Test Hailo detection when available."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Hailo-8\nFirmware Version: 4.17.0")

        result = self.service._detect_hailo()

        self.assertGreater(len(result), 0)
        self.assertEqual(result[0].type, AcceleratorType.HAILO_8)
        self.assertEqual(result[0].status, AcceleratorStatus.AVAILABLE)

    @patch("subprocess.run")
    def test_detect_hailo_8l(self, mock_run):
        """Test Hailo-8L detection."""
        mock_run.return_value = MagicMock(returncode=0, stdout="Hailo-8L\nFirmware Version: 4.17.0")

        result = self.service._detect_hailo()

        self.assertGreater(len(result), 0)
        self.assertEqual(result[0].type, AcceleratorType.HAILO_8L)

    @patch("subprocess.run")
    def test_detect_coral_usb(self, mock_run):
        """Test Google Coral USB detection."""

        def run_side_effect(*args, **kwargs):
            if "lsusb" in args[0]:
                return MagicMock(returncode=0, stdout="Bus 001 Device 003: ID 1a6e:089a Global Unichip Corp.")
            return MagicMock(returncode=1, stdout="")

        mock_run.side_effect = run_side_effect

        result = self.service._detect_coral()

        usb_corals = [acc for acc in result if acc.type == AcceleratorType.GOOGLE_CORAL_USB]
        self.assertEqual(len(usb_corals), 1)


class TestRecommendationLogic(TestHardwareDetectionService):
    """Tests for accelerator recommendation logic."""

    def test_recommend_tensorrt_over_cuda(self):
        """Test that TensorRT is recommended over plain CUDA."""
        accelerators = [
            AcceleratorInfo(
                type=AcceleratorType.NVIDIA_GPU,
                name="RTX 3080",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.NVIDIA_TENSORRT,
                name="TensorRT on RTX 3080",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.CPU,
                name="CPU",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
        ]

        result = self.service._get_recommended_accelerator(accelerators)

        self.assertEqual(result, AcceleratorType.NVIDIA_TENSORRT)

    def test_recommend_hailo_over_coral(self):
        """Test that Hailo is recommended over Coral."""
        accelerators = [
            AcceleratorInfo(
                type=AcceleratorType.HAILO_8,
                name="Hailo-8",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.GOOGLE_CORAL_USB,
                name="Coral USB",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.CPU,
                name="CPU",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
        ]

        result = self.service._get_recommended_accelerator(accelerators)

        self.assertEqual(result, AcceleratorType.HAILO_8)

    def test_recommend_cpu_when_no_accelerators(self):
        """Test that CPU is recommended when no accelerators available."""
        accelerators = [
            AcceleratorInfo(
                type=AcceleratorType.NVIDIA_GPU,
                name="RTX 3080",
                status=AcceleratorStatus.DRIVER_MISSING,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.CPU,
                name="CPU",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
        ]

        result = self.service._get_recommended_accelerator(accelerators)

        self.assertEqual(result, AcceleratorType.CPU)

    def test_skip_unavailable_accelerators(self):
        """Test that unavailable accelerators are skipped in recommendation."""
        accelerators = [
            AcceleratorInfo(
                type=AcceleratorType.NVIDIA_TENSORRT,
                name="TensorRT",
                status=AcceleratorStatus.UNAVAILABLE,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.HAILO_8,
                name="Hailo-8",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.CPU,
                name="CPU",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
        ]

        result = self.service._get_recommended_accelerator(accelerators)

        self.assertEqual(result, AcceleratorType.HAILO_8)


class TestCaching(TestHardwareDetectionService):
    """Tests for caching behavior."""

    def test_detect_all_caches_result(self):
        """Test that detect_all caches its result."""
        result1 = self.service.detect_all()
        result2 = self.service.detect_all()

        # Should return same cached object
        self.assertIs(result1, result2)

    def test_detect_all_force_refresh_bypasses_cache(self):
        """Test that force_refresh bypasses the cache."""
        result1 = self.service.detect_all()
        result2 = self.service.detect_all(force_refresh=True)

        # Should be different objects (re-detected)
        self.assertIsNot(result1, result2)
        # But should have same structure
        self.assertEqual(result1.cpu.architecture, result2.cpu.architecture)

    def test_cache_expires_after_ttl(self):
        """Test that cache expires after TTL."""
        # Set a very short TTL for testing
        self.service._cache_ttl = 0.1  # 100ms

        result1 = self.service.detect_all()
        time.sleep(0.15)  # Wait for cache to expire
        result2 = self.service.detect_all()

        # Should be different objects (cache expired)
        self.assertIsNot(result1, result2)


class TestFullDetection(TestHardwareDetectionService):
    """Integration tests for full hardware detection."""

    def test_detect_all_returns_complete_result(self):
        """Test that detect_all returns a complete HardwareDetectionResult."""
        result = self.service.detect_all()

        self.assertIsInstance(result, HardwareDetectionResult)
        self.assertIsInstance(result.cpu, CPUInfo)
        self.assertIsInstance(result.memory, MemoryInfo)
        self.assertIsInstance(result.platform, PlatformInfo)
        self.assertIsInstance(result.accelerators, list)
        self.assertIsInstance(result.detection_timestamp, str)
        self.assertIsInstance(result.detection_duration_ms, float)

    def test_detect_all_has_valid_timestamp(self):
        """Test that detection timestamp is valid ISO format."""
        result = self.service.detect_all()

        # Should be able to parse as ISO format
        from datetime import datetime

        try:
            datetime.fromisoformat(result.detection_timestamp.replace("Z", "+00:00"))
        except ValueError:
            self.fail("detection_timestamp is not valid ISO format")

    def test_detect_all_has_positive_duration(self):
        """Test that detection duration is positive."""
        result = self.service.detect_all()

        self.assertGreater(result.detection_duration_ms, 0)

    def test_detect_all_has_accelerators(self):
        """Test that at least one accelerator (CPU) is detected."""
        result = self.service.detect_all()

        self.assertGreater(len(result.accelerators), 0)

        # CPU should always be present
        cpu_types = [acc.type for acc in result.accelerators]
        self.assertIn(AcceleratorType.CPU, cpu_types)

    def test_detect_all_has_recommended_accelerator(self):
        """Test that a recommended accelerator is provided."""
        result = self.service.detect_all()

        # Should have a recommendation (at minimum CPU)
        self.assertIsNotNone(result.recommended_accelerator)
        self.assertIsInstance(result.recommended_accelerator, AcceleratorType)


class TestEdgeCases(TestHardwareDetectionService):
    """Tests for edge cases and error handling."""

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_handles_file_read_errors_gracefully(self, mock_open, mock_exists):
        """Test that file read errors are handled gracefully."""
        mock_exists.return_value = True
        mock_open.side_effect = OSError("Permission denied")

        # Should not raise, should return valid (possibly default) values
        result = self.service._detect_cpu()

        self.assertIsInstance(result, CPUInfo)

    @patch("subprocess.run")
    def test_handles_subprocess_timeout(self, mock_run):
        """Test that subprocess timeouts are handled gracefully."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)

        # Should not raise
        result = self.service._detect_nvidia_gpu()

        self.assertIsInstance(result, list)

    def test_empty_accelerator_list_returns_cpu(self):
        """Test that an empty accelerator detection still includes CPU."""
        # Even if all detection methods fail, CPU should be added
        result = self.service._detect_accelerators()

        cpu_found = any(acc.type == AcceleratorType.CPU for acc in result)
        self.assertTrue(cpu_found, "CPU accelerator should always be present")
