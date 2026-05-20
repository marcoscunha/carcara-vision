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

The writer keeps only the latest frame in memory and sends frames to FFmpeg
from a dedicated background thread. If encoding or RTSP publishing falls
behind, older frames are dropped instead of blocking the inference thread.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
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
        encoder_mode: Hardware encoder selection — one of
                      ``auto``, ``nvenc``, ``jetson``, ``v4l2``, ``x264``.
                      ``auto`` and ``nvenc`` map to ``h264_nvenc``;
                      ``jetson`` maps to ``h264_omx``;
                      ``v4l2`` maps to ``h264_v4l2m2m``;
                      anything else falls back to ``libx264``.
    """

    # Mapping from resolved encoder mode to (ffmpeg_codec, extra_args).
    # All profiles forced to Constrained Baseline + no B-frames for maximum
    # WebRTC/HLS compatibility. SPS/PPS are repeated before every keyframe via
    # the ``dump_extra`` bitstream filter (added in ``_build_encoder_args``)
    # so mid-stream WebRTC subscribers can start decoding within one GOP.
    _ENCODER_MAP: dict[str, tuple[str, list[str]]] = {
        "nvenc": (
            "h264_nvenc",
            [
                "-preset",
                "p4",
                "-tune",
                "ll",
                "-profile:v",
                "baseline",
                "-bf",
                "0",
                "-forced-idr",
                "1",
                "-b:v",
                "1500k",
            ],
        ),
        "jetson": (
            "h264_omx",
            [
                "-profile:v",
                "baseline",
                "-bf",
                "0",
                "-b:v",
                "1500k",
            ],
        ),
        "v4l2": (
            "h264_v4l2m2m",
            [
                "-profile:v",
                "baseline",
                "-b:v",
                "1500k",
            ],
        ),
    }

    def __init__(
        self,
        stream_name: str,
        mediamtx_rtsp_url: str = "rtsp://mediamtx:8554",
        width: int = 640,
        height: int = 360,
        fps: int = 15,
        encoder_mode: str = "x264",
    ) -> None:
        self._stream_name = stream_name
        self._annotated_path = f"annotated_{stream_name}"
        self._output_url = f"{mediamtx_rtsp_url}/{self._annotated_path}"
        self._width = width
        self._height = height
        self._fps = fps
        self._encoder_mode = encoder_mode

        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._process_lock = threading.Lock()
        self._frame_ready = threading.Condition(self._lock)
        self._latest_frame: np.ndarray | None = None
        self._worker_stop = threading.Event()
        self._worker_thread: threading.Thread | None = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def output_url(self) -> str:
        return self._output_url

    def push_frame(self, frame: np.ndarray) -> None:
        """
        Publish the latest BGR frame without blocking the caller.

        If the output path falls behind, older queued frames are replaced by
        the newest frame so the stream stays near real time.
        """
        with self._lock:
            self._ensure_worker_running()
            self._latest_frame = frame
            self._frame_ready.notify()

    def stop(self) -> None:
        """Cleanly terminate the FFmpeg child process."""
        with self._lock:
            self._worker_stop.set()
            self._frame_ready.notify_all()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)

        with self._lock:
            self._latest_frame = None
            self._worker_thread = None

        with self._process_lock:
            self._terminate_process()
        logger.info("AnnotatedStreamWriter stopped for '%s'", self._stream_name)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _ensure_worker_running(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        self._worker_stop.clear()
        self._worker_thread = threading.Thread(
            target=self._writer_loop,
            name=f"annotated-stream-writer-{self._stream_name}",
            daemon=True,
        )
        self._worker_thread.start()

    def _ensure_process_running(self) -> None:
        """Start or restart FFmpeg if it is not running (called under process lock)."""
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

    def _writer_loop(self) -> None:
        frame_interval = 1.0 / max(self._fps, 1)
        next_frame_at = time.monotonic()

        while not self._worker_stop.is_set():
            frame = self._wait_for_frame(timeout=frame_interval)
            if frame is None:
                continue

            now = time.monotonic()
            if now < next_frame_at:
                if self._worker_stop.wait(timeout=next_frame_at - now):
                    break

            if not self._write_frame(frame):
                self._worker_stop.wait(timeout=0.1)

            next_frame_at = max(next_frame_at + frame_interval, time.monotonic())

    def _wait_for_frame(self, timeout: float) -> np.ndarray | None:
        with self._lock:
            if self._latest_frame is None and not self._worker_stop.is_set():
                self._frame_ready.wait(timeout=timeout)
            return self._latest_frame

    def _write_frame(self, frame: np.ndarray) -> bool:
        with self._process_lock:
            self._ensure_process_running()
            if self._process is None or self._process.stdin is None:
                return False

            try:
                self._process.stdin.write(frame.tobytes())
                return True
            except BrokenPipeError:
                logger.warning("FFmpeg pipe broken for '%s', restarting", self._stream_name)
                self._terminate_process()
                return False
            except Exception as exc:
                logger.warning("FFmpeg write failed for '%s': %s", self._stream_name, exc)
                self._terminate_process()
                return False

    def _build_encoder_args(self) -> list[str]:
        """Return FFmpeg codec/encoder arguments for the configured encoder_mode.

        All paths produce Constrained-Baseline H.264 with a short GOP and an
        in-band SPS/PPS repetition (``dump_extra=freq=keyframe``) so that any
        WebRTC/HLS client that joins mid-stream can start decoding within one
        GOP rather than waiting indefinitely for parameter sets.
        """
        # 1 keyframe per second keeps new subscribers' time-to-first-frame low.
        gop = max(self._fps, 1)
        common_tail = [
            "-g",
            str(gop),
            "-keyint_min",
            str(gop),
            "-pix_fmt",
            "yuv420p",
            # Repeat SPS/PPS before every IDR so RTP/WebRTC clients can
            # initialise their decoder without seeing the very first packet.
            "-bsf:v",
            "dump_extra=freq=keyframe",
        ]

        mode = self._encoder_mode
        if mode in self._ENCODER_MAP:
            codec, extra = self._ENCODER_MAP[mode]
            return ["-c:v", codec, *extra, *common_tail]

        # Default: software libx264 (auto, x264, or any unrecognised value)
        return [
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-profile:v",
            "baseline",
            "-bf",
            "0",
            "-b:v",
            "1500k",
            "-maxrate",
            "2000k",
            "-bufsize",
            "3000k",
            *common_tail,
        ]

    def _spawn_ffmpeg(self) -> subprocess.Popen:
        """Spawn the FFmpeg child process."""
        encoder_args = self._build_encoder_args()
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
            # Encode (hardware-aware)
            *encoder_args,
            # Output: RTSP push to MediaMTX
            "-f",
            "rtsp",
            "-rtsp_transport",
            "tcp",
            self._output_url,
        ]
        logger.info(
            "Starting FFmpeg for annotated stream '%s'  →  %s | cmd: %s",
            self._stream_name,
            self._output_url,
            " ".join(cmd),
        )
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,  # silence ffmpeg progress output
            stderr=subprocess.PIPE,
        )
        # Drain stderr in a background thread so the pipe never blocks and
        # encoder errors actually surface in the application log.
        threading.Thread(
            target=self._drain_ffmpeg_stderr,
            args=(process,),
            name=f"annotated-stream-ffmpeg-stderr-{self._stream_name}",
            daemon=True,
        ).start()
        return process

    def _drain_ffmpeg_stderr(self, process: subprocess.Popen) -> None:
        """Forward FFmpeg stderr line-by-line to the application logger."""
        stderr = process.stderr
        if stderr is None:
            return
        try:
            for raw in iter(stderr.readline, b""):
                if not raw:
                    break
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                lowered = line.lower()
                if "error" in lowered or "fatal" in lowered or "failed" in lowered:
                    logger.warning("[ffmpeg %s] %s", self._stream_name, line)
                else:
                    logger.debug("[ffmpeg %s] %s", self._stream_name, line)
        except Exception:
            pass

    def _terminate_process(self) -> None:
        """Terminate FFmpeg and close the stdin pipe (called under process lock)."""
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
