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
