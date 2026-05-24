"""
Model management endpoints.

Exposes the ModelRegistry over HTTP so the frontend can:
  - list all available models (optionally filtered by task type)
  - retrieve a single model's metadata
  - trigger on-demand download/availability for a specific model
"""

from typing import Any

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from ...services.models import ensure_model_available
from ...services.models import get_available_models
from ...services.models import get_model_by_name
from ...services.models import register_yolo_model

router = APIRouter()


class RegisterModelRequest(BaseModel):
    name: str = Field(min_length=1, description="Model logical name, e.g. yolov8-custom")
    task_type: str = Field(default="detect", description="Task type: detect, pose, segment")
    description: str = Field(default="", description="Optional model description")
    version: str = Field(default="custom", description="Optional model version label")


@router.get("/", response_model=list[dict[str, Any]])
def list_models(task_type: str | None = Query(None, description="Filter by task: detect, pose, segment")):
    """Return all registered models, optionally filtered by task type."""
    return get_available_models(task_type=task_type)


@router.get("/{name}", response_model=dict[str, Any])
def get_model(name: str):
    """Return metadata for a specific model by name."""
    try:
        return get_model_by_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{name}/ensure", status_code=202)
def trigger_model_download(name: str, background_tasks: BackgroundTasks):
    """
    Ensure a model is available on disk (triggers auto-download if needed).

    The download runs in a background task; the endpoint returns immediately
    with 202 Accepted.  Clients may poll ``GET /models/{name}`` and check
    ``is_available`` to monitor progress.
    """
    try:
        get_model_by_name(name)  # raises 404 if model is unknown
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    background_tasks.add_task(ensure_model_available, name)
    return {"message": f"Download initiated for '{name}'", "model": name}


@router.post("/catalog/register", response_model=dict[str, Any], status_code=201)
def register_model(payload: RegisterModelRequest):
    """Register a custom model entry so it appears in the Settings model catalog."""
    try:
        return register_yolo_model(
            payload.name,
            task_type=payload.task_type,
            description=payload.description,
            version=payload.version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
