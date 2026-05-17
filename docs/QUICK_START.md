# 🚀 Quick Start

## Prerequisites

- 🐳 Docker Engine
- 🐳 Docker Compose (docker-compose-plugin)
- 🎮 NVIDIA GPU _(optional, for hardware acceleration)_
- 🎮 NVIDIA Container Toolkit _(optional, for GPU support)_

## Run with Docker (recommended)

```bash
git clone https://github.com/yourusername/carcara-vision.git
cd carcara-vision
cp .env.example .env
docker compose up -d
```

API docs are available at http://localhost:8000/docs 🎉

## 🛠️ Development Setup

```bash
cd backend
uv sync

# Optional extras
uv sync --extra cuda
uv sync --extra vlm
uv sync --extra full

uv run uvicorn src.main:app --reload

cd ../frontend
npm install
npm run dev
```
