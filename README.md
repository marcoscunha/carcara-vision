# Carcara NVC - Network Video Controller with ML-Powered Detection

<div align="center">

**A modern, extensible video surveillance system with ML-powered detection**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Under%20Development-orange.svg)]()

</div>

> ⚠️ **Work in Progress**: This project is under active development. Features, APIs, and documentation may change without notice. Hardware acceleration support is implemented but pending validation on real hardware. Use in production at your own risk.

## 🎯 Overview

Carcara NVC manages IP camera streams with real-time detection and intelligent video analysis. It runs on powerful servers with NVIDIA GPUs down to edge devices like Jetson Nano and Raspberry Pi.

### ✨ Highlights

- 🤖 **Multi-model ML** — YOLO v5/v8/v11 detection + Vision Language Models for scene understanding
- ⚡ **Hardware acceleration** — CUDA, TensorRT, Jetson, Coral TPU, Hailo & more
- 🔌 **Modular architecture** — Pluggable inference engines and accelerator backends
- 📹 **Flexible streaming** — GStreamer pipelines with MediaMTX (RTSP/WebRTC/HLS)
- 📷 **Smart camera discovery** — Persistent V4L2 device paths that survive reboots

## 📖 Documentation

| Topic                     | Link                                                   |
| ------------------------- | ------------------------------------------------------ |
| 🚀 Quick Start            | [docs/QUICK_START.md](docs/QUICK_START.md)             |
| ⚙️ Configuration          | [docs/CONFIGURATION.md](docs/CONFIGURATION.md)         |
| 📚 API Reference          | [docs/API.md](docs/API.md)                             |
| 🏗️ Architecture           | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)           |
| ✨ Features               | [docs/FEATURES.md](docs/FEATURES.md)                   |
| 🔧 Platform Setup         | [docs/PLATFORM_SETUP.md](docs/PLATFORM_SETUP.md)       |
| 🤖 Vision Language Models | [docs/VLM.md](docs/VLM.md)                             |
| 🐳 Docker                 | [docs/DOCKER.md](docs/DOCKER.md)                       |
| 🧪 Testing                | [docs/TESTING.md](docs/TESTING.md)                     |
| 🚧 Roadmap                | [docs/ROADMAP.md](docs/ROADMAP.md)                     |
| 📷 Local Camera Scan      | [docs/LOCAL_CAMERA_SCAN.md](docs/LOCAL_CAMERA_SCAN.md) |
| 🎨 Design System          | [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md)         |

## 🚀 Quick start

```bash

cd carcara-nvc
cp .env.example .env
docker compose up -d
```

API docs: http://localhost:8000/docs

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss proposed changes.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 🚧 Roadmap

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

## 📄 License

MIT License — see the LICENSE file for details.

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
        Coral["Coral TPU"]
