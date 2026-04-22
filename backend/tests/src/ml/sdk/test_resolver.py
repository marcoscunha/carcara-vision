"""
Unit tests for the resolver decision matrix.

These tests exercise *only* the pure logic in resolver.py and never touch
real hardware or load weights.  All hardware-detection calls are patched.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from src.ml.base import HardwareAccelerator
from src.ml.base import ModelType
from src.ml.sdk.config import PipelineConfig
from src.ml.sdk.exceptions import DeviceUnavailableError
from src.ml.sdk.exceptions import ModelNotFoundError
from src.ml.sdk.exceptions import RuntimeNotSupportedError
from src.ml.sdk.resolver import _resolve_accelerator
from src.ml.sdk.resolver import _resolve_dtype
from src.ml.sdk.resolver import _resolve_model_type
from src.ml.sdk.resolver import _resolve_ort_providers
from src.ml.sdk.resolver import _resolve_runtime
from src.ml.sdk.resolver import resolve

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #


def _cfg(**kwargs) -> PipelineConfig:
    """Build a minimal PipelineConfig, overriding any fields via kwargs."""
    defaults = dict(task="object-detection", model="model.pt")
    defaults.update(kwargs)
    return PipelineConfig(**defaults)


# --------------------------------------------------------------------------- #
# _resolve_model_type                                                          #
# --------------------------------------------------------------------------- #


class TestResolveModelType:
    def test_vlm_task_returns_vlm(self):
        assert _resolve_model_type("image-text-to-text", "any.pt") == ModelType.VLM

    def test_engine_extension_returns_tensorrt(self):
        assert _resolve_model_type("object-detection", "best.engine") == ModelType.TENSORRT

    def test_trt_extension_returns_tensorrt(self):
        assert _resolve_model_type("object-detection", "best.trt") == ModelType.TENSORRT

    def test_onnx_extension_returns_onnx(self):
        assert _resolve_model_type("object-detection", "best.onnx") == ModelType.ONNX

    def test_pt_extension_returns_yolo(self):
        assert _resolve_model_type("object-detection", "yolov8n.pt") == ModelType.YOLO

    def test_unknown_extension_defaults_to_task_map(self):
        assert _resolve_model_type("object-detection", "model.bin") == ModelType.YOLO


# --------------------------------------------------------------------------- #
# _resolve_accelerator                                                         #
# --------------------------------------------------------------------------- #


class TestResolveAccelerator:
    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CUDA,
    )
    def test_auto_returns_best_accelerator(self, mock_detect):
        result = _resolve_accelerator("auto")
        assert result == HardwareAccelerator.CUDA
        mock_detect.assert_called_once()

    @patch(
        "src.ml.sdk.resolver.HardwareDetector.detect_all",
        return_value={HardwareAccelerator.CUDA: True},
    )
    def test_explicit_cuda_when_available(self, _mock):
        assert _resolve_accelerator("cuda") == HardwareAccelerator.CUDA

    @patch(
        "src.ml.sdk.resolver.HardwareDetector.detect_all",
        return_value={HardwareAccelerator.CUDA: False},
    )
    def test_explicit_cuda_when_unavailable_raises(self, _mock):
        with pytest.raises(DeviceUnavailableError):
            _resolve_accelerator("cuda")

    def test_unknown_device_raises(self):
        with pytest.raises(DeviceUnavailableError):
            _resolve_accelerator("hailo")


# --------------------------------------------------------------------------- #
# _resolve_runtime                                                             #
# --------------------------------------------------------------------------- #


class TestResolveRuntime:
    def test_engine_extension_auto_selects_tensorrt(self):
        result = _resolve_runtime("object-detection", "auto", "model.engine", HardwareAccelerator.CPU)
        assert result == "tensorrt"

    def test_trt_extension_auto_selects_tensorrt(self):
        result = _resolve_runtime("object-detection", "auto", "model.trt", HardwareAccelerator.CPU)
        assert result == "tensorrt"

    def test_onnx_extension_auto_selects_onnxruntime(self):
        result = _resolve_runtime("object-detection", "auto", "model.onnx", HardwareAccelerator.CPU)
        assert result == "onnxruntime"

    def test_pt_extension_auto_selects_yolo(self):
        result = _resolve_runtime("object-detection", "auto", "model.pt", HardwareAccelerator.CPU)
        assert result == "yolo"

    def test_auto_with_tensorrt_accelerator(self):
        result = _resolve_runtime("object-detection", "auto", "model.bin", HardwareAccelerator.TENSORRT)
        assert result == "tensorrt"

    def test_auto_with_cuda_accelerator(self):
        result = _resolve_runtime("object-detection", "auto", "model.bin", HardwareAccelerator.CUDA)
        assert result == "onnxruntime"

    def test_auto_cpu_fallback(self):
        result = _resolve_runtime("object-detection", "auto", "model.bin", HardwareAccelerator.CPU)
        assert result == "yolo"

    def test_explicit_runtime_returned_as_is_when_available(self):
        # "yolo" has no required import so it always passes
        result = _resolve_runtime("object-detection", "yolo", "model.pt", HardwareAccelerator.CPU)
        assert result == "yolo"

    def test_explicit_runtime_raises_when_package_missing(self):
        with patch("builtins.__import__", side_effect=ImportError), pytest.raises(RuntimeNotSupportedError):
            _resolve_runtime("object-detection", "tensorrt", "model.engine", HardwareAccelerator.TENSORRT)

    def test_vlm_auto_runtime(self):
        result = _resolve_runtime("image-text-to-text", "auto", "llava", HardwareAccelerator.CPU)
        assert result == "ollama_vlm"

    def test_vlm_task_rejects_vision_runtime(self):
        with pytest.raises(RuntimeNotSupportedError):
            _resolve_runtime("image-text-to-text", "onnxruntime", "llava", HardwareAccelerator.CPU)


# --------------------------------------------------------------------------- #
# _resolve_dtype                                                               #
# --------------------------------------------------------------------------- #


class TestResolveDtype:
    @pytest.mark.parametrize(
        "accelerator",
        [HardwareAccelerator.CUDA, HardwareAccelerator.TENSORRT, HardwareAccelerator.JETSON],
    )
    def test_auto_picks_fp16_for_gpu_accelerators(self, accelerator):
        assert _resolve_dtype("auto", "yolo", accelerator) == "fp16"

    def test_auto_picks_fp32_for_cpu(self):
        assert _resolve_dtype("auto", "yolo", HardwareAccelerator.CPU) == "fp32"

    def test_explicit_dtype_returned_unchanged(self):
        assert _resolve_dtype("int8", "tensorrt", HardwareAccelerator.TENSORRT) == "int8"


# --------------------------------------------------------------------------- #
# _resolve_ort_providers                                                       #
# --------------------------------------------------------------------------- #


class TestResolveOrtProviders:
    def test_non_ort_runtime_returns_empty(self):
        assert _resolve_ort_providers("yolo", HardwareAccelerator.CPU) == []
        assert _resolve_ort_providers("tensorrt", HardwareAccelerator.TENSORRT) == []

    def test_ort_cpu_returns_only_cpu_provider(self):
        providers = _resolve_ort_providers("onnxruntime", HardwareAccelerator.CPU)
        assert providers == ["CPUExecutionProvider"]

    def test_ort_cuda_includes_cuda_and_cpu(self):
        providers = _resolve_ort_providers("onnxruntime", HardwareAccelerator.CUDA)
        assert "CUDAExecutionProvider" in providers
        assert providers[-1] == "CPUExecutionProvider"

    def test_ort_tensorrt_includes_trt_cuda_cpu(self):
        providers = _resolve_ort_providers("onnxruntime", HardwareAccelerator.TENSORRT)
        assert providers[0] == "TensorrtExecutionProvider"
        assert "CUDAExecutionProvider" not in providers  # TRT includes CUDA implicitly
        assert providers[-1] == "CPUExecutionProvider"

    def test_explicit_ort_providers_are_used_in_order(self):
        providers = _resolve_ort_providers(
            "onnxruntime",
            HardwareAccelerator.CPU,
            explicit_providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        assert providers == ["CUDAExecutionProvider", "CPUExecutionProvider"]

    def test_explicit_ort_providers_append_cpu_fallback(self):
        providers = _resolve_ort_providers(
            "onnxruntime",
            HardwareAccelerator.CPU,
            explicit_providers=["TensorrtExecutionProvider"],
        )
        assert providers == ["TensorrtExecutionProvider", "CPUExecutionProvider"]

    def test_unknown_explicit_provider_raises(self):
        with pytest.raises(RuntimeNotSupportedError):
            _resolve_ort_providers(
                "onnxruntime",
                HardwareAccelerator.CPU,
                explicit_providers=["NotAProvider"],
            )


# --------------------------------------------------------------------------- #
# resolve() integration (all helpers together)                                 #
# --------------------------------------------------------------------------- #


class TestResolveIntegration:
    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CPU,
    )
    def test_resolve_pt_model_file(self, _mock, tmp_path):
        model_file = tmp_path / "yolov8n.pt"
        model_file.touch()

        plan = resolve(_cfg(model=str(model_file)))

        assert plan.model_path == str(model_file)
        assert plan.model_type == ModelType.YOLO
        assert plan.runtime == "yolo"
        assert plan.accelerator == HardwareAccelerator.CPU
        assert plan.dtype == "fp32"

    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CUDA,
    )
    def test_resolve_onnx_model_file_cuda(self, _mock, tmp_path):
        model_file = tmp_path / "best.onnx"
        model_file.touch()

        plan = resolve(_cfg(model=str(model_file)))

        assert plan.model_type == ModelType.ONNX
        assert plan.runtime == "onnxruntime"
        assert plan.accelerator == HardwareAccelerator.CUDA
        assert plan.dtype == "fp16"
        assert "CUDAExecutionProvider" in plan.providers

    def test_resolve_missing_model_raises(self):
        with pytest.raises(ModelNotFoundError):
            resolve(_cfg(model="does_not_exist.pt"))

    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CPU,
    )
    def test_build_model_config_round_trip(self, _mock, tmp_path):
        model_file = tmp_path / "model.pt"
        model_file.touch()

        plan = resolve(_cfg(model=str(model_file), confidence=0.6, iou=0.3))
        mc = plan.build_model_config()

        assert mc.confidence_threshold == 0.6
        assert mc.iou_threshold == 0.3
        assert mc.preferred_accelerator == HardwareAccelerator.CPU

    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CPU,
    )
    def test_resolve_vlm_model_name_without_file(self, _mock):
        plan = resolve(_cfg(task="image-text-to-text", model="llava"))

        assert plan.model_path == "llava"
        assert plan.model_type == ModelType.VLM
        assert plan.runtime == "ollama_vlm"
        assert plan.extra.get("vlm_backend") == "ollama"

    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CPU,
    )
    @patch("builtins.__import__", return_value=object())
    def test_resolve_with_explicit_ort_providers_persists_in_plan_and_config(self, _mock_import, _mock, tmp_path):
        model_file = tmp_path / "best.onnx"
        model_file.touch()

        plan = resolve(
            _cfg(
                model=str(model_file),
                runtime="onnxruntime",
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
        )

        assert plan.providers == ["CUDAExecutionProvider", "CPUExecutionProvider"]
        mc = plan.build_model_config()
        assert mc.options.get("providers") == ["CUDAExecutionProvider", "CPUExecutionProvider"]

    @patch("builtins.__import__", return_value=object())
    @patch(
        "src.ml.sdk.resolver.HardwareDetector.get_best_accelerator",
        return_value=HardwareAccelerator.CPU,
    )
    def test_explicit_openai_runtime_is_valid_for_vlm_task(self, _mock_accel, mock_import):
        plan = resolve(
            _cfg(
                task="image-text-to-text",
                model="gpt-4o",
                runtime="openai_vlm",
            )
        )
        assert plan.runtime == "openai_vlm"
