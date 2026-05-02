"""
ONNX Inference Engine - Cross-platform model inference.

Supports ONNX Runtime with various execution providers:
- CPU (default)
- CUDA
- TensorRT
- OpenVINO
- CoreML (macOS)
"""

import logging
import time
from typing import Any

import cv2
import numpy as np

from ..base import BaseInferenceEngine
from ..base import HardwareAccelerator
from ..base import InferenceResult
from ..base import ModelConfig

logger = logging.getLogger(__name__)


class ONNXEngine(BaseInferenceEngine):
    """
    ONNX Runtime inference engine.

    Provides cross-platform inference with automatic
    execution provider selection.
    """

    # Mapping of accelerators to ONNX execution providers
    PROVIDER_MAP = {
        HardwareAccelerator.CUDA: "CUDAExecutionProvider",
        HardwareAccelerator.TENSORRT: "TensorrtExecutionProvider",
        HardwareAccelerator.OPENVINO: "OpenVINOExecutionProvider",
        HardwareAccelerator.CPU: "CPUExecutionProvider",
    }

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._session = None
        self._input_name: str | None = None
        self._output_names: list[str] = []
        self._class_names: dict[int, str] = {}

    def get_supported_accelerators(self) -> list[HardwareAccelerator]:
        """Return accelerators supported by ONNX Runtime."""
        try:
            import onnxruntime as ort

            available = []
            providers = ort.get_available_providers()

            if "CUDAExecutionProvider" in providers:
                available.append(HardwareAccelerator.CUDA)
            if "TensorrtExecutionProvider" in providers:
                available.append(HardwareAccelerator.TENSORRT)
            if "OpenVINOExecutionProvider" in providers:
                available.append(HardwareAccelerator.OPENVINO)

            available.append(HardwareAccelerator.CPU)  # Always available

            return available

        except ImportError:
            return [HardwareAccelerator.CPU]

    def load(self) -> bool:
        """Load ONNX model."""
        try:
            import onnxruntime as ort

            # Determine execution providers
            providers = self._get_providers()

            logger.info(f"Loading ONNX model from {self.config.model_path}")
            logger.info(f"Execution providers: {providers}")

            # Session options
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            # Create session
            self._session = ort.InferenceSession(self.config.model_path, sess_options=sess_options, providers=providers)

            # Get input/output info
            inputs = self._session.get_inputs()
            outputs = self._session.get_outputs()

            self._input_name = inputs[0].name
            self._output_names = [o.name for o in outputs]

            # Determine actual provider used
            used_provider = self._session.get_providers()[0]
            self._current_accelerator = self._provider_to_accelerator(used_provider)

            self._is_loaded = True

            logger.info(f"ONNX model loaded, using {used_provider}")
            return True

        except ImportError:
            logger.error("onnxruntime not installed. Run: pip install onnxruntime")
            return False
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            return False

    def _get_providers(self) -> list[str]:
        """Get ordered list of execution providers to try."""
        import onnxruntime as ort

        available = ort.get_available_providers()

        explicit = self.config.options.get("providers")
        if isinstance(explicit, list) and explicit:
            providers = [p for p in explicit if p in available or p == "CPUExecutionProvider"]
            if "CPUExecutionProvider" not in providers:
                providers.append("CPUExecutionProvider")
            return providers

        providers = []

        # Try preferred first
        preferred = self.PROVIDER_MAP.get(self.config.preferred_accelerator)
        if preferred and preferred in available:
            providers.append(preferred)

        # Add fallbacks
        for fallback in self.config.fallback_accelerators:
            provider = self.PROVIDER_MAP.get(fallback)
            if provider and provider in available and provider not in providers:
                providers.append(provider)

        # Always have CPU as final fallback
        if "CPUExecutionProvider" not in providers:
            providers.append("CPUExecutionProvider")

        return providers

    def _provider_to_accelerator(self, provider: str) -> HardwareAccelerator:
        """Convert ONNX provider name to HardwareAccelerator."""
        for acc, prov in self.PROVIDER_MAP.items():
            if prov == provider:
                return acc
        return HardwareAccelerator.CPU

    def unload(self) -> None:
        """Release ONNX session."""
        if self._session is not None:
            del self._session
            self._session = None

        self._is_loaded = False
        logger.info("ONNX model unloaded")

    def infer(self, image: np.ndarray, **kwargs) -> InferenceResult:
        """
        Run ONNX inference on an image.

        Args:
            image: Input image (BGR, HWC format)
            **kwargs: Additional parameters

        Returns:
            InferenceResult with detections
        """
        if not self._is_loaded or self._session is None:
            raise RuntimeError("Model not loaded")

        start_time = time.perf_counter()

        # Preprocess
        preprocess_start = time.perf_counter()
        input_tensor = self._preprocess(image)
        preprocess_ms = (time.perf_counter() - preprocess_start) * 1000

        # Run inference
        outputs = self._session.run(self._output_names, {self._input_name: input_tensor})

        inference_time = (time.perf_counter() - start_time) * 1000

        # Parse results
        postprocess_start = time.perf_counter()
        result = InferenceResult(
            model_name=self.config.model_name,
            inference_time_ms=inference_time,
            hardware_used=self._current_accelerator or HardwareAccelerator.CPU,
            raw_output=outputs,
            preprocess_ms=preprocess_ms,
        )

        # Parse detections (YOLO format)
        detections = self._parse_yolo_output(outputs, image.shape[:2])
        for det in detections:
            result.add_detection(**det)

        result.postprocess_ms = (time.perf_counter() - postprocess_start) * 1000
        return result

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for ONNX model.

        Uses the torch.cuda path when the active execution provider is CUDA/TensorRT
        and torch.cuda is available.  Falls back to the CPU path otherwise.
        """
        if self._should_use_cuda_preprocess():
            return self._preprocess_cuda(image)
        return self._preprocess_cpu(image)

    def _should_use_cuda_preprocess(self) -> bool:
        """Return True when GPU preprocessing is viable for this session."""
        if self._current_accelerator not in (
            HardwareAccelerator.CUDA,
            HardwareAccelerator.TENSORRT,
        ):
            return False
        try:
            import torch

            return bool(torch.cuda.is_available())
        except ImportError:
            return False

    def _preprocess_cpu(self, image: np.ndarray) -> np.ndarray:
        """CPU preprocessing path (always available)."""
        target_w, target_h = self.config.input_size
        resized = cv2.resize(image, (target_w, target_h))
        if self.config.bgr_to_rgb:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        if self.config.normalize:
            resized = resized.astype(np.float32) / 255.0
        tensor = resized.transpose(2, 0, 1)
        tensor = np.expand_dims(tensor, axis=0)
        return tensor.astype(np.float32)

    def _preprocess_cuda(self, image: np.ndarray) -> np.ndarray:
        """GPU preprocessing path via torch.cuda.

        Fuses BGR→RGB, HWC→CHW, normalize, and bilinear resize into a single
        GPU pass.  Returns a contiguous float32 numpy array on the host so that
        ONNX Runtime can consume it regardless of execution provider.
        """
        import torch
        import torch.nn.functional

        target_w, target_h = self.config.input_size

        # Upload HWC uint8 frame to GPU
        t = torch.from_numpy(image).cuda()  # HWC uint8

        # BGR -> RGB (in-place channel reorder)
        if self.config.bgr_to_rgb:
            t = t[..., [2, 1, 0]]

        # HWC -> 1CHW float
        t = t.permute(2, 0, 1).unsqueeze(0).float()

        # Normalize
        if self.config.normalize:
            t = t / 255.0

        # Resize to model input size
        t = torch.nn.functional.interpolate(t, size=(target_h, target_w), mode="bilinear", align_corners=False)

        return t.squeeze(0).unsqueeze(0).contiguous().cpu().numpy()

    def _parse_yolo_output(self, outputs: list[np.ndarray], original_shape: tuple[int, int]) -> list[dict[str, Any]]:
        """
        Parse YOLO-format ONNX output.

        Args:
            outputs: Model outputs
            original_shape: Original image (H, W)

        Returns:
            List of detection dictionaries
        """
        detections = []

        if len(outputs) == 0:
            return detections

        output = outputs[0]

        # Handle different output formats
        if len(output.shape) == 3:
            # Shape: (1, num_classes + 4, num_detections) - YOLOv8
            output = output[0].T
        elif len(output.shape) == 2:
            # Shape: (num_detections, num_classes + 4)
            pass
        else:
            logger.warning(f"Unexpected output shape: {output.shape}")
            return detections

        orig_h, orig_w = original_shape
        input_w, input_h = self.config.input_size

        scale_x = orig_w / input_w
        scale_y = orig_h / input_h

        # Guard against malformed output tensors
        if output.shape[1] < 5:
            return self._apply_nms(detections)

        # ---- Vectorized parsing (replaces row-by-row Python loop) ----
        # output shape: (N, 4 + num_classes)
        boxes_raw = output[:, :4]  # (N, 4)  x_c, y_c, w, h
        class_scores = output[:, 4:]  # (N, num_classes)

        class_ids = np.argmax(class_scores, axis=1)  # (N,)
        confidences = class_scores[np.arange(len(output)), class_ids]  # (N,)

        # Confidence filter
        keep = confidences >= self.config.confidence_threshold
        if not np.any(keep):
            return detections

        boxes_raw = boxes_raw[keep]
        class_ids = class_ids[keep]
        confidences = confidences[keep]

        # Convert to corner format, scale to original image, and clamp
        x1 = np.clip((boxes_raw[:, 0] - boxes_raw[:, 2] / 2) * scale_x, 0, orig_w)
        y1 = np.clip((boxes_raw[:, 1] - boxes_raw[:, 3] / 2) * scale_y, 0, orig_h)
        x2 = np.clip((boxes_raw[:, 0] + boxes_raw[:, 2] / 2) * scale_x, 0, orig_w)
        y2 = np.clip((boxes_raw[:, 1] + boxes_raw[:, 3] / 2) * scale_y, 0, orig_h)

        detections = [
            {
                "bbox": [float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i])],
                "class_id": int(class_ids[i]),
                "class_name": self._class_names.get(int(class_ids[i]), f"class_{class_ids[i]}"),
                "confidence": float(confidences[i]),
            }
            for i in range(len(x1))
        ]

        # Apply NMS
        detections = self._apply_nms(detections)

        return detections

    def _apply_nms(self, detections: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply Non-Maximum Suppression to detections."""
        if len(detections) == 0:
            return detections

        boxes = np.array([d["bbox"] for d in detections])
        scores = np.array([d["confidence"] for d in detections])

        # Simple NMS implementation
        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(),
            scores.tolist(),
            self.config.confidence_threshold,
            self.config.iou_threshold,
        )

        if len(indices) == 0:
            return []

        indices = indices.flatten()
        return [detections[i] for i in indices]

    def set_class_names(self, class_names: dict[int, str]) -> None:
        """Set class names for detection output."""
        self._class_names = class_names

    def get_model_info(self) -> dict[str, Any]:
        """Get ONNX model information."""
        if not self._is_loaded or self._session is None:
            return {}

        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()

        return {
            "inputs": [{"name": i.name, "shape": i.shape, "type": i.type} for i in inputs],
            "outputs": [{"name": o.name, "shape": o.shape, "type": o.type} for o in outputs],
            "providers": self._session.get_providers(),
        }
