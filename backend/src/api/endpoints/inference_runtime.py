from fastapi import APIRouter
from fastapi import HTTPException

from ...api.models.inference_runtime import InferenceRuntimeConfigResponse
from ...api.models.inference_runtime import InferenceRuntimeConfigUpdate
from ...services.inference_runtime import inference_runtime_service

router = APIRouter()


@router.get("/", response_model=InferenceRuntimeConfigResponse)
def get_inference_runtime_config() -> InferenceRuntimeConfigResponse:
    config = inference_runtime_service.get()
    return InferenceRuntimeConfigResponse(
        model_name=config.model_name,
        accelerator=config.accelerator.value,
        task_type=config.task_type,
        acceleration_profile=config.acceleration_profile,
        accel_preprocess_mode=config.accel_preprocess_mode,
        accel_postprocess_mode=config.accel_postprocess_mode,
        accel_annotate_mode=config.accel_annotate_mode,
        accel_encoder_mode=config.accel_encoder_mode,
        available_models=inference_runtime_service.list_available_models(),
        available_accelerators=inference_runtime_service.list_available_accelerators(),
    )


@router.put("/", response_model=InferenceRuntimeConfigResponse)
def update_inference_runtime_config(payload: InferenceRuntimeConfigUpdate) -> InferenceRuntimeConfigResponse:
    try:
        updated = inference_runtime_service.update(
            model_name=payload.model_name,
            accelerator=payload.accelerator,
            task_type=payload.task_type,
            refresh_capabilities=payload.refresh_capabilities,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid accelerator: {payload.accelerator}") from exc

    return InferenceRuntimeConfigResponse(
        model_name=updated.model_name,
        accelerator=updated.accelerator.value,
        task_type=updated.task_type,
        acceleration_profile=updated.acceleration_profile,
        accel_preprocess_mode=updated.accel_preprocess_mode,
        accel_postprocess_mode=updated.accel_postprocess_mode,
        accel_annotate_mode=updated.accel_annotate_mode,
        accel_encoder_mode=updated.accel_encoder_mode,
        available_models=inference_runtime_service.list_available_models(),
        available_accelerators=inference_runtime_service.list_available_accelerators(),
    )
