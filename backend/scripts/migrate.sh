#!/bin/bash

# Activate the virtual environment
source /app/.venv/bin/activate

# Wait for the database to be ready
echo "Waiting for database to be ready..."
DB_HOST="${POSTGRES_SERVER:-${DB_HOST:-localhost}}"
DB_PORT="${POSTGRES_PORT:-5432}"
MAX_WAIT_SECONDS="${MIGRATION_DB_WAIT_TIMEOUT:-120}"
START_TS=$(date +%s)

while ! nc -z "$DB_HOST" "$DB_PORT"; do
  NOW_TS=$(date +%s)
  ELAPSED=$((NOW_TS - START_TS))
  if [ "$ELAPSED" -ge "$MAX_WAIT_SECONDS" ]; then
    echo "Database not reachable at ${DB_HOST}:${DB_PORT} after ${MAX_WAIT_SECONDS}s"
    exit 1
  fi
  sleep 1
done
echo "Database is ready!"

# Create versions directory if it doesn't exist
# mkdir -p migrations/versions

# Initialize migrations if not already initialized
# if [ ! -f "migrations/versions/initial.py" ]; then
#     echo "Initializing migrations..."
#     alembic revision --autogenerate -m "initial"
# fi

# # Generate new migration
# echo "Generating migration..."
# alembic revision --autogenerate -m "add_camera_type_and_device_id"

# Run migration
echo "Running migration..."
/app/.venv/bin/alembic upgrade head

echo "Migration completed!"
