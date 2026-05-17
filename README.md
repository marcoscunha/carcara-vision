# Carcara Vision - Hardware-Accelerated ML Inference Platform

<div align="center">

**A modern, extensible video surveillance system with ML-powered detection**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/Status-Under%20Development-orange.svg)]()

</div>

> ⚠️ **Work in Progress**: This project is under active development. Features, APIs, and documentation may change without notice. Hardware acceleration support is implemented but pending validation on real hardware. Use in production at your own risk.

## 🎯 Overview

Carcara Vision is a hardware-accelerated ML inference platform that enables data scientists to maximize GPU/accelerator utilization across multiple video streams. Deploy custom models with a simple SDK and seamless hardware acceleration integration.

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
cd carcara-vision
cp .env.example .env
./launch_docker_gpu.sh
```

For local development without login, keep `AUTH_ENABLED=false` and `VITE_AUTH_ENABLED=false` in `.env`.
Set both to `true` when you want full Keycloak authentication.

This script auto-detects Jetson vs PC+NVIDIA and applies the right Docker Compose override.
If needed, you can still run plain Docker Compose manually.

API docs: http://localhost:8000/docs

## 🤝 Contributing

Everybody is invited and welcome to contribute to Carcara Vision! There's a lot to do — whether you're a developer, a tester with edge hardware, or someone who wants to improve the docs.

### How to contribute

1. **Start a conversation** — Open an [issue](https://github.com/marcoscunha/carcara-vision/issues) to report a bug or suggest a feature, or start a [discussion](https://github.com/marcoscunha/carcara-vision/discussions) for broader ideas.
2. **Pick up or create an issue** — Check existing issues or propose your own. Comment on it so others know you're working on it.
3. **Create a branch** — Branch off `dev` with a descriptive name:
   ```bash
   git checkout dev
   git pull
   git checkout -b feature/my-awesome-feature
   ```
4. **Write code & tests** — Make your changes, ensure tests pass (`uv run pytest`).
5. **Open a Pull Request** — Submit a PR against the `dev` branch. Describe _what_ changed and _why_.

### Other ways to help

- 📝 **Documentation** — Fix typos, clarify guides, add examples
- 🧪 **Hardware testing** — Validate accelerator backends on Jetson, Raspberry Pi, Coral, or Hailo
- 🐛 **Bug reports** — Detailed reports with logs and reproduction steps are incredibly valuable
- 💡 **Feature ideas** — Start a discussion with your use case

## 🚧 Roadmap

- [x] Core API structure (FastAPI backend)
- [x] Database models and migrations
- [x] ML inference layer architecture
- [x] Hardware accelerator abstraction layer
- [x] VLM integration (Ollama, OpenAI)
- [x] Frontend basic structure (React)
- [x] Alarms and ROI management
- [x] Per-stream inference workers with real-time WebSocket events
- [x] Hardware auto-detection (CPU, platform, NVIDIA/Hailo/Coral/etc.)
- [x] Model registry with on-demand download
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
