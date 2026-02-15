from pydantic import BaseModel


class InferenceRuntimeConfigResponse(BaseModel):
    model_name: str
    accelerator: str
    available_models: list[str]
    available_accelerators: list[str]


class InferenceRuntimeConfigUpdate(BaseModel):
    model_name: str | None = None
    accelerator: str | None = None


class StreamInferenceMetrics(BaseModel):
    stream_id: int
    samples: int
    avg_inference_time_ms: float
    min_inference_time_ms: float
    max_inference_time_ms: float
    fps: float
    last_inference_time_ms: float
    model_name: str | None = None
    accelerator: str | None = None


class GlobalInferenceMetrics(BaseModel):
    global_metrics: dict
    per_stream: dict[int, StreamInferenceMetrics]
