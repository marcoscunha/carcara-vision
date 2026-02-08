# ✨ Features

## 🎯 Object Detection

- **YOLOv5/v8/v11** — State-of-the-art object detection
- **Object Tracking** — ByteTrack integration for multi-object tracking
- **ROI Support** — Define regions of interest for focused detection
- **Batch Processing** — Efficient multi-frame inference

## 🤖 Vision Language Models (VLM)

- **Scene Understanding** — Natural language descriptions of camera feeds
- **Custom Queries** — Ask questions about what's happening in the video
- **Supported Backends**:
  - Ollama (LLaVA, Llama 3.2 Vision, BakLLaVA)
  - OpenAI (GPT-4V, GPT-4o)
  - Local HuggingFace models

## ⚡ Hardware Acceleration

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

## 📹 Video Management

- **Local Camera Discovery** — Automatic V4L2 device scanning with persistent `/dev/v4l/by-id/` symlinks that survive reboots 🔒
- **Network Camera Discovery** — RTSP and ONVIF camera support
- **GStreamer Pipelines** — Native GStreamer pipeline management for video processing
- **MediaMTX Streaming** — RTSP/WebRTC/HLS streaming via MediaMTX
- **Alarm/Event System** — Configurable detection-based alerts 🔔
