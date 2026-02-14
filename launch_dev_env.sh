#!/bin/bash

# Start the frontend
echo "Starting frontend..."
(cd frontend && npm run dev) &

# Start the backend
echo "Starting backend..."
(
	cd backend
	uv sync
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level debug --reload --reload-dir src
) &

# Start core services (db, mediamtx, gstreamer, keycloak)
echo "Starting core services..."
docker compose up -d db mediamtx gstreamer keycloak

# Wait for Keycloak to be ready
echo "Waiting for Keycloak to be ready..."
for i in {1..30}; do
	if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health | grep -q "200"; then
		echo "Keycloak is ready."
		break
	fi
	sleep 2
done

# Wait for all processes to start
wait
