# syntax=docker/dockerfile:1.4
# Build stage
FROM python:3.13-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy requirements first for better caching
COPY pyproject.toml uv.lock* ./

# Create virtual environment and install Python dependencies
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv /app/.venv && \
    uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Final stage
FROM python:3.13-slim

WORKDIR /app

# Install only the necessary runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    netcat-traditional \
    udev \
    v4l-utils \
    pciutils \
    usbutils

# Install uv for runtime
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy only necessary application files
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/migrations /app/migrations

# Add virtual environment to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV VIRTUAL_ENV=/app/.venv

# Expose port
EXPOSE 8000

# Run migrations and start the application
CMD sh -c "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level debug --reload --reload-dir src"
