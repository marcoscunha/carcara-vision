#!/bin/bash

# Start the frontend
echo "Starting frontend..."
(cd frontend && npm run dev) &

# Start the backend
echo "Starting backend..."
(cd backend && uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level debug --reload --reload-dir src) &

# Start the database
echo "Starting database..."
docker compose up -d db

# Wait for all processes to start
wait
