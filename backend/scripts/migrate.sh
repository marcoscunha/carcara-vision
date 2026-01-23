#!/bin/bash

# Wait for the database to be ready
echo "Waiting for database to be ready..."
DB_HOST="${POSTGRES_SERVER:-${DB_HOST:-localhost}}"
while ! nc -z $DB_HOST 5432; do
  sleep 0.1
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
alembic upgrade head

echo "Migration completed!"