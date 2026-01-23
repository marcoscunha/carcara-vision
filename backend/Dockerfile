# syntax=docker/dockerfile:1.4
# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies needed for building
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    dos2unix

# Copy requirements first for better caching
COPY pyproject.toml poetry.lock* ./

# Install Python dependencies with cache mounts
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cache/pypoetry \
    pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry config installer.max-workers 10 && \
    poetry install --only main --no-root --no-interaction

# Copy application code
COPY . .

# Fix line endings and make scripts executable in one layer
RUN dos2unix scripts/migrate.sh scripts/start.sh && \
    chmod +x scripts/migrate.sh scripts/start.sh

# Final stage
FROM python:3.11-slim

WORKDIR /app

# Install only the necessary runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    netcat-traditional \
    v4l-utils

# Copy Python packages from builder (already cleaned)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only necessary application files
COPY --from=builder /app/src /app/src
COPY --from=builder /app/scripts /app/scripts
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations

# Add application directory to PYTHONPATH
ENV PYTHONPATH=/app

# Run migrations and start the application
CMD ["/bin/bash", "./scripts/start.sh"]
