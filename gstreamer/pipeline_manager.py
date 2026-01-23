#!/usr/bin/env python3
"""
GStreamer Pipeline Manager Service.

This service manages GStreamer pipelines for video streaming,
replacing go2rtc functionality with native GStreamer pipelines.
"""
import asyncio
import json
import logging
import os
import signal
import sys
import threading
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from threading import Lock
from typing import Any
from typing import Dict
from typing import Optional

import gi
from gi.repository import GLib
from gi.repository import Gst
from gi.repository import GstRtspServer

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')

# Initialize GStreamer
Gst.init(None)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class StreamConfig:
    """Configuration for a video stream."""
    name: str
    source_type: str  # 'v4l2', 'rtsp', 'test'
    source_uri: Optional[str] = None
    device_id: Optional[int] = None
    width: int = 640
    height: int = 360
    framerate: int = 30
    codec: str = "h264"
    bitrate: int = 2000000

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "device_id": self.device_id,
            "width": self.width,
            "height": self.height,
            "framerate": self.framerate,
            "codec": self.codec,
            "bitrate": self.bitrate,
        }


@dataclass
class PipelineInfo:
    """Information about a running pipeline."""
    config: StreamConfig
    pipeline: Optional[Gst.Pipeline] = None
    status: PipelineStatus = PipelineStatus.STOPPED
    error_message: Optional[str] = None


class GStreamerPipelineManager:
    """
    Manages GStreamer pipelines for video streaming.

    Provides functionality to:
    - Create and manage video capture pipelines
    - Stream to RTSP server (MediaMTX)
    - Support V4L2 (USB cameras), RTSP sources, and test sources
    """

    def __init__(self, mediamtx_host: str = "mediamtx", mediamtx_rtsp_port: int = 8554):
        self.mediamtx_host = mediamtx_host
        self.mediamtx_rtsp_port = mediamtx_rtsp_port
        self.pipelines: Dict[str, PipelineInfo] = {}
        self.lock = Lock()
        self.main_loop: Optional[GLib.MainLoop] = None

        logger.info(f"GStreamer Pipeline Manager initialized")
        logger.info(f"MediaMTX target: rtsp://{mediamtx_host}:{mediamtx_rtsp_port}")

    def _build_v4l2_source(self, config: StreamConfig) -> str:
        """Build V4L2 source element string."""
        return (
            f"v4l2src device=/dev/video{config.device_id} ! "
            f"video/x-raw,width={config.width},height={config.height},"
            f"framerate={config.framerate}/1 ! "
            f"videoconvert ! videoscale"
        )

    def _build_rtsp_source(self, config: StreamConfig) -> str:
        """Build RTSP source element string."""
        return (
            f"rtspsrc location={config.source_uri} latency=0 ! "
            f"rtph264depay ! h264parse"
        )

    def _build_test_source(self, config: StreamConfig) -> str:
        """Build test video source element string."""
        return (
            f"videotestsrc pattern=ball ! "
            f"video/x-raw,width={config.width},height={config.height},"
            f"framerate={config.framerate}/1 ! "
            f"videoconvert"
        )

    def _build_encoder(self, config: StreamConfig) -> str:
        """Build encoder element string based on codec."""
        if config.codec == "h264":
            # Try hardware encoding first, fallback to software
            # Check for available encoders
            x264_enc = (
                f"x264enc tune=zerolatency bitrate={config.bitrate // 1000} "
                f"speed-preset=ultrafast key-int-max=30"
            )
            return f"{x264_enc} ! h264parse"
        elif config.codec == "h265":
            return f"x265enc tune=zerolatency bitrate={config.bitrate // 1000} ! h265parse"
        else:
            # Default to H.264
            return f"x264enc tune=zerolatency ! h264parse"

    def _build_rtsp_sink(self, stream_name: str) -> str:
        """Build RTSP client sink for MediaMTX."""
        rtsp_url = f"rtsp://{self.mediamtx_host}:{self.mediamtx_rtsp_port}/{stream_name}"
        return f"rtspclientsink location={rtsp_url} latency=0"

    def build_pipeline_string(self, config: StreamConfig) -> str:
        """
        Build complete GStreamer pipeline string.

        Pipeline structure:
        source -> encoder -> rtsp_sink (to MediaMTX)
        """
        # Build source based on type
        if config.source_type == "v4l2":
            source = self._build_v4l2_source(config)
            encoder = f" ! {self._build_encoder(config)}"
        elif config.source_type == "rtsp":
            source = self._build_rtsp_source(config)
            encoder = ""  # RTSP source is usually already encoded
        elif config.source_type == "test":
            source = self._build_test_source(config)
            encoder = f" ! {self._build_encoder(config)}"
        else:
            raise ValueError(f"Unknown source type: {config.source_type}")

        # Build sink
        sink = self._build_rtsp_sink(config.name)

        pipeline_str = f"{source}{encoder} ! {sink}"
        logger.debug(f"Pipeline string for {config.name}: {pipeline_str}")

        return pipeline_str

    def _on_bus_message(self, bus: Gst.Bus, message: Gst.Message, stream_name: str) -> bool:
        """Handle GStreamer bus messages."""
        msg_type = message.type

        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline {stream_name} error: {err.message}")
            logger.debug(f"Debug info: {debug}")

            with self.lock:
                if stream_name in self.pipelines:
                    self.pipelines[stream_name].status = PipelineStatus.ERROR
                    self.pipelines[stream_name].error_message = err.message

        elif msg_type == Gst.MessageType.EOS:
            logger.info(f"Pipeline {stream_name} reached end of stream")
            with self.lock:
                if stream_name in self.pipelines:
                    self.pipelines[stream_name].status = PipelineStatus.STOPPED

        elif msg_type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.pipelines.get(stream_name, PipelineInfo(StreamConfig("", ""))).pipeline:
                old, new, pending = message.parse_state_changed()
                logger.debug(f"Pipeline {stream_name} state: {old.value_nick} -> {new.value_nick}")

                if new == Gst.State.PLAYING:
                    with self.lock:
                        if stream_name in self.pipelines:
                            self.pipelines[stream_name].status = PipelineStatus.RUNNING

        elif msg_type == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            logger.warning(f"Pipeline {stream_name} warning: {warn.message}")

        return True

    def create_pipeline(self, config: StreamConfig) -> bool:
        """
        Create a new GStreamer pipeline.

        Args:
            config: Stream configuration

        Returns:
            True if pipeline was created successfully
        """
        with self.lock:
            if config.name in self.pipelines:
                logger.warning(f"Pipeline {config.name} already exists")
                return False

            try:
                pipeline_str = self.build_pipeline_string(config)
                logger.info(f"Creating pipeline: {pipeline_str}")

                pipeline = Gst.parse_launch(pipeline_str)

                if not pipeline:
                    logger.error(f"Failed to create pipeline for {config.name}")
                    return False

                # Set up bus message handling
                bus = pipeline.get_bus()
                bus.add_signal_watch()
                bus.connect("message", self._on_bus_message, config.name)

                self.pipelines[config.name] = PipelineInfo(
                    config=config,
                    pipeline=pipeline,
                    status=PipelineStatus.STOPPED
                )

                logger.info(f"Pipeline {config.name} created successfully")
                return True

            except Exception as e:
                logger.error(f"Error creating pipeline {config.name}: {e}")
                return False

    def start_pipeline(self, stream_name: str) -> bool:
        """Start a pipeline by name."""
        with self.lock:
            if stream_name not in self.pipelines:
                logger.error(f"Pipeline {stream_name} not found")
                return False

            pipeline_info = self.pipelines[stream_name]

            if pipeline_info.status == PipelineStatus.RUNNING:
                logger.warning(f"Pipeline {stream_name} is already running")
                return True

            pipeline_info.status = PipelineStatus.STARTING
            ret = pipeline_info.pipeline.set_state(Gst.State.PLAYING)

            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error(f"Failed to start pipeline {stream_name}")
                pipeline_info.status = PipelineStatus.ERROR
                return False

            logger.info(f"Pipeline {stream_name} started")
            return True

    def stop_pipeline(self, stream_name: str) -> bool:
        """Stop a pipeline by name."""
        with self.lock:
            if stream_name not in self.pipelines:
                logger.error(f"Pipeline {stream_name} not found")
                return False

            pipeline_info = self.pipelines[stream_name]
            pipeline_info.pipeline.set_state(Gst.State.NULL)
            pipeline_info.status = PipelineStatus.STOPPED

            logger.info(f"Pipeline {stream_name} stopped")
            return True

    def remove_pipeline(self, stream_name: str) -> bool:
        """Remove a pipeline by name."""
        self.stop_pipeline(stream_name)

        with self.lock:
            if stream_name in self.pipelines:
                del self.pipelines[stream_name]
                logger.info(f"Pipeline {stream_name} removed")
                return True
            return False

    def get_pipeline_status(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a pipeline."""
        with self.lock:
            if stream_name not in self.pipelines:
                return None

            info = self.pipelines[stream_name]
            return {
                "name": stream_name,
                "status": info.status.value,
                "config": info.config.to_dict(),
                "error": info.error_message
            }

    def list_pipelines(self) -> Dict[str, Dict[str, Any]]:
        """List all pipelines and their status."""
        with self.lock:
            return {
                name: {
                    "status": info.status.value,
                    "config": info.config.to_dict(),
                    "error": info.error_message
                }
                for name, info in self.pipelines.items()
            }

    def run(self):
        """Run the main loop."""
        self.main_loop = GLib.MainLoop()

        # Handle shutdown signals
        def shutdown_handler(signum, frame):
            logger.info("Shutting down...")
            for name in list(self.pipelines.keys()):
                self.stop_pipeline(name)
            if self.main_loop:
                self.main_loop.quit()

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        logger.info("GStreamer Pipeline Manager running...")
        self.main_loop.run()


# Simple HTTP API for pipeline management


class PipelineAPIHandler(BaseHTTPRequestHandler):
    """Simple HTTP API handler for pipeline management."""

    manager: GStreamerPipelineManager = None

    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == '/api/streams' or self.path == '/api/pipelines':
            pipelines = self.manager.list_pipelines()
            self._send_json(pipelines)
        elif self.path == '/health':
            self._send_json({"status": "ok"})
        elif self.path.startswith('/api/streams/'):
            stream_name = self.path.split('/')[-1]
            status = self.manager.get_pipeline_status(stream_name)
            if status:
                self._send_json(status)
            else:
                self._send_json({"error": "Stream not found"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_PUT(self):
        if self.path == '/api/streams':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body)
                config = StreamConfig(
                    name=data['name'],
                    source_type=data.get('source_type', 'v4l2'),
                    source_uri=data.get('source_uri'),
                    device_id=data.get('device_id'),
                    width=data.get('width', 640),
                    height=data.get('height', 360),
                    framerate=data.get('framerate', 30),
                    codec=data.get('codec', 'h264'),
                    bitrate=data.get('bitrate', 2000000),
                )

                if self.manager.create_pipeline(config):
                    if self.manager.start_pipeline(config.name):
                        self._send_json({"status": "created", "name": config.name}, 201)
                    else:
                        self._send_json({"error": "Failed to start pipeline"}, 500)
                else:
                    self._send_json({"error": "Failed to create pipeline"}, 500)
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self):
        if self.path.startswith('/api/streams/'):
            stream_name = self.path.split('/')[-1]
            if self.manager.remove_pipeline(stream_name):
                self._send_json({"status": "deleted"})
            else:
                self._send_json({"error": "Stream not found"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {args[0]}")


def run_api_server(manager: GStreamerPipelineManager, port: int = 8085):
    """Run the HTTP API server."""
    PipelineAPIHandler.manager = manager
    server = HTTPServer(('0.0.0.0', port), PipelineAPIHandler)
    logger.info(f"API server listening on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    # Configuration from environment
    MEDIAMTX_HOST = os.getenv("MEDIAMTX_HOST", "mediamtx")
    MEDIAMTX_RTSP_PORT = int(os.getenv("MEDIAMTX_RTSP_PORT", "8554"))
    API_PORT = int(os.getenv("GSTREAMER_API_PORT", "8085"))

    # Create manager
    manager = GStreamerPipelineManager(
        mediamtx_host=MEDIAMTX_HOST,
        mediamtx_rtsp_port=MEDIAMTX_RTSP_PORT
    )

    # Start API server in background thread
    api_thread = threading.Thread(target=run_api_server, args=(manager, API_PORT), daemon=True)
    api_thread.start()

    # Run main loop
    manager.run()
