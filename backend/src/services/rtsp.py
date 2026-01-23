"""
RTSP streaming service using go2rtc.

DEPRECATED: This module is deprecated and will be removed in a future version.
Please use gstreamer.py (GStreamerService) instead for managing video streams.

This module provides integration with go2rtc for managing RTSP streams,
supporting WebRTC, HLS, MSE, and MJPEG protocols.
"""
import logging
import warnings
from typing import Any
from typing import Dict
from typing import Optional

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

# Emit deprecation warning on import
warnings.warn(
    "The rtsp module (Go2RTCService) is deprecated and will be removed in a future version. "
    "Please use gstreamer.py (GStreamerService) instead.",
    DeprecationWarning,
    stacklevel=2
)


class Go2RTCService:
    """Service for managing streams via go2rtc API."""

    def __init__(self):
        self.base_url = settings.GO2RTC_URL
        self.rtsp_host = settings.GO2RTC_RTSP_HOST
        self.rtsp_port = settings.GO2RTC_RTSP_PORT

    def _get_api_url(self, endpoint: str) -> str:
        """Build API URL for go2rtc."""
        return f"{self.base_url}/api{endpoint}"

    async def health_check(self) -> bool:
        """Check if go2rtc service is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self._get_api_url("/streams"))
                return response.status_code == 200
        except Exception as e:
            logger.error(f"go2rtc health check failed: {e}")
            return False

    async def get_streams(self) -> Dict[str, Any]:
        """Get all registered streams from go2rtc."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._get_api_url("/streams"))
                if response.status_code == 200:
                    return response.json()
                logger.error(f"Failed to get streams: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error getting streams from go2rtc: {e}")
            return {}

    async def add_stream(self, name: str, source_url: str) -> bool:
        """
        Add or update a stream in go2rtc.

        Args:
            name: Unique stream name/identifier
            source_url: Source URL (RTSP, FFmpeg device, etc.)

        Returns:
            True if stream was added successfully
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # go2rtc API: PUT /api/streams?src=<source>&name=<name>
                response = await client.put(
                    self._get_api_url("/streams"),
                    params={"src": source_url, "name": name}
                )
                if response.status_code in (200, 201):
                    logger.info(f"Stream '{name}' added to go2rtc with source: {source_url}")
                    return True
                else:
                    logger.error(f"Failed to add stream '{name}': {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error adding stream '{name}' to go2rtc: {e}")
            return False

    async def remove_stream(self, name: str) -> bool:
        """
        Remove a stream from go2rtc.

        Args:
            name: Stream name to remove

        Returns:
            True if stream was removed successfully
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    self._get_api_url("/streams"),
                    params={"name": name}
                )
                if response.status_code in (200, 204):
                    logger.info(f"Stream '{name}' removed from go2rtc")
                    return True
                else:
                    logger.warning(f"Failed to remove stream '{name}': {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Error removing stream '{name}' from go2rtc: {e}")
            return False

    def get_stream_urls(self, stream_name: str, host: Optional[str] = None) -> Dict[str, str]:
        """
        Get all available URLs for a stream.

        Args:
            stream_name: Name of the stream in go2rtc
            host: Optional host override for URL generation

        Returns:
            Dictionary with URLs for different protocols
        """
        # Use provided host or default to rtsp_host
        url_host = host or self.rtsp_host

        # Extract just the hostname from base_url for API endpoints
        api_host = self.base_url.replace("http://", "").replace("https://", "").split(":")[0]
        if host:
            api_host = host

        # go2rtc default port is 1984 for HTTP API
        api_port = self.base_url.split(":")[-1] if ":" in self.base_url else "1984"

        return {
            "rtsp": f"rtsp://{url_host}:{self.rtsp_port}/{stream_name}",
            "webrtc": f"http://{api_host}:{api_port}/api/webrtc?src={stream_name}",
            "hls": f"http://{api_host}:{api_port}/api/stream.m3u8?src={stream_name}",
            "mse": f"http://{api_host}:{api_port}/api/stream.mp4?src={stream_name}",
            "mjpeg": f"http://{api_host}:{api_port}/api/frame.jpeg?src={stream_name}",
            "ws": f"ws://{api_host}:{api_port}/api/ws?src={stream_name}"
        }

    def build_source_url(
        self,
        camera_type: str,
        rtsp_url: Optional[str] = None,
        device_id: Optional[int] = None,
        width: int = 640,
        height: int = 360,
        codec: str = "h264"
    ) -> str:
        """
        Build a source URL for go2rtc based on camera type.

        Args:
            camera_type: Type of camera ('rtsp', 'usb', 'local')
            rtsp_url: RTSP URL for network cameras
            device_id: Device ID for local cameras (e.g., /dev/video0)
            width: Video width
            height: Video height
            codec: Video codec (h264, mjpeg, etc.)

        Returns:
            Formatted source URL for go2rtc

        Raises:
            ValueError: If required parameters are missing
        """
        if camera_type == "rtsp":
            if not rtsp_url:
                raise ValueError("RTSP URL is required for RTSP cameras")
            return rtsp_url

        elif camera_type in ("usb", "local"):
            if device_id is None:
                raise ValueError("Device ID is required for USB/local cameras")
            # FFmpeg device source format for go2rtc
            # Note: Additional FFmpeg options should be configured in go2rtc.yaml
            # to avoid space-related security restrictions in the API
            return f"ffmpeg:device?video={device_id}&video_size={width}x{height}#video={codec}"

        else:
            raise ValueError(f"Unsupported camera type: {camera_type}")


# Global service instance
go2rtc_service = Go2RTCService()
