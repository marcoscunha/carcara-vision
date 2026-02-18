"""
Annotated Stream Writer.

Pushes annotated (AI-overlaid) video frames as a separate RTSP stream back
to MediaMTX using an FFmpeg child process.

The RTSP path published is  ``annotated_{stream_name}`` so MediaMTX exposes
it at the same media-server host alongside the raw stream.

Architecture::

    InferenceWorker
        │  annotated np.ndarray (BGR, HWC)
        ▼
    AnnotatedStreamWriter.push_frame(frame)
        │  raw BGR bytes  →  ffmpeg stdin pipe
        ▼
    ffmpeg -f rawvideo -i pipe:0 ... -f rtsp rtsp://mediamtx:8554/annotated_<name>
        ▼
    MediaMTX  →  WebRTC / HLS / RTSP to browser

The writer starts FFmpeg lazily on the first ``push_frame`` call and
restarts it automatically if the process dies.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

_FFMPEG_BINARY = "ffmpeg"


class AnnotatedStreamWriter:
    """
    Thread-safe writer that pipes BGR frames into an FFmpeg process
    which re-publishes them to MediaMTX as RTSP.

    Args:
        stream_name:  Raw stream name (e.g. ``camera_1_3_front``).
        mediamtx_rtsp_url: Full RTSP base URL of MediaMTX,
                           e.g. ``rtsp://mediamtx:8554``.
        width:  Frame width in pixels.
        height: Frame height in pixels.
        fps:    Target output frame-rate.
    """

    def __init__(
        self,
        stream_name: str,
        mediamtx_rtsp_url: str = "rtsp://mediamtx:8554",
        width: int = 640,
        height: int = 360,
        fps: int = 15,
    ) -> None:
        self._stream_name = stream_name
        self._annotated_path = f"annotated_{stream_name}"
        self._output_url = f"{mediamtx_rtsp_url}/{self._annotated_path}"
        self._width = width
        self._height = height
        self._fps = fps

        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._started = False

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def output_url(self) -> str:
        return self._output_url

    def push_frame(self, frame: np.ndarray) -> None:
        """
        Write a single BGR frame to the FFmpeg input pipe.

        Silently drops the frame if FFmpeg is not running; the next call
        will restart the process.
        """
        with self._lock:
            self._ensure_process_running()
            if self._process is None or self._process.stdin is None:
                return
            try:
                self._process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                logger.warning("FFmpeg pipe broken for '%s', restarting", self._stream_name)
                self._terminate_process()

    def stop(self) -> None:
        """Cleanly terminate the FFmpeg child process."""
        with self._lock:
            self._terminate_process()
        logger.info("AnnotatedStreamWriter stopped for '%s'", self._stream_name)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _ensure_process_running(self) -> None:
        """Start or restart FFmpeg if it is not running (called under lock)."""
        if self._process is not None and self._process.poll() is None:
            return  # still alive

        if self._process is not None:
            returncode = self._process.poll()
            logger.warning(
                "FFmpeg for '%s' exited with code %s, restarting",
                self._stream_name,
                returncode,
            )

        self._process = self._spawn_ffmpeg()
        self._started = True

    def _spawn_ffmpeg(self) -> subprocess.Popen:
        """Spawn the FFmpeg child process."""
        cmd = [
            _FFMPEG_BINARY,
            "-y",
            # Input: raw BGR frames from stdin
            "-f",
            "rawvideo",
            "-video_size",
            f"{self._width}x{self._height}",
            "-pixel_format",
            "bgr24",
            "-framerate",
            str(self._fps),
            "-i",
            "pipe:0",
            # Encode
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-g",
            "30",
            "-keyint_min",
            "30",
            "-b:v",
            "1500k",
            "-maxrate",
            "2000k",
            "-bufsize",
            "3000k",
            "-pix_fmt",
            "yuv420p",
            # Output: RTSP push to MediaMTX
            "-f",
            "rtsp",
            "-rtsp_transport",
            "tcp",
            self._output_url,
        ]
        logger.info("Starting FFmpeg for annotated stream '%s'  →  %s", self._stream_name, self._output_url)
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,  # silence ffmpeg progress output
            stderr=subprocess.DEVNULL,
        )

    def _terminate_process(self) -> None:
        """Terminate FFmpeg and close the stdin pipe."""
        if self._process is None:
            return
        try:
            if self._process.stdin:
                self._process.stdin.close()
            self._process.terminate()
            self._process.wait(timeout=3)
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass
        finally:
            self._process = None

    # Context-manager support
    def __enter__(self) -> AnnotatedStreamWriter:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
