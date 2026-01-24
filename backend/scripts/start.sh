#!/bin/bash

# Activate the virtual environment
source /app/.venv/bin/activate

# Run migrations
if [ -f "./scripts/migrate.sh" ]; then
    echo "Running migrations"
    echo "--------------------------------"
    # check permissions
    chmod +x ./scripts/migrate.sh
    # run migrations
    ./scripts/migrate.sh
    echo "--------------------------------"
else
    echo "--------------------------------"
    echo "Warning: migrate.sh not found, skipping migrations"
    echo "--------------------------------"
fi

# Start the application
echo "Starting application"
echo "--------------------------------"
exec /app/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level debug --reload --reload-dir src
echo "--------------------------------"