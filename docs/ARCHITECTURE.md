# 🏗️ Architecture

This document describes the system layout and how data flows through Carcara Vision.

## High-level View

```
High-Level Architecture

External Sources
  +---------------------+
  | IP Cameras / RTSP   |
  | Local V4L2 Cameras  |
  +----------+----------+
             |
             v
Services Layer
  Streaming
    +------------------------+      +--------------------+
    | GStreamer Pipeline     | ---> | MediaMTX RTSP/     |
    | Manager                |      | WebRTC/HLS Server  |
    +-----------+------------+      +---------+----------+
                |                             |
                v                             v
  API                                           Data
    +------------------------+                 +--------------------+
    | FastAPI Backend        | --------------> | PostgreSQL         |
    +-----------+------------+                 +--------------------+
                |
                v
  REST API Endpoints
    +---------------------------------------------+
    | /cameras  /streams  /detections  /alarms     |
    | /roi      /models   /hardware    /discovery  |
    | /inference-runtime  /ws (WebSocket)          |
    +---------------------------------------------+
                |
                v
Processing
  Inference Worker Manager
    +-------------------------------+
    | Per-stream inference workers  |
    +-------------------------------+
                |
                v
  ML Inference Layer
    +-------+   +------+   +------+   +-----------+
    | YOLO  |   | VLM  |   | ONNX |   | TensorRT  |
    +---+---+   +--+---+   +--+---+   +-----+-----+
        \         |          |             /
         \        |          |            /
          v       v          v           v
  Hardware Accelerator Layer
    +-----+  +------+  +--------+  +-----+  +---------+  +--------+
    | CPU |  | CUDA |  | Jetson |  | RPi |  | Coral   |  | Hailo-8|
    +-----+  +------+  +--------+  +-----+  +---------+  +--------+
```

## Component Responsibilities

| Component                      | Responsibility                                                       |
| ------------------------------ | -------------------------------------------------------------------- |
| **FastAPI Backend**            | REST API, DB access, request validation, service orchestration       |
| **GStreamer Pipeline Manager** | Build and control per-stream capture/encode pipelines                |
| **MediaMTX**                   | Distribute streams over RTSP, WebRTC, and HLS                        |
| **Inference Worker Manager**   | Spawn, track, and stop per-stream ML inference workers               |
| **ML Inference Layer**         | Run object detection / VLM models via SDK facade and engine backends |
| **Hardware Accelerator Layer** | Abstract CPU, CUDA, TensorRT, Jetson, Coral, Hailo, and more         |
| **PostgreSQL**                 | Persist cameras, streams, detections, alarms, and ROIs               |

## 📝 Notes

- The API coordinates model selection and inference requests.
- The backend now centralizes runtime/model/provider resolution through the SDK `pipeline(...)` layer (`backend/src/ml/sdk/`) used by services and workers.
- Hardware acceleration is selected by the accelerator backend and runtime config; see `GET /api/v1/hardware/recommended`.
- Streaming uses GStreamer pipelines and MediaMTX for distribution (RTSP/WebRTC/HLS).
- Active streams survive backend restarts: `restore_active_stream_pipelines` re-registers them on startup.
- Real-time detection events are streamed to clients via WebSocket at `/api/v1/ws/streams/{stream_id}/detections`.

## SDK Principles

The inference SDK follows a small set of project-wide principles:

- Prefer one-line task construction via `pipeline(task=..., model=...)`.
- Default to auto-selection (`device="auto"`, `runtime="auto"`, `dtype="auto"`) for safe portability.
- Allow explicit runtime/provider overrides for performance tuning when required.
- Keep output contracts stable and task-level (`DetectionResult`, `VLMResult`) regardless of backend engine.
- Reuse the same resolution path in services and workers to avoid runtime drift.

Decision record:

- `docs/adr/ADR-0001-inference-sdk.md`
