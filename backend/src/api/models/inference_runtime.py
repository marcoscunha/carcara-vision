from pydantic import BaseModel


class InferenceRuntimeConfigResponse(BaseModel):
    model_name: str
    accelerator: str
    task_type: str = "detect"
    acceleration_profile: str = "generic"
    accel_preprocess_mode: str = "python"
    accel_postprocess_mode: str = "python"
    accel_annotate_mode: str = "cpu"
    accel_encoder_mode: str = "x264"
    available_models: list[str]
    available_accelerators: list[str]
    available_task_types: list[str] = ["detect", "pose", "segment"]


class InferenceRuntimeConfigUpdate(BaseModel):
    model_name: str | None = None
    accelerator: str | None = None
    task_type: str | None = None
    refresh_capabilities: bool = False


class StreamInferenceMetrics(BaseModel):
    stream_id: int
    samples: int
    avg_inference_time_ms: float
    min_inference_time_ms: float
    max_inference_time_ms: float
    fps: float
    inference_throughput_fps: float = 0.0
    target_inference_fps: float = 0.0
    output_fps: float = 0.0
    last_inference_time_ms: float
    model_name: str | None = None
    accelerator: str | None = None


class GlobalInferenceMetrics(BaseModel):
    global_metrics: dict
    per_stream: dict[int, StreamInferenceMetrics]
