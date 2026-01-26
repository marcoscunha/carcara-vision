# Carcara NVC - Network Video Controller with ML-Powered Detection

<div align="center">

**A modern, extensible video surveillance system with cutting-edge ML capabilities**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Under%20Development-orange.svg)]()

</div>

> ⚠️ **Work in Progress**: This project is currently under active development. Features, APIs, and documentation may change without notice. Hardware acceleration support is implemented but pending validation on real hardware. Use in production at your own risk.

## 🎯 Overview

Carcara NVC is a robust backend system for managing IP camera streams with real-time object detection and intelligent video analysis. It's designed to run on various hardware platforms, from powerful servers with NVIDIA GPUs to edge devices like Jetson Nano and Raspberry Pi.

### Key Differentiators

- **🤖 Multi-Model ML Support**: YOLO (v5, v8, v11) for object detection + Vision Language Models (VLMs) for intelligent scene understanding
- **⚡ Hardware Acceleration**: Native support for CUDA, TensorRT, Jetson, Raspberry Pi, Coral TPU, and Hailo accelerators
- **🔌 Modular Architecture**: Pluggable inference engines and accelerator backends
- **📹 Flexible Streaming**: GStreamer pipelines with MediaMTX for RTSP/WebRTC stream handling

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph CarcaraNVC["🎥 Carcara NVC"]
        subgraph API["API Layer"]
            FastAPI["FastAPI Backend"]
            REST["REST API Endpoints"]
        end

        subgraph ML["ML Inference Layer"]
            YOLO["YOLO Engine"]
            VLM["VLM Engine"]
            ONNX["ONNX Engine"]
            TensorRT["TensorRT Engine"]
        end

        subgraph HW["Hardware Accelerator Layer"]
            CPU["CPU"]
            CUDA["CUDA"]
            Jetson["Jetson"]
            RPi["Raspberry Pi"]
            Coral["Coral TPU"]
            Hailo["Hailo-8"]
        end
    end

    subgraph Streaming["Streaming Layer"]
        GStreamer["GStreamer Pipeline Manager"]
        MediaMTX["MediaMTX RTSP Server"]
    end

    subgraph External["External Services"]
        DB[(PostgreSQL)]
        Cameras["IP Cameras / RTSP"]
    end

    FastAPI --> ML
    REST --> ML

    YOLO --> HW
    VLM --> HW
    ONNX --> HW
    TensorRT --> HW

    Cameras --> GStreamer
    GStreamer --> MediaMTX
    MediaMTX --> FastAPI
    FastAPI --> DB

    style CarcaraNVC fill:#181A1F,stroke:#484F57,color:#F9FAFB
    style API fill:#D26A27,stroke:#484F57,color:#F9FAFB
    style ML fill:#F5A45A,stroke:#484F57,color:#181A1F
    style HW fill:#E3D3B0,stroke:#484F57,color:#181A1F
    style Streaming fill:#D26A27,stroke:#484F57,color:#F9FAFB
    style External fill:#484F57,stroke:#181A1F,color:#F9FAFB
```

## ✨ Features

### Object Detection

- **YOLOv5/v8/v11**: State-of-the-art object detection
- **Object Tracking**: ByteTrack integration for multi-object tracking
- **ROI Support**: Define regions of interest for focused detection
- **Batch Processing**: Efficient multi-frame inference

### Vision Language Models (VLMs)

- **Scene Understanding**: Natural language descriptions of camera feeds
- **Custom Queries**: Ask questions about what's happening in the video
- **Supported Backends**:
  - Ollama (LLaVA, Llama 3.2 Vision, BakLLaVA)
  - OpenAI (GPT-4V, GPT-4o)
  - Local HuggingFace models

### Hardware Acceleration

> **Note**: Hardware acceleration backends are implemented but require validation on actual hardware. Status reflects implementation state, not production readiness.

| Platform             | Accelerator      | Implementation | Hardware Tested |
| -------------------- | ---------------- | -------------- | --------------- |
| Desktop/Server       | CUDA (NVIDIA)    | ✅ Implemented | ⏳ Pending      |
| Desktop/Server       | TensorRT         | ✅ Implemented | ⏳ Pending      |
| Jetson Nano          | Jetson GPU       | ✅ Implemented | ⏳ Pending      |
| Jetson Xavier/Orin   | Jetson GPU + DLA | ✅ Implemented | ⏳ Pending      |
| Raspberry Pi 4/5     | CPU (ARM NEON)   | ✅ Implemented | ⏳ Pending      |
| Raspberry Pi + Coral | Edge TPU         | ✅ Implemented | ⏳ Pending      |
| Raspberry Pi + Hailo | Hailo-8/8L       | ✅ Implemented | ⏳ Pending      |
| Intel CPUs           | OpenVINO         | 🚧 Planned     | ⏳ Pending      |

### Video Management

- Camera discovery (RTSP, ONVIF)
- GStreamer pipeline management for video processing
- MediaMTX for RTSP/WebRTC/HLS streaming
- Alarm/event system

## 🚀 Quick Start

### Prerequisites

- Docker Engine
- Docker Compose (included with Docker Desktop or install via `apt install docker-compose-plugin`)
- NVIDIA GPU (optional, for hardware acceleration)
- NVIDIA Container Toolkit (optional, for GPU support)

### Using Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/carcara-nvc.git
cd carcara-nvc

# Copy environment template
cp .env.example .env

# Start services
docker compose up -d

# Access the API
open http://localhost:8000/docs
```

### Development Setup

```bash
# Backend setup
cd backend
uv sync

# Install with GPU support
uv sync --extra cuda

# Install with VLM support
uv sync --extra vlm

# Install everything
uv sync --extra full

# Run development server
uv run uvicorn src.main:app --reload

# Frontend setup
cd ../frontend
npm install
npm run dev
```

## ⚙️ Configuration

### Environment Variables

```bash
# Database
POSTGRES_SERVER=db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=carcara_nvc

# ML Configuration
DEFAULT_MODEL=yolov8n.pt
CONFIDENCE_THRESHOLD=0.5
USE_GPU=true
ACCELERATOR=auto  # auto, cpu, cuda, tensorrt, jetson, rpi

# TensorRT (for NVIDIA GPUs)
TENSORRT_ENABLED=true
TENSORRT_FP16=true

# Jetson Settings
JETSON_POWER_MODE=0  # 0 = max performance
JETSON_USE_DLA=false  # Enable DLA cores on Xavier/Orin

# Raspberry Pi Settings
RPI_USE_CORAL_TPU=false
RPI_USE_HAILO=false

# VLM Configuration
VLM_ENABLED=true
VLM_BACKEND=ollama  # ollama, openai, local
VLM_MODEL=llava
OLLAMA_HOST=http://localhost:11434

# For OpenAI VLM
# OPENAI_API_KEY=your-api-key
# VLM_BACKEND=openai
# VLM_MODEL=gpt-4o
```

## 📚 API Documentation

Once running, access the interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key API Endpoints

#### ML Models & Detection

- `GET /api/v1/ml-models/` - List available models
- `GET /api/v1/ml-models/active` - Get active model info
- `POST /api/v1/ml-models/switch` - Switch model
- `GET /api/v1/ml-models/hardware` - List hardware accelerators
- `POST /api/v1/ml-models/detect` - Run detection on image
- `POST /api/v1/ml-models/analyze` - VLM image analysis

#### Cameras

- `POST /api/v1/cameras/` - Create a new camera
- `GET /api/v1/cameras/` - List all cameras
- `GET /api/v1/cameras/{camera_id}` - Get camera details
- `PUT /api/v1/cameras/{camera_id}` - Update camera
- `DELETE /api/v1/cameras/{camera_id}` - Delete camera

#### Streams

- `POST /api/v1/streams/` - Create a new stream
- `GET /api/v1/streams/` - List all streams
- `GET /api/v1/streams/{stream_id}` - Get stream details
- `GET /api/v1/streams/{stream_id}/rtsp` - Get RTSP stream URL

### Detections

- `POST /api/v1/detections/` - Create a new detection
- `GET /api/v1/detections/` - List all detections
- `GET /api/v1/detections/{detection_id}` - Get detection details
- `DELETE /api/v1/detections/{detection_id}` - Delete detection

## 🔧 Platform-Specific Setup

### NVIDIA Jetson

```bash
# JetPack should be pre-installed with CUDA and TensorRT

# Set power mode for inference
sudo nvpmodel -m 0  # Max performance
sudo jetson_clocks

# Install with Jetson extras
poetry install

# Set environment
export ACCELERATOR=jetson
export TENSORRT_ENABLED=true
```

### Raspberry Pi with Coral TPU

```bash
# Install Edge TPU runtime
echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | sudo tee /etc/apt/sources.list.d/coral-edgetpu.list
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
sudo apt update
sudo apt install libedgetpu1-std python3-pycoral

# Install with edge extras
poetry install -E edge

# Set environment
export ACCELERATOR=rpi
export RPI_USE_CORAL_TPU=true
```

### Raspberry Pi with Hailo-8

```bash
# Install Hailo runtime (from Hailo website)
# Follow: https://hailo.ai/developer-zone/

# Set environment
export ACCELERATOR=rpi
export RPI_USE_HAILO=true
```

## 🤖 Using VLMs

### With Ollama (Local)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a vision model
ollama pull llava

# Configure Carcara
export VLM_ENABLED=true
export VLM_BACKEND=ollama
export VLM_MODEL=llava
```

### With OpenAI

```bash
export VLM_ENABLED=true
export VLM_BACKEND=openai
export VLM_MODEL=gpt-4o
export OPENAI_API_KEY=your-api-key
```

### Example API Usage

```python
import requests
import base64

# Load image
with open("image.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

# Analyze with VLM
response = requests.post(
    "http://localhost:8000/api/v1/ml-models/analyze",
    json={
        "image_base64": image_b64,
        "prompt": "Describe what's happening in this security camera feed."
    }
)

print(response.json()["analysis"])
```

## 📁 Project Structure

```
carcara-nvc/
├── backend/
│   ├── src/
│   │   ├── api/endpoints/       # FastAPI endpoints
│   │   ├── core/                # Configuration
│   │   ├── db/                  # Database models
│   │   ├── ml/                  # ML infrastructure
│   │   │   ├── accelerators/    # Hardware backends
│   │   │   ├── engines/         # Inference engines
│   │   │   ├── base.py          # Base classes
│   │   │   ├── factory.py       # Engine factory
│   │   │   └── registry.py      # Model registry
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   └── services/            # Business logic
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/                    # React frontend
├── gstreamer/                   # GStreamer pipeline manager
├── mediamtx/                    # MediaMTX RTSP server config
├── docker-compose.yml
└── README.md
```

## 🧪 Testing

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/src/services/test_detection_service.py -v
```

## Docker Commands

### Start Services

```bash
docker compose up -d
```

### Stop Services

```bash
docker compose down
```

### View Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs backend
docker compose logs frontend
docker compose logs db
```

### Rebuild Services

```bash
# All services
docker compose build

# Specific service
docker compose build backend
docker compose build frontend
```

### Restart Services

```bash
# All services
docker compose restart

# Specific service
docker compose restart backend
docker compose restart frontend
```

## 🚧 Development Roadmap

- [x] Core API structure (FastAPI backend)
- [x] Database models and migrations
- [x] ML inference layer architecture
- [x] Hardware accelerator abstraction layer
- [x] VLM integration (Ollama, OpenAI)
- [x] Frontend basic structure (React)
- [ ] Hardware acceleration validation on real devices
- [ ] End-to-end testing on Jetson devices
- [ ] End-to-end testing on Raspberry Pi
- [ ] Coral TPU integration testing
- [ ] Hailo-8 integration testing
- [ ] Production deployment guide
- [ ] Performance benchmarks

## 🤝 Contributing

Contributions are welcome! As this project is under active development, please open an issue first to discuss proposed changes.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- [Ultralytics](https://ultralytics.com/) for YOLO models
- [GStreamer](https://gstreamer.freedesktop.org/) for video pipeline processing
- [MediaMTX](https://github.com/bluenviron/mediamtx) for RTSP/WebRTC streaming
- [Ollama](https://ollama.com/) for local VLM inference
- The FastAPI and Pydantic teams

---

<div align="center">
Made with ❤️ for the video surveillance and ML community
</div>
