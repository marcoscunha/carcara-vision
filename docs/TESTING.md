# 🧪 Testing

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run a specific test file
uv run pytest tests/src/services/test_detection_service.py -v

# Run SDK and worker integration-focused tests
uv run pytest tests/src/ml/sdk -v
uv run pytest tests/src/services/test_object_detection_sdk_service.py -v
uv run pytest tests/src/services/test_inference_worker_sdk.py -v

# Lint + formatting checks
uv run pre-commit run --all-files
```

## Worker Runtime Controls (SDK)

Inference workers now instantiate SDK pipelines directly. Per-stream overrides
can be set under `stream_metadata`:

- `detection_runtime`: `auto|yolo|onnxruntime|tensorrt|openai_vlm|ollama_vlm|local_vlm`
- `detection_dtype`: `auto|fp32|fp16|int8`
- `detection_providers`: ordered ORT provider list, for example:

```json
{
  "detection_runtime": "onnxruntime",
  "detection_dtype": "fp16",
  "detection_providers": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
}
```
