#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_COMPOSE="$SCRIPT_DIR/docker-compose.yml"
JETSON_COMPOSE="$SCRIPT_DIR/docker-compose.jetson.yml"
PC_COMPOSE="$SCRIPT_DIR/docker-compose.nvidia-pc.yml"

is_jetson() {
  [[ -f /etc/nv_tegra_release ]] && return 0

  if [[ -r /proc/device-tree/model ]]; then
    local model
    model="$(tr -d '\0' < /proc/device-tree/model | tr '[:upper:]' '[:lower:]')"
    [[ "$model" == *"jetson"* ]] && return 0
  fi

  return 1
}

has_nvidia_desktop_gpu() {
  command -v nvidia-smi >/dev/null 2>&1 && return 0
  [[ -r /proc/driver/nvidia/version ]] && return 0
  return 1
}

compose_files=("-f" "$BASE_COMPOSE")
platform="none"

if is_jetson; then
  platform="jetson"
  compose_files+=("-f" "$JETSON_COMPOSE")
elif has_nvidia_desktop_gpu; then
  platform="nvidia-pc"
  compose_files+=("-f" "$PC_COMPOSE")
fi

if [[ $# -eq 0 ]]; then
  set -- up -d --build
fi

echo "Detected platform: $platform"
if [[ "$platform" == "jetson" ]]; then
  echo "Using override: docker-compose.jetson.yml"
elif [[ "$platform" == "nvidia-pc" ]]; then
  echo "Using override: docker-compose.nvidia-pc.yml"
else
  echo "No NVIDIA platform detected. Using base docker-compose.yml only."
fi

echo "Running: docker compose ${compose_files[*]} $*"
exec docker compose "${compose_files[@]}" "$@"
