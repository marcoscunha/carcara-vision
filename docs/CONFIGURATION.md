# ⚙️ Configuration

This project is configured via environment variables. Use `.env` for local development.

## 🔧 Core Settings

```bash
POSTGRES_SERVER=db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=carcara_nvc

DEFAULT_MODEL=yolov8n.pt
CONFIDENCE_THRESHOLD=0.5
USE_GPU=true
ACCELERATOR=auto  # auto, cpu, cuda, tensorrt, jetson, rpi
```

## 🎮 NVIDIA / TensorRT

```bash
TENSORRT_ENABLED=true
TENSORRT_FP16=true
```

## 🚀 Jetson

```bash
JETSON_POWER_MODE=0  # 0 = max performance
JETSON_USE_DLA=false
```

## 🍓 Raspberry Pi

```bash
RPI_USE_CORAL_TPU=false
RPI_USE_HAILO=false
```

## 🤖 VLM

```bash
VLM_ENABLED=true
VLM_BACKEND=ollama  # ollama, openai, local
VLM_MODEL=llava
OLLAMA_HOST=http://localhost:11434

# OpenAI
# OPENAI_API_KEY=your-api-key
# VLM_BACKEND=openai
# VLM_MODEL=gpt-4o
```
