"""
GStreamer streaming service.

This module provides integration with GStreamer pipeline manager and MediaMTX
for managing video streams, replacing go2rtc functionality.
"""

import logging
from typing import Any

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class GStreamerService:
    """Service for managing streams via GStreamer and MediaMTX."""

    def __init__(self):
        self.gstreamer_api_url = settings.GSTREAMER_API_URL
        self.mediamtx_api_url = settings.MEDIAMTX_API_URL
        self.rtsp_host = settings.MEDIAMTX_RTSP_HOST
        self.rtsp_port = settings.MEDIAMTX_RTSP_PORT
        self.webrtc_port = settings.MEDIAMTX_WEBRTC_PORT
        self.hls_port = settings.MEDIAMTX_HLS_PORT

    def _get_gstreamer_api_url(self, endpoint: str) -> str:
        """Build API URL for GStreamer pipeline manager."""
        return f"{self.gstreamer_api_url}/api{endpoint}"

    def _get_mediamtx_api_url(self, endpoint: str) -> str:
        """Build API URL for MediaMTX."""
        return f"{self.mediamtx_api_url}/v3{endpoint}"

    async def health_check(self) -> bool:
        """Check if GStreamer and MediaMTX services are available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check GStreamer service
                gst_response = await client.get(f"{self.gstreamer_api_url}/health")
                if gst_response.status_code != 200:
                    logger.error("GStreamer service health check failed")
                    return False

                # Check MediaMTX service
                mtx_response = await client.get(f"{self.mediamtx_api_url}/v3/paths/list")
                if mtx_response.status_code != 200:
                    logger.error("MediaMTX service health check failed")
                    return False

                return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_streams(self) -> dict[str, Any]:
        """Get all registered streams from GStreamer pipeline manager."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._get_gstreamer_api_url("/streams"))
                if response.status_code == 200:
                    return response.json()
                logger.error(f"Failed to get streams: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error getting streams from GStreamer: {e}")
            return {}

    async def get_mediamtx_paths(self) -> dict[str, Any]:
        """Get all paths from MediaMTX."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self._get_mediamtx_api_url("/paths/list"))
                if response.status_code == 200:
                    return response.json()
                logger.error(f"Failed to get MediaMTX paths: {response.status_code}")
                return {}
        except Exception as e:
            logger.error(f"Error getting paths from MediaMTX: {e}")
            return {}

    async def add_stream(
        self,
        name: str,
        source_type: str,
        source_uri: str | None = None,
        device_id: int | None = None,
        device_path: str | None = None,
        width: int = 640,
        height: int = 360,
        framerate: int = 30,
        codec: str = "h264",
    ) -> bool:
        """
        Add or update a stream in GStreamer pipeline manager.

        Args:
            name: Unique stream name/identifier
            source_type: Type of source ('v4l2', 'rtsp', 'test')
            source_uri: Source URI for RTSP streams
            device_id: Device ID for V4L2 sources (legacy, prefer device_path)
            device_path: Persistent device path for V4L2 sources (preferred)
            width: Video width
            height: Video height
            framerate: Target framerate
            codec: Video codec (h264, h265)

        Returns:
            True if stream was added successfully
        """
        try:
            payload = {
                "name": name,
                "source_type": source_type,
                "source_uri": source_uri,
                "device_id": device_id,
                "device_path": device_path,
                "width": width,
                "height": height,
                "framerate": framerate,
                "codec": codec,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(self._get_gstreamer_api_url("/streams"), json=payload)
                if response.status_code in (200, 201):
                    logger.info(f"Stream '{name}' added to GStreamer")
                    return True
                else:
                    logger.error(f"Failed to add stream '{name}': {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error adding stream '{name}' to GStreamer: {e}")
            return False

    async def remove_stream(self, name: str) -> bool:
        """
        Remove a stream from GStreamer pipeline manager.

        Args:
            name: Stream name to remove

        Returns:
            True if stream was removed successfully
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(self._get_gstreamer_api_url(f"/streams/{name}"))
                if response.status_code in (200, 204):
                    logger.info(f"Stream '{name}' removed from GStreamer")
                    return True
                else:
                    logger.warning(f"Failed to remove stream '{name}': {response.status_code}")
                    return False
        except Exception as e:
            logger.error(f"Error removing stream '{name}' from GStreamer: {e}")
            return False

    def get_stream_urls(self, stream_name: str, host: str | None = None) -> dict[str, str]:
        """
        Get all available URLs for a stream.

        Includes both the raw stream URLs and the annotated (AI-overlaid)
        stream URLs served from the ``annotated_{stream_name}`` MediaMTX path.

        Args:
            stream_name: Name of the stream in GStreamer/MediaMTX
            host: Optional host override for URL generation

        Returns:
            Dictionary with URLs for different protocols
        """
        url_host = host or self.rtsp_host
        annotated = f"annotated_{stream_name}"

        return {
            # Raw stream
            "rtsp": f"rtsp://{url_host}:{self.rtsp_port}/{stream_name}",
            "webrtc": f"http://{url_host}:{self.webrtc_port}/{stream_name}/whep",
            "hls": f"http://{url_host}:{self.hls_port}/{stream_name}/index.m3u8",
            "mse": f"http://{url_host}:{self.webrtc_port}/{stream_name}",
            "mjpeg": f"http://{url_host}:{self.hls_port}/{stream_name}/index.m3u8",
            "ws": f"ws://{url_host}:{self.webrtc_port}/{stream_name}/ws",
            # Annotated stream (server-side AI overlay pushed by InferenceWorker)
            "annotated_rtsp": f"rtsp://{url_host}:{self.rtsp_port}/{annotated}",
            "annotated_webrtc": f"http://{url_host}:{self.webrtc_port}/{annotated}/whep",
            "annotated_hls": f"http://{url_host}:{self.hls_port}/{annotated}/index.m3u8",
        }

    def build_source_config(
        self,
        camera_type: str,
        rtsp_url: str | None = None,
        device_id: int | None = None,
        device_path: str | None = None,
        width: int = 640,
        height: int = 360,
        codec: str = "h264",
    ) -> dict[str, Any]:
        """
        Build a source configuration for GStreamer pipeline.

        Args:
            camera_type: Type of camera ('rtsp', 'usb', 'local')
            rtsp_url: RTSP URL for network cameras
            device_id: Device ID for local cameras (legacy, prefer device_path)
            device_path: Persistent device path (e.g. /dev/v4l/by-id/...)
            width: Video width
            height: Video height
            codec: Video codec (h264, mjpeg, etc.)

        Returns:
            Configuration dictionary for GStreamer

        Raises:
            ValueError: If required parameters are missing
        """
        if camera_type == "rtsp":
            if not rtsp_url:
                raise ValueError("RTSP URL is required for RTSP cameras")
            return {
                "source_type": "rtsp",
                "source_uri": rtsp_url,
                "device_id": None,
                "device_path": None,
                "width": width,
                "height": height,
                "codec": codec,
            }

        elif camera_type in ("usb", "local"):
            if device_path is None and device_id is None:
                raise ValueError("Device path or device ID is required for USB/local cameras")
            return {
                "source_type": "v4l2",
                "source_uri": None,
                "device_id": device_id,
                "device_path": device_path,
                "width": width,
                "height": height,
                "codec": codec,
            }

        else:
            raise ValueError(f"Unsupported camera type: {camera_type}")


# Global service instance
gstreamer_service = GStreamerService()
