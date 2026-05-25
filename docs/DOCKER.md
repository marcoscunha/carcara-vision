# 🐳 Docker Commands

## ▶️ Start Services

```bash
docker compose up -d
```

### Auto-detect NVIDIA platform (Jetson or PC)

```bash
./launch_docker_gpu.sh
```

By default it runs `up -d --build` and automatically picks:

- `docker-compose.jetson.yml` on Jetson
- `docker-compose.nvidia-pc.yml` on PC with NVIDIA GPU
- Base `docker-compose.yml` when no NVIDIA platform is detected

You can pass any compose command through it, for example:

```bash
./launch_docker_gpu.sh logs -f backend
./launch_docker_gpu.sh down
```

### NVIDIA Jetson (uses NVIDIA runtime)

```bash
docker compose -f docker-compose.yml -f docker-compose.jetson.yml up -d --build
```

### PC with NVIDIA GPU (uses GPU device reservations)

```bash
docker compose -f docker-compose.yml -f docker-compose.nvidia-pc.yml up -d --build
```

## ⏹️ Stop Services

```bash
docker compose down
```

## 📋 View Logs

```bash
docker compose logs

docker compose logs backend
docker compose logs frontend
docker compose logs db
```

## 🔨 Rebuild Services

```bash
docker compose build

docker compose build backend
docker compose build frontend
```

## 🔄 Restart Services

```bash
docker compose restart

docker compose restart backend
docker compose restart frontend
```

## 💾 Persistent Models Across Rebuilds

The backend now uses project bind mounts for models and model registry cache:

- `./models` -> `/app/models`
- `./.model_cache` -> `/app/.model_cache`

Optional override in `.env`:

- `MODELS_VOLUME_DIR=./models`
- `MODEL_CACHE_VOLUME_DIR=./.model_cache`

This keeps downloaded models available after `docker compose down`, rebuilds, and container recreation.

Manual local copy example:

```bash
cp /path/to/my-model.pt ./models/
docker compose restart backend
```

After restart, the model file remains in the project folder and is reused by the backend.
