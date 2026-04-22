# 📚 API Reference

> **Prerequisites**: Make sure the services are running before accessing the API docs. Follow the [🚀 Quick Start](QUICK_START.md) guide to get everything up.

Once the backend is running, interactive documentation is available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Key Endpoints

### 📦 Models

- `GET /api/v1/models/` — List available models (filter by `?task_type=detect|pose|segment`)
- `GET /api/v1/models/{name}` — Get metadata for a specific model
- `POST /api/v1/models/{name}/ensure` — Trigger on-demand model download (202 Accepted; poll `is_available`)

### ⚙️ Inference Runtime

- `GET /api/v1/inference-runtime/` — Get active inference runtime config (model, accelerator, task type)
- `PUT /api/v1/inference-runtime/` — Update inference runtime config

### 📷 Cameras

- `GET /api/v1/cameras/scan` — Scan for local V4L2 cameras (returns persistent `device_path`)
- `POST /api/v1/cameras/` — Create a new camera
- `GET /api/v1/cameras/` — List all cameras
- `GET /api/v1/cameras/{camera_id}` — Get camera details
- `GET /api/v1/cameras/{camera_id}/status` — Get camera status
- `PUT /api/v1/cameras/{camera_id}` — Update camera
- `DELETE /api/v1/cameras/{camera_id}` — Delete camera and associated streams/detections

### 📹 Streams

- `POST /api/v1/streams/` — Create a new stream
- `GET /api/v1/streams/` — List all streams
- `GET /api/v1/streams/{stream_id}` — Get stream details
- `GET /api/v1/streams/{stream_id}/urls` — Get all stream URLs (RTSP, WebRTC, HLS, etc.)
- `PUT /api/v1/streams/{stream_id}` — Update stream settings (resolution, codec, detection config)
- `POST /api/v1/streams/{stream_id}/restart` — Restart stream pipeline
- `DELETE /api/v1/streams/{stream_id}` — Delete stream
- `GET /api/v1/streams/{stream_id}/detections` — Run on-demand detection on the stream's current frame
- `GET /api/v1/streams/{stream_id}/ml-info` — Get ML hardware and baseline inference performance info
- `GET /api/v1/streams/{stream_id}/metrics` — Get per-stream inference metrics
- `GET /api/v1/streams/metrics/realtime` — Get realtime metrics across all active streams
- `GET /api/v1/streams/health/gstreamer` — GStreamer pipeline health check

Per-stream SDK inference overrides can be set in `stream_metadata` (via create/update stream payload), including:

- `detection_runtime`: `auto|yolo|onnxruntime|tensorrt|openai_vlm|ollama_vlm|local_vlm`
- `detection_dtype`: `auto|fp32|fp16|int8`
- `detection_providers`: ordered ONNX Runtime provider chain

### 🔍 Detections

- `POST /api/v1/detections/` — Create a new detection
- `GET /api/v1/detections/` — List all detections
- `GET /api/v1/detections/{detection_id}` — Get detection details
- `DELETE /api/v1/detections/{detection_id}` — Delete detection

### 🔔 Alarms

- `GET /api/v1/alarms/` — List all alarms
- `GET /api/v1/alarms/{alarm_id}` — Get alarm details
- `POST /api/v1/alarms/` — Create a new alarm
- `PUT /api/v1/alarms/{alarm_id}` — Update alarm
- `DELETE /api/v1/alarms/{alarm_id}` — Delete alarm

### 🗺️ Regions of Interest (ROI)

- `GET /api/v1/roi/` — List all ROIs
- `GET /api/v1/roi/{roi_id}` — Get ROI details
- `POST /api/v1/roi/` — Create a new ROI
- `PUT /api/v1/roi/{roi_id}` — Update ROI
- `DELETE /api/v1/roi/{roi_id}` — Delete ROI

### 🔧 Hardware

- `GET /api/v1/hardware/detect` — Full hardware detection (CPU, platform, accelerators); cached 5 min, use `?refresh=true` to force
- `GET /api/v1/hardware/cpu` — CPU info (architecture, cores, features)
- `GET /api/v1/hardware/platform` — Platform/board info (vendor, OS)
- `GET /api/v1/hardware/accelerators` — List detected AI accelerators (NVIDIA, Hailo, Coral, etc.)
- `GET /api/v1/hardware/recommended` — Get recommended accelerator for this system

### 📡 Discovery

- `GET /api/v1/discovery/cameras` — Discover cameras on the local network via ONVIF/mDNS

### 🔌 WebSocket

- `WS /api/v1/ws/streams/{stream_id}/detections` — Real-time detection events for a stream
- `WS /api/v1/ws/workers/stats` — Real-time inference worker statistics
