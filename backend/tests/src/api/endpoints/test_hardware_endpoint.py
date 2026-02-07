"""
Tests for Hardware Detection API Endpoints.

These tests verify the REST API for hardware detection.
"""

from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.main import app
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


def create_mock_hardware_result() -> HardwareDetectionResult:
    """Create a mock HardwareDetectionResult for testing."""
    return HardwareDetectionResult(
        cpu=CPUInfo(
            architecture=CPUArchitecture.X86_64,
            model_name="Intel(R) Core(TM) i7-10700K CPU @ 3.80GHz",
            vendor="GenuineIntel",
            cores=8,
            threads=16,
            max_frequency_mhz=5100.0,
            features=["avx", "avx2", "sse4_2"],
        ),
        memory=MemoryInfo(
            total_gb=32.0,
            available_gb=24.5,
            used_percent=23.4,
        ),
        platform=PlatformInfo(
            vendor=PlatformVendor.INTEL,
            board_name="Intel x86_64",
            board_model=None,
            serial_number=None,
            os_name="Ubuntu",
            os_version="22.04",
            kernel_version="5.15.0-generic",
        ),
        accelerators=[
            AcceleratorInfo(
                type=AcceleratorType.NVIDIA_GPU,
                name="NVIDIA GeForce RTX 3080",
                status=AcceleratorStatus.AVAILABLE,
                driver_version="535.104.05",
                memory_mb=10240,
                compute_capability="8.6",
                details={},
            ),
            AcceleratorInfo(
                type=AcceleratorType.CPU,
                name="CPU",
                status=AcceleratorStatus.AVAILABLE,
                details={},
            ),
        ],
        recommended_accelerator=AcceleratorType.NVIDIA_GPU,
        detection_timestamp="2026-01-27T10:30:00+00:00",
        detection_duration_ms=1523.5,
    )


class TestHardwareEndpoints(TestCase):
    """Test cases for hardware detection API endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up resources shared across all tests."""
        cls.client = TestClient(app)
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up resources shared across all tests."""
        cls.client = None
        super().tearDownClass()


class TestDetectEndpoint(TestHardwareEndpoints):
    """Tests for GET /api/v1/hardware/detect endpoint."""

    def test_detect_hardware_returns_200(self):
        """Test that hardware detection endpoint returns 200."""
        response = self.client.get("/api/v1/hardware/detect")

        self.assertEqual(response.status_code, 200)

    def test_detect_hardware_returns_valid_structure(self):
        """Test that hardware detection returns valid JSON structure."""
        response = self.client.get("/api/v1/hardware/detect")
        data = response.json()

        # Check required fields exist
        self.assertIn("cpu", data)
        self.assertIn("memory", data)
        self.assertIn("platform", data)
        self.assertIn("accelerators", data)
        self.assertIn("detection_timestamp", data)
        self.assertIn("detection_duration_ms", data)

    def test_detect_hardware_cpu_structure(self):
        """Test that CPU info has correct structure."""
        response = self.client.get("/api/v1/hardware/detect")
        cpu = response.json()["cpu"]

        self.assertIn("architecture", cpu)
        self.assertIn("model_name", cpu)
        self.assertIn("vendor", cpu)
        self.assertIn("cores", cpu)
        self.assertIn("threads", cpu)
        self.assertIn("features", cpu)

    def test_detect_hardware_memory_structure(self):
        """Test that memory info has correct structure."""
        response = self.client.get("/api/v1/hardware/detect")
        memory = response.json()["memory"]

        self.assertIn("total_gb", memory)
        self.assertIn("available_gb", memory)
        self.assertIn("used_percent", memory)

    def test_detect_hardware_platform_structure(self):
        """Test that platform info has correct structure."""
        response = self.client.get("/api/v1/hardware/detect")
        platform = response.json()["platform"]

        self.assertIn("vendor", platform)
        self.assertIn("board_name", platform)
        self.assertIn("os_name", platform)
        self.assertIn("kernel_version", platform)

    def test_detect_hardware_accelerators_structure(self):
        """Test that accelerators list has correct structure."""
        response = self.client.get("/api/v1/hardware/detect")
        accelerators = response.json()["accelerators"]

        self.assertIsInstance(accelerators, list)
        self.assertGreater(len(accelerators), 0, "Should have at least CPU accelerator")

        # Check first accelerator structure
        acc = accelerators[0]
        self.assertIn("type", acc)
        self.assertIn("name", acc)
        self.assertIn("status", acc)

    def test_detect_hardware_refresh_parameter(self):
        """Test that refresh parameter is accepted."""
        response = self.client.get("/api/v1/hardware/detect?refresh=true")

        self.assertEqual(response.status_code, 200)

    def test_detect_hardware_refresh_false(self):
        """Test that refresh=false uses cached data."""
        # First call
        response1 = self.client.get("/api/v1/hardware/detect")
        # Second call with refresh=false
        response2 = self.client.get("/api/v1/hardware/detect?refresh=false")

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)


class TestCPUEndpoint(TestHardwareEndpoints):
    """Tests for GET /api/v1/hardware/cpu endpoint."""

    def test_get_cpu_returns_200(self):
        """Test that CPU endpoint returns 200."""
        response = self.client.get("/api/v1/hardware/cpu")

        self.assertEqual(response.status_code, 200)

    def test_get_cpu_returns_cpu_info(self):
        """Test that CPU endpoint returns CPU info directly."""
        response = self.client.get("/api/v1/hardware/cpu")
        data = response.json()

        self.assertIn("architecture", data)
        self.assertIn("model_name", data)
        self.assertIn("cores", data)
        self.assertIn("threads", data)

    def test_get_cpu_valid_architecture(self):
        """Test that CPU architecture is a valid value."""
        response = self.client.get("/api/v1/hardware/cpu")
        arch = response.json()["architecture"]

        valid_architectures = ["x86_64", "x86", "arm64", "armv7", "armv8", "unknown"]
        self.assertIn(arch, valid_architectures)


class TestPlatformEndpoint(TestHardwareEndpoints):
    """Tests for GET /api/v1/hardware/platform endpoint."""

    def test_get_platform_returns_200(self):
        """Test that platform endpoint returns 200."""
        response = self.client.get("/api/v1/hardware/platform")

        self.assertEqual(response.status_code, 200)

    def test_get_platform_returns_platform_info(self):
        """Test that platform endpoint returns platform info directly."""
        response = self.client.get("/api/v1/hardware/platform")
        data = response.json()

        self.assertIn("vendor", data)
        self.assertIn("board_name", data)
        self.assertIn("os_name", data)

    def test_get_platform_valid_vendor(self):
        """Test that platform vendor is a valid value."""
        response = self.client.get("/api/v1/hardware/platform")
        vendor = response.json()["vendor"]

        valid_vendors = [
            "intel",
            "amd",
            "nvidia_jetson",
            "raspberry_pi",
            "orange_pi",
            "aetina",
            "rock_pi",
            "khadas",
            "generic_arm",
            "generic_x86",
            "unknown",
        ]
        self.assertIn(vendor, valid_vendors)


class TestAcceleratorsEndpoint(TestHardwareEndpoints):
    """Tests for GET /api/v1/hardware/accelerators endpoint."""

    def test_get_accelerators_returns_200(self):
        """Test that accelerators endpoint returns 200."""
        response = self.client.get("/api/v1/hardware/accelerators")

        self.assertEqual(response.status_code, 200)

    def test_get_accelerators_returns_list(self):
        """Test that accelerators endpoint returns a list."""
        response = self.client.get("/api/v1/hardware/accelerators")
        data = response.json()

        self.assertIsInstance(data, list)

    def test_get_accelerators_includes_cpu(self):
        """Test that CPU is always included in accelerators."""
        response = self.client.get("/api/v1/hardware/accelerators")
        accelerators = response.json()

        cpu_types = [acc["type"] for acc in accelerators]
        self.assertIn("cpu", cpu_types)

    def test_get_accelerators_valid_status(self):
        """Test that all accelerators have valid status."""
        response = self.client.get("/api/v1/hardware/accelerators")
        accelerators = response.json()

        valid_statuses = ["available", "unavailable", "driver_missing", "not_detected", "error"]
        for acc in accelerators:
            self.assertIn(acc["status"], valid_statuses)

    def test_get_accelerators_refresh_parameter(self):
        """Test that refresh parameter is accepted."""
        response = self.client.get("/api/v1/hardware/accelerators?refresh=true")

        self.assertEqual(response.status_code, 200)


class TestRecommendedEndpoint(TestHardwareEndpoints):
    """Tests for GET /api/v1/hardware/recommended endpoint."""

    def test_get_recommended_returns_200(self):
        """Test that recommended endpoint returns 200."""
        response = self.client.get("/api/v1/hardware/recommended")

        self.assertEqual(response.status_code, 200)

    def test_get_recommended_returns_dict(self):
        """Test that recommended endpoint returns a dictionary."""
        response = self.client.get("/api/v1/hardware/recommended")
        data = response.json()

        self.assertIsInstance(data, dict)

    def test_get_recommended_has_required_fields(self):
        """Test that recommended response has required fields."""
        response = self.client.get("/api/v1/hardware/recommended")
        data = response.json()

        self.assertIn("recommended", data)
        self.assertIn("available_accelerators", data)

    def test_get_recommended_available_is_list(self):
        """Test that available_accelerators is a list."""
        response = self.client.get("/api/v1/hardware/recommended")
        data = response.json()

        self.assertIsInstance(data["available_accelerators"], list)

    def test_get_recommended_has_value(self):
        """Test that a recommended accelerator is provided."""
        response = self.client.get("/api/v1/hardware/recommended")
        data = response.json()

        # Should have at least CPU as recommended
        self.assertIsNotNone(data["recommended"])


class TestErrorHandling(TestHardwareEndpoints):
    """Tests for error handling in hardware endpoints."""

    @patch("src.services.hardware.hardware_detection_service.detect_all")
    def test_detect_handles_service_error(self, mock_detect):
        """Test that detection endpoint handles service errors gracefully."""
        mock_detect.side_effect = Exception("Detection failed")

        response = self.client.get("/api/v1/hardware/detect")

        self.assertEqual(response.status_code, 500)
        self.assertIn("detail", response.json())

    def test_invalid_endpoint_returns_404(self):
        """Test that invalid endpoints return 404."""
        response = self.client.get("/api/v1/hardware/invalid")

        self.assertEqual(response.status_code, 404)


class TestResponseTypes(TestHardwareEndpoints):
    """Tests for correct response content types."""

    def test_detect_returns_json(self):
        """Test that detect endpoint returns JSON."""
        response = self.client.get("/api/v1/hardware/detect")

        self.assertEqual(response.headers["content-type"], "application/json")

    def test_cpu_returns_json(self):
        """Test that CPU endpoint returns JSON."""
        response = self.client.get("/api/v1/hardware/cpu")

        self.assertEqual(response.headers["content-type"], "application/json")

    def test_platform_returns_json(self):
        """Test that platform endpoint returns JSON."""
        response = self.client.get("/api/v1/hardware/platform")

        self.assertEqual(response.headers["content-type"], "application/json")

    def test_accelerators_returns_json(self):
        """Test that accelerators endpoint returns JSON."""
        response = self.client.get("/api/v1/hardware/accelerators")

        self.assertEqual(response.headers["content-type"], "application/json")
