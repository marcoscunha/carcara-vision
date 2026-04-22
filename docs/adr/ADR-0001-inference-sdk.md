# ADR-0001: Inference SDK (HF-Inspired)

Date: 2026-04-22
Status: Accepted, Implemented

## Context

The backend supports multiple model formats and runtimes (`.pt`, `.onnx`, `.engine`) and multiple hardware targets (CPU, CUDA, TensorRT, Jetson). Before this ADR, runtime and model selection logic was spread across services and workers.

This created duplicated decision paths, drift risk, and a higher maintenance cost for adding new runtimes or model families.

## Decision

Adopt a single SDK facade modeled after `transformers.pipeline(...)` with explicit but optional controls.

Public entrypoint:

- `from src.ml.sdk import pipeline`

Core principles:

1. One-line task entrypoint
2. Auto resolution by default (`device="auto"`, `runtime="auto"`, `dtype="auto"`)
3. Explicit override capability for power users
4. Stable task-level output contracts independent from engine internals
5. Single resolution path reused by services and workers

## Runtime Vocabulary

- runtime: `yolo | onnxruntime | tensorrt | openai_vlm | ollama_vlm | local_vlm`
- device: `cpu | cuda | tensorrt | jetson`
- providers (ORT): `CPUExecutionProvider | CUDAExecutionProvider | TensorrtExecutionProvider`

Provider override is supported via `PipelineConfig.providers` and `pipeline(..., providers=[...])`.

## Implementation Summary

Implemented in `backend/src/ml/sdk/`:

- `config.py`: user-facing `PipelineConfig`
- `resolver.py`: runtime/device/dtype/provider decision matrix
- `pipeline.py`: facade constructor
- `tasks.py`: adapters (`ObjectDetectionPipeline`, `VLMPipeline`)
- `types.py`: stable output contracts
- `exceptions.py`: actionable SDK error model

Integrations completed:

- `ObjectDetectionService` internally uses SDK pipeline
- `InferenceWorker` initializes SDK pipeline directly
- Worker config supports explicit `runtime`, `dtype`, and `providers`

## Consequences

Positive:

- Centralized and consistent runtime resolution
- Easier onboarding and predictable public API
- Reduced drift between service and worker inference paths
- Better testability via resolver/adapter contracts

Tradeoffs:

- Extra adapter layer introduces a small abstraction cost
- Requires clear docs for when to use auto vs explicit runtime/provider settings

## Validation

Implemented test coverage includes:

- Resolver matrix tests
- Object-detection and VLM adapter contract tests
- Service SDK integration tests
- Worker SDK initialization and inference-path regression tests
