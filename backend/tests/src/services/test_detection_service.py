from unittest import TestCase

import numpy as np
from src.core.config import settings
from src.services.camera_service import CameraService
from src.services.object_detection import ObjectDetectionService


class ObjectDetectionServiceTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Set up resources shared across all tests."""
        cls.detection_service = ObjectDetectionService(model_name=settings.DEFAULT_MODEL)
        cls.camera_service = CameraService()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up resources shared across all tests."""
        cls.detection_service = None
        cls.camera_service = None
        super().tearDownClass()

    def setUp(self):
        """Set up resources for each individual test."""
        super().setUp()

    def tearDown(self) -> None:
        """Clean up resources for each individual test."""
        super().tearDown()

    def test_model_loading(self):
        """Test if the model loads correctly."""
        # Arrange
        # No specific arrangement required for this test.

        # Act
        device = self.detection_service.device

        # Assert
        self.assertIn(device, ["cuda", "cpu"], "Device should be either 'cuda' or 'cpu'")
        print(f"Model loaded on device: {device}")

        # Clean
        # No specific cleanup required for this test.

    def test_scan_local_cameras(self):
        """Test scanning for local cameras."""
        # Arrange
        # No specific arrangement required for this test.

        # Act
        cameras = self.camera_service.scan_local_cameras()

        # Assert
        self.assertIsInstance(cameras, list, "Cameras should be a list")
        print(f"Available cameras: {cameras}")

        # Clean
        # No specific cleanup required for this test.

    def test_detection_on_dummy_frame(self):
        """Test detection on a dummy frame."""
        # Arrange
        dummy_frame = np.zeros((640, 480, 3), dtype=np.uint8)  # Black image

        # Act
        detections = self.detection_service.detect(dummy_frame)

        # Assert
        self.assertIsInstance(detections, list, "Detections should be a list")
        print(f"Detections on dummy frame: {detections}")

        # Clean
        # No specific cleanup required for this test.

    def test_process_local_camera_stream(self):
        """Test processing a local camera stream."""
        # Arrange
        cameras = self.camera_service.scan_local_cameras()

        if cameras:
            device_id = cameras[0]["device_id"]

            # Act
            frame = self.camera_service.process_stream(stream_url=None, camera_type="local", device_id=device_id)

            # Assert
            self.assertIsNotNone(frame, "Failed to capture a frame from the local camera")
            print("Successfully captured a frame from the local camera.")

            # Clean
            # No specific cleanup required for this test.
        else:
            self.skipTest("No local cameras available for testing.")
