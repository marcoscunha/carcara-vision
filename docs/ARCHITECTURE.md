# 🏗️ Architecture

This document describes the system layout and how data flows through Carcara NVC.

## High-level View

```
High-Level Architecture

External Sources
  +---------------------+
  | IP Cameras / RTSP   |
  +----------+----------+
             |
             v
Services Layer
  Streaming
    +------------------------+      +--------------------+
    | GStreamer Pipeline     | ---> | MediaMTX RTSP      |
    | Manager                |      | Server             |
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
    +------------------------+
    | /cameras /streams ...  |
    +-----------+------------+
                |
                v
Processing
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

## 📝 Notes

- The API coordinates model selection and inference requests.
- Hardware acceleration is selected by the accelerator backend and runtime config.
- Streaming uses GStreamer pipelines and MediaMTX for distribution.
