from unittest import TestCase
from unittest.mock import patch

from src.services.camera_service import CameraService


class CameraServiceIdentityResolutionTests(TestCase):
    def test_resolve_local_camera_prefers_usb_serial_number(self):
        scanned_cameras = [
            {
                "device_id": 2,
                "device_path": "/dev/v4l/by-id/usb-cam-a-video-index0",
                "physical_address": "pci-0000:00:14.0-usb-0:1:1.0",
                "usb_vendor_id": "046d",
                "usb_product_id": "0825",
                "usb_serial_number": "SER123",
                "usb_id": "046d:0825",
            },
            {
                "device_id": 5,
                "device_path": "/dev/v4l/by-id/usb-cam-b-video-index0",
                "physical_address": "pci-0000:00:14.0-usb-0:2:1.0",
                "usb_vendor_id": "046d",
                "usb_product_id": "0825",
                "usb_serial_number": "SER999",
                "usb_id": "046d:0825",
            },
        ]

        with (
            patch.object(CameraService, "describe_local_device", return_value=None),
            patch.object(CameraService, "scan_local_cameras", return_value=scanned_cameras),
        ):
            resolved = CameraService.resolve_local_camera(
                device_path="/dev/v4l/by-id/usb-stale-video-index0",
                usb_vendor_id="046d",
                usb_product_id="0825",
                usb_serial_number="SER123",
            )

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["device_id"], 2)
        self.assertEqual(resolved["usb_serial_number"], "SER123")

    def test_resolve_local_camera_rejects_ambiguous_vendor_product_match(self):
        scanned_cameras = [
            {
                "device_id": 2,
                "device_path": "/dev/v4l/by-id/usb-cam-a-video-index0",
                "physical_address": "pci-0000:00:14.0-usb-0:1:1.0",
                "usb_vendor_id": "046d",
                "usb_product_id": "0825",
                "usb_serial_number": "SER123",
                "usb_id": "046d:0825",
            },
            {
                "device_id": 5,
                "device_path": "/dev/v4l/by-id/usb-cam-b-video-index0",
                "physical_address": "pci-0000:00:14.0-usb-0:2:1.0",
                "usb_vendor_id": "046d",
                "usb_product_id": "0825",
                "usb_serial_number": "SER999",
                "usb_id": "046d:0825",
            },
        ]

        with (
            patch.object(CameraService, "describe_local_device", return_value=None),
            patch.object(CameraService, "scan_local_cameras", return_value=scanned_cameras),
        ):
            resolved = CameraService.resolve_local_camera(
                usb_vendor_id="046d",
                usb_product_id="0825",
            )

        self.assertIsNone(resolved)

    def test_resolve_local_camera_uses_exact_persistent_path_when_unique(self):
        scanned_cameras = [
            {
                "device_id": 1,
                "device_path": "/dev/v4l/by-id/usb-cam-a-video-index0",
                "physical_address": "pci-0000:00:14.0-usb-0:1:1.0",
                "usb_vendor_id": "046d",
                "usb_product_id": "0825",
                "usb_serial_number": None,
                "usb_id": "046d:0825",
            },
            {
                "device_id": 4,
                "device_path": "/dev/v4l/by-id/usb-cam-b-video-index0",
                "physical_address": "pci-0000:00:14.0-usb-0:2:1.0",
                "usb_vendor_id": "1234",
                "usb_product_id": "5678",
                "usb_serial_number": None,
                "usb_id": "1234:5678",
            },
        ]

        with (
            patch.object(CameraService, "describe_local_device", return_value=None),
            patch.object(CameraService, "scan_local_cameras", return_value=scanned_cameras),
        ):
            resolved = CameraService.resolve_local_camera(
                device_path="/dev/v4l/by-id/usb-cam-b-video-index0",
            )

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["device_id"], 4)
        self.assertEqual(resolved["device_path"], "/dev/v4l/by-id/usb-cam-b-video-index0")
