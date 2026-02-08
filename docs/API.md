# 📚 API Reference

Interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Key Endpoints

### 🤖 ML Models & Detection

- `GET /api/v1/ml-models/` — List available models
- `GET /api/v1/ml-models/active` — Get active model info
- `POST /api/v1/ml-models/switch` — Switch model
- `GET /api/v1/ml-models/hardware` — List hardware accelerators
- `POST /api/v1/ml-models/detect` — Run detection on image
- `POST /api/v1/ml-models/analyze` — VLM image analysis

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
- `GET /api/v1/streams/{stream_id}/rtsp` — Get RTSP stream URL

### 🔍 Detections

- `POST /api/v1/detections/` — Create a new detection
- `GET /api/v1/detections/` — List all detections
- `GET /api/v1/detections/{detection_id}` — Get detection details
- `DELETE /api/v1/detections/{detection_id}` — Delete detection
