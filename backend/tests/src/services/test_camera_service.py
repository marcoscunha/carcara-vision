from unittest import TestCase
from unittest.mock import MagicMock, patch

from src.services.camera_service import CameraService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cap(width=640, height=480, fps=30.0, opened=True, frame_ok=True):
    """Return a mock cv2.VideoCapture-like object."""
    cap = MagicMock()
    cap.isOpened.return_value = opened

    def _get(prop):
        import cv2

        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(width)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(height)
        if prop == cv2.CAP_PROP_FPS:
            return fps
        return 0.0

    cap.get.side_effect = _get
    cap.read.return_value = (frame_ok, MagicMock() if frame_ok else None)
    return cap


def _identity(device_id, *, vendor="046d", product="0825", serial=None, sysfs_parent=None, device_path=None):
    """Build a minimal device identity dict as returned by describe_local_device."""
    return {
        "device_id": device_id,
        "device_path": device_path or f"/dev/v4l/by-id/usb-cam-video-index{device_id}",
        "physical_address": f"pci-0000:00:14.0-usb-0:{device_id}:1.0",
        "usb_vendor_id": vendor,
        "usb_product_id": product,
        "usb_serial_number": serial,
        "usb_id": f"{vendor}:{product}" if vendor and product else None,
    }


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
            patch.object(CameraService, "scan_local_camera_identities", return_value=scanned_cameras),
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
            patch.object(CameraService, "scan_local_camera_identities", return_value=scanned_cameras),
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
            patch.object(CameraService, "scan_local_camera_identities", return_value=scanned_cameras),
        ):
            resolved = CameraService.resolve_local_camera(
                device_path="/dev/v4l/by-id/usb-cam-b-video-index0",
            )

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved["device_id"], 4)
        self.assertEqual(resolved["device_path"], "/dev/v4l/by-id/usb-cam-b-video-index0")


# ---------------------------------------------------------------------------
# scan_local_cameras - deduplication regression tests
# ---------------------------------------------------------------------------


def _make_cv2_cap(width=640, height=480, fps=30.0, frame_ok=True):
    """Return a mock cv2.VideoCapture that reports a readable frame."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.get.side_effect = lambda prop: {
        0: width,  # CAP_PROP_FRAME_WIDTH  = 3 → index 0 in side-effect mapping
        3: width,
        4: height,
        5: fps,
    }.get(prop, 0)
    cap.read.return_value = (frame_ok, MagicMock() if frame_ok else None)
    return cap


class ScanLocalCamerasDeduplicationTests(TestCase):
    """
    Guard against the regression where scan_local_cameras returned a "shadow"
    node for the same physical USB camera (e.g. /dev/video0 AND /dev/video1 from
    one C920 webcam) because the deduplication key mistakenly used device_path,
    which differs per video node (…-video-index0 vs …-video-index1).
    """

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _make_identity(
        self,
        device_id,
        *,
        vendor="046d",
        product="0825",
        serial=None,
        physical="pci-0000:00:14.0-usb-0:1:1.0",
        sysfs_parent="/sys/bus/usb/devices/1-1",
        index=0,
    ):
        return {
            "device_id": device_id,
            "device_path": f"/dev/v4l/by-id/usb-Logitech_C920-video-index{index}",
            "physical_address": physical,
            "usb_vendor_id": vendor,
            "usb_product_id": product,
            "usb_serial_number": serial,
            "usb_id": f"{vendor}:{product}",
            "_sysfs_parent": sysfs_parent,
        }

    # ------------------------------------------------------------------ #
    # Tests                                                                #
    # ------------------------------------------------------------------ #

    def test_same_physical_camera_two_video_nodes_returns_one_entry(self):
        """
        A UVC webcam typically exposes /dev/video0 (capture) and /dev/video1
        (metadata). Both nodes have different device_path suffixes but share the
        same physical identity. Only one entry must be returned.
        """
        identity_node0 = self._make_identity(0, serial="SER001", index=0)
        identity_node1 = self._make_identity(1, serial="SER001", index=1)

        with (
            patch("glob.glob", return_value=["/dev/video0", "/dev/video1"]),
            patch.object(CameraService, "is_capture_device", return_value=True),
            patch("cv2.VideoCapture", return_value=_make_cv2_cap()),
            patch.object(
                CameraService,
                "describe_local_device",
                side_effect=[identity_node0, identity_node1],
            ),
            patch.object(CameraService, "_get_device_path_fallback", return_value="/sys/bus/usb/devices/1-1"),
            patch.object(CameraService, "get_camera_name", return_value="HD Pro Webcam C920"),
            patch.object(CameraService, "get_camera_friendly_name", return_value="Logitech C920"),
            patch.object(CameraService, "get_supported_resolutions", return_value=[(640, 480), (1280, 720)]),
        ):
            cameras = CameraService.scan_local_cameras(max_devices=10)

        self.assertEqual(len(cameras), 1, "Expected exactly one entry for the physical camera")
        self.assertEqual(cameras[0]["device_id"], 0)

    def test_two_different_cameras_both_returned(self):
        """Two distinct cameras must both appear in scan results."""
        identity_cam_a = self._make_identity(0, serial="SER001", physical="usb-0:1", sysfs_parent="/sys/usb/1")
        identity_cam_b = self._make_identity(
            2, vendor="1234", product="5678", serial="SER002", physical="usb-0:2", sysfs_parent="/sys/usb/2"
        )

        with (
            patch("glob.glob", return_value=["/dev/video0", "/dev/video2"]),
            patch.object(CameraService, "is_capture_device", return_value=True),
            patch("cv2.VideoCapture", return_value=_make_cv2_cap()),
            patch.object(
                CameraService,
                "describe_local_device",
                side_effect=[identity_cam_a, identity_cam_b],
            ),
            patch.object(
                CameraService,
                "_get_device_path_fallback",
                side_effect=["/sys/usb/1", "/sys/usb/2"],
            ),
            patch.object(CameraService, "get_camera_name", return_value="Camera"),
            patch.object(CameraService, "get_camera_friendly_name", return_value=None),
            patch.object(CameraService, "get_supported_resolutions", return_value=[]),
        ):
            cameras = CameraService.scan_local_cameras(max_devices=10)

        self.assertEqual(len(cameras), 2, "Expected one entry per distinct physical camera")
        device_ids = {c["device_id"] for c in cameras}
        self.assertEqual(device_ids, {0, 2})

    def test_dedup_uses_sysfs_parent_not_device_path_when_no_serial(self):
        """
        Regression guard: when no serial number is present the key must be the
        sysfs parent path (same for all nodes of the same device), NOT
        device_path which differs per node (index0 / index1).
        """
        # Same physical device: same sysfs parent, different device_path suffixes
        identity_node0 = self._make_identity(0, serial=None, index=0, sysfs_parent="/sys/bus/usb/devices/1-1")
        identity_node1 = self._make_identity(1, serial=None, index=1, sysfs_parent="/sys/bus/usb/devices/1-1")

        sysfs_side_effects = ["/sys/bus/usb/devices/1-1", "/sys/bus/usb/devices/1-1"]

        with (
            patch("glob.glob", return_value=["/dev/video0", "/dev/video1"]),
            patch.object(CameraService, "is_capture_device", return_value=True),
            patch("cv2.VideoCapture", return_value=_make_cv2_cap()),
            patch.object(
                CameraService,
                "describe_local_device",
                side_effect=[identity_node0, identity_node1],
            ),
            patch.object(
                CameraService,
                "_get_device_path_fallback",
                side_effect=sysfs_side_effects,
            ),
            patch.object(CameraService, "get_camera_name", return_value="Webcam"),
            patch.object(CameraService, "get_camera_friendly_name", return_value=None),
            patch.object(CameraService, "get_supported_resolutions", return_value=[]),
        ):
            cameras = CameraService.scan_local_cameras(max_devices=10)

        self.assertEqual(
            len(cameras),
            1,
            "Shadow node must be deduplicated using sysfs parent, not device_path",
        )

    def test_non_capture_device_is_excluded(self):
        """Nodes that fail is_capture_device must never appear in results."""
        with (
            patch("glob.glob", return_value=["/dev/video0", "/dev/video1"]),
            patch.object(
                CameraService,
                "is_capture_device",
                side_effect=lambda device_id=None, device_path=None: device_id == 0,
            ),
            patch("cv2.VideoCapture", return_value=_make_cv2_cap()),
            patch.object(
                CameraService,
                "describe_local_device",
                return_value=self._make_identity(0, serial="SER001"),
            ),
            patch.object(CameraService, "_get_device_path_fallback", return_value="/sys/usb/1"),
            patch.object(CameraService, "get_camera_name", return_value="Webcam"),
            patch.object(CameraService, "get_camera_friendly_name", return_value=None),
            patch.object(CameraService, "get_supported_resolutions", return_value=[]),
        ):
            cameras = CameraService.scan_local_cameras(max_devices=10)

        self.assertEqual(len(cameras), 1)
        self.assertEqual(cameras[0]["device_id"], 0)

    def test_is_capture_device_returns_true_when_v4l2_ctl_absent_and_no_sysfs(self):
        """
        Regression: when v4l2-ctl is not installed and sysfs caps are unreadable
        the function must return True (permissive) so that cameras are not silently
        blocked. OpenCV / downstream operations handle invalid nodes.
        """
        with (
            patch("shutil.which", return_value=None),
            patch("os.path.isfile", return_value=False),
        ):
            result = CameraService.is_capture_device(device_id=0)

        self.assertTrue(result, "Should default to True when v4l2-ctl and sysfs caps are unavailable")

    def test_is_capture_device_uses_sysfs_cap_bitmask_when_v4l2_ctl_absent(self):
        """When v4l2-ctl is absent but sysfs capabilities exist, read the bitmask."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.path.basename", return_value="video0"),
            patch("os.path.realpath", return_value="/dev/video0"),
            patch("os.path.isfile", return_value=True),
            patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=lambda s, *a: s,
                        __exit__=lambda s, *a: None,
                        read=lambda: "0x04000001",  # VIDEO_CAPTURE bit set
                    )
                ),
            ),
        ):
            result = CameraService.is_capture_device(device_id=0)

        self.assertTrue(result)


# ---------------------------------------------------------------------------
# Regression tests — scan_local_cameras deduplication
# ---------------------------------------------------------------------------


class CameraServiceScanDeduplicationTests(TestCase):
    """Guard against shadow-camera regression (multi-node USB cameras showing up twice).

    A UVC webcam exposes two /dev/videoN nodes: a video-capture node and a
    metadata node.  Both nodes share the same USB identity and the same sysfs
    parent directory, so scan_local_cameras must emit exactly ONE entry per
    physical device.
    """

    def _run_scan(self, device_ids, identity_map, sysfs_map, capture_map, cap_map):
        """Run scan_local_cameras with fully-controlled dependencies."""

        def _is_capture(device_id=None, device_path=None, **__):
            return capture_map.get(device_id, True)

        def _describe(device_id=None, device_path=None, **__):
            return identity_map[device_id]

        def _sysfs(device_id):
            return sysfs_map.get(device_id)

        def _video_cap(dev_id):
            return cap_map.get(dev_id, _make_cap())

        with (
            patch("glob.glob", return_value=[f"/dev/video{d}" for d in device_ids]),
            patch.object(CameraService, "is_capture_device", side_effect=_is_capture),
            patch.object(CameraService, "describe_local_device", side_effect=_describe),
            patch.object(CameraService, "_get_device_path_fallback", side_effect=_sysfs),
            patch.object(CameraService, "get_camera_name", return_value="Test Cam"),
            patch.object(CameraService, "get_camera_friendly_name", return_value=None),
            patch.object(CameraService, "get_supported_resolutions", return_value=[(640, 480)]),
            patch(f"{CameraService.__module__}.cv2.VideoCapture", side_effect=_video_cap),
        ):
            return CameraService.scan_local_cameras(max_devices=20)

    # --- deduplication by USB serial number ---

    def test_two_nodes_same_serial_deduplicated_to_one(self):
        """video0 (capture) + video1 with same serial -> 1 result."""
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={
                0: _identity(0, vendor="046d", product="0825", serial="SER001"),
                1: _identity(1, vendor="046d", product="0825", serial="SER001"),
            },
            sysfs_map={0: "/sys/bus/usb/devices/1-1/1-1:1.0", 1: "/sys/bus/usb/devices/1-1/1-1:1.0"},
            capture_map={0: True, 1: True},
            cap_map={0: _make_cap(), 1: _make_cap()},
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["device_id"], 0)

    def test_two_different_serials_both_appear(self):
        """Two physically distinct cameras with different serials -> 2 results."""
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={
                0: _identity(0, vendor="046d", product="0825", serial="SER001"),
                1: _identity(1, vendor="046d", product="0825", serial="SER002"),
            },
            sysfs_map={0: "/sys/bus/usb/devices/1-1/1-1:1.0", 1: "/sys/bus/usb/devices/1-2/1-2:1.0"},
            capture_map={0: True, 1: True},
            cap_map={0: _make_cap(), 1: _make_cap()},
        )
        self.assertEqual(len(results), 2)

    # --- deduplication by sysfs parent (no serial) ---

    def test_two_nodes_same_sysfs_parent_no_serial_deduplicated(self):
        """Same sysfs parent, no serial -> shadow node deduplication."""
        shared_sysfs = "/sys/bus/usb/devices/1-1/1-1:1.0"
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={
                0: _identity(0, vendor="046d", product="0825", serial=None),
                1: _identity(1, vendor="046d", product="0825", serial=None),
            },
            sysfs_map={0: shared_sysfs, 1: shared_sysfs},
            capture_map={0: True, 1: True},
            cap_map={0: _make_cap(), 1: _make_cap()},
        )
        self.assertEqual(len(results), 1, "Shadow node must be deduplicated via shared sysfs parent")

    def test_two_nodes_different_sysfs_parents_no_serial_both_appear(self):
        """Different sysfs parents, no serial -> two distinct cameras."""
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={
                0: _identity(0, vendor="046d", product="0825", serial=None),
                1: _identity(1, vendor="1234", product="5678", serial=None),
            },
            sysfs_map={0: "/sys/bus/usb/devices/1-1/1-1:1.0", 1: "/sys/bus/usb/devices/1-2/1-2:1.0"},
            capture_map={0: True, 1: True},
            cap_map={0: _make_cap(), 1: _make_cap()},
        )
        self.assertEqual(len(results), 2)

    def test_device_path_index_suffix_does_not_prevent_dedup(self):
        """by-id paths with -index0 / -index1 suffixes must NOT prevent deduplication.

        This is the exact regression introduced when the old (physical_address, usb_id)
        key was replaced with one that fell back to device_path, causing both video nodes
        to appear as separate cameras.
        """
        shared_sysfs = "/sys/bus/usb/devices/1-1/1-1:1.0"
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={
                0: _identity(
                    0,
                    vendor="046d",
                    product="0825",
                    serial=None,
                    device_path="/dev/v4l/by-id/usb-Logitech_C920-video-index0",
                ),
                1: _identity(
                    1,
                    vendor="046d",
                    product="0825",
                    serial=None,
                    device_path="/dev/v4l/by-id/usb-Logitech_C920-video-index1",
                ),
            },
            sysfs_map={0: shared_sysfs, 1: shared_sysfs},
            capture_map={0: True, 1: True},
            cap_map={0: _make_cap(), 1: _make_cap()},
        )
        self.assertEqual(len(results), 1, "Cameras with -index0/-index1 device_path suffixes must not bypass dedup")

    # --- metadata node filtering ---

    def test_metadata_node_excluded_by_is_capture_check(self):
        """Metadata nodes that fail is_capture_device must be skipped entirely."""
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={
                0: _identity(0, vendor="046d", product="0825", serial="SER001"),
                1: _identity(1, vendor="046d", product="0825", serial="SER001"),
            },
            sysfs_map={0: "/sys/bus/usb/devices/1-1/1-1:1.0", 1: "/sys/bus/usb/devices/1-1/1-1:1.0"},
            capture_map={0: True, 1: False},  # video1 is metadata-only
            cap_map={0: _make_cap(), 1: _make_cap()},
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["device_id"], 0)

    def test_no_cameras_when_all_nodes_fail_capture_check(self):
        """If every node fails the capture check, scan returns empty list."""
        results = self._run_scan(
            device_ids=[0, 1],
            identity_map={0: _identity(0), 1: _identity(1)},
            sysfs_map={},
            capture_map={0: False, 1: False},
            cap_map={},
        )
        self.assertEqual(results, [])

    # --- is_capture_device fallback behaviour ---

    def test_is_capture_device_returns_true_without_v4l2_ctl_and_no_sysfs(self):
        """Without v4l2-ctl and without readable sysfs caps, assume capture is possible.

        Returning False here would block all cameras when v4l2-ctl is not installed.
        """
        with (
            patch("shutil.which", return_value=None),
            patch("os.path.realpath", return_value="/dev/video0"),
            patch("os.path.basename", return_value="video0"),
            patch("os.path.isfile", return_value=False),  # no sysfs caps file
        ):
            result = CameraService.is_capture_device(device_id=0)
        self.assertTrue(result, "Must return True (permissive) when v4l2-ctl absent and sysfs unreadable")

    def test_is_capture_device_uses_sysfs_bitmask_without_v4l2_ctl_capture_node(self):
        """Capture node: sysfs bitmask with VIDEO_CAPTURE bit set -> True."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.path.realpath", return_value="/dev/video0"),
            patch("os.path.basename", return_value="video0"),
            patch("os.path.isfile", return_value=True),
            patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=lambda s, *a: s,
                        __exit__=lambda s, *a: None,
                        read=lambda: "0x00000001",
                    )
                ),
            ),
        ):
            self.assertTrue(CameraService.is_capture_device(device_id=0))

    def test_is_capture_device_uses_sysfs_bitmask_without_v4l2_ctl_metadata_node(self):
        """Metadata node: sysfs bitmask without VIDEO_CAPTURE bit -> False."""
        with (
            patch("shutil.which", return_value=None),
            patch("os.path.realpath", return_value="/dev/video1"),
            patch("os.path.basename", return_value="video1"),
            patch("os.path.isfile", return_value=True),
            patch(
                "builtins.open",
                MagicMock(
                    return_value=MagicMock(
                        __enter__=lambda s, *a: s,
                        __exit__=lambda s, *a: None,
                        read=lambda: "0x04000000",  # metadata only — no VIDEO_CAPTURE bit
                    )
                ),
            ),
        ):
            self.assertFalse(CameraService.is_capture_device(device_id=1))
