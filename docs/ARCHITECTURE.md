# 🏗️ Architecture

This document describes the system layout and how data flows through Carcara NVC.

## High-level View

```mermaid
flowchart TB
    subgraph External["📡 External Sources"]
        direction LR
        Cameras["IP Cameras / RTSP"]
        DB[(PostgreSQL)]
    end

    subgraph Services["🌐 Services Layer"]
        direction LR
        subgraph Streaming["Streaming"]
            direction LR
            GStreamer["GStreamer Pipeline Manager"]
            MediaMTX["MediaMTX RTSP Server"]
        end

        subgraph API["API"]
            direction LR
            FastAPI["FastAPI Backend"]
            REST["REST API Endpoints"]
        end
    end

    subgraph ML["🤖 ML Inference Layer"]
        direction LR
        YOLO["YOLO Engine"]
        VLM["VLM Engine"]
        ONNX["ONNX Engine"]
        TensorRT["TensorRT Engine"]
    end

    subgraph HW["⚡ Hardware Accelerator Layer"]
        direction LR
        CPU["CPU"]
        CUDA["CUDA"]
        Jetson["Jetson"]
        RPi["Raspberry Pi"]
        Coral["Coral TPU"]
        Hailo["Hailo-8"]
    end

    Cameras --> GStreamer
    GStreamer --> MediaMTX
    MediaMTX --> FastAPI
    FastAPI --> DB

    FastAPI --> ML
    REST --> ML

    YOLO --> HW
    VLM --> HW
    ONNX --> HW
    TensorRT --> HW
```

## 📝 Notes

- The API coordinates model selection and inference requests.
- Hardware acceleration is selected by the accelerator backend and runtime config.
- Streaming uses GStreamer pipelines and MediaMTX for distribution.
