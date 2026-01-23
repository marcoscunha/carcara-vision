# syntax=docker/dockerfile:1.4
FROM python:3.11-slim

# Install GStreamer and dependencies with cache mount
# Note: V4L2 support is included in gstreamer1.0-plugins-good
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    # GStreamer core
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    # RTSP server and client support
    gstreamer1.0-rtsp \
    # Hardware acceleration (optional - may not be available on all systems)
    gstreamer1.0-gl \
    # V4L2 utilities
    v4l-utils \
    # GObject introspection data for GStreamer
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-rtsp-server-1.0 \
    # Build dependencies for PyGObject (girepository-2.0 in Debian Trixie)
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libcairo2-dev \
    libgirepository-2.0-dev \
    gobject-introspection \
    pkg-config \
    gcc

# Install Python dependencies with pip cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install \
    pycairo \
    PyGObject \
    httpx

WORKDIR /app

# Copy service files
COPY . /app/

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import gi; gi.require_version('Gst', '1.0'); from gi.repository import Gst; Gst.init(None); print('OK')" || exit 1

CMD ["python", "pipeline_manager.py"]
