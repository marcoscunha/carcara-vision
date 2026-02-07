from typing import Any

from fastapi import APIRouter, HTTPException

from ...services.models import get_available_models, get_model_by_name

router = APIRouter()


@router.get("/", response_model=list[dict[str, Any]])
def read_models():
    """
    Get a list of available models.
    """
    return get_available_models()


@router.get("/{name}", response_model=dict[str, Any])
def read_model(name: str):
    """
    Get a model by its name.
    """
    try:
        return get_model_by_name(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
