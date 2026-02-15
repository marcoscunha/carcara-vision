from fastapi import APIRouter
from fastapi import HTTPException

from ...api.models.inference_runtime import InferenceRuntimeConfigResponse
from ...api.models.inference_runtime import InferenceRuntimeConfigUpdate
from ...core.config import settings
from ...services.inference_runtime import inference_runtime_service

router = APIRouter()


@router.get("/", response_model=InferenceRuntimeConfigResponse)
def get_inference_runtime_config() -> InferenceRuntimeConfigResponse:
    config = inference_runtime_service.get()
    return InferenceRuntimeConfigResponse(
        model_name=config.model_name,
        accelerator=config.accelerator.value,
        available_models=settings.SUPPORTED_MODELS,
        available_accelerators=inference_runtime_service.list_available_accelerators(),
    )


@router.put("/", response_model=InferenceRuntimeConfigResponse)
def update_inference_runtime_config(payload: InferenceRuntimeConfigUpdate) -> InferenceRuntimeConfigResponse:
    try:
        updated = inference_runtime_service.update(
            model_name=payload.model_name,
            accelerator=payload.accelerator,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid accelerator: {payload.accelerator}") from exc

    return InferenceRuntimeConfigResponse(
        model_name=updated.model_name,
        accelerator=updated.accelerator.value,
        available_models=settings.SUPPORTED_MODELS,
        available_accelerators=inference_runtime_service.list_available_accelerators(),
    )
