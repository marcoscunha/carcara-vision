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
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

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
        self._input_name: Optional[str] = None
        self._output_names: List[str] = []
        self._class_names: Dict[int, str] = {}

    def get_supported_accelerators(self) -> List[HardwareAccelerator]:
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
            sess_options.graph_optimization_level = (
                ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            )

            # Create session
            self._session = ort.InferenceSession(
                self.config.model_path,
                sess_options=sess_options,
                providers=providers
            )

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

    def _get_providers(self) -> List[str]:
        """Get ordered list of execution providers to try."""
        import onnxruntime as ort

        available = ort.get_available_providers()
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

    def infer(
        self,
        image: np.ndarray,
        **kwargs
    ) -> InferenceResult:
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
        input_tensor = self._preprocess(image)

        # Run inference
        outputs = self._session.run(
            self._output_names,
            {self._input_name: input_tensor}
        )

        inference_time = (time.perf_counter() - start_time) * 1000

        # Parse results
        result = InferenceResult(
            model_name=self.config.model_name,
            inference_time_ms=inference_time,
            hardware_used=self._current_accelerator or HardwareAccelerator.CPU,
            raw_output=outputs,
        )

        # Parse detections (YOLO format)
        detections = self._parse_yolo_output(outputs, image.shape[:2])
        for det in detections:
            result.add_detection(**det)

        return result

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for ONNX model."""
        target_w, target_h = self.config.input_size

        # Resize
        resized = cv2.resize(image, (target_w, target_h))

        # BGR to RGB
        if self.config.bgr_to_rgb:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Normalize
        if self.config.normalize:
            resized = resized.astype(np.float32) / 255.0

        # HWC to CHW
        tensor = resized.transpose(2, 0, 1)

        # Add batch dimension
        tensor = np.expand_dims(tensor, axis=0)

        return tensor.astype(np.float32)

    def _parse_yolo_output(
        self,
        outputs: List[np.ndarray],
        original_shape: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
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

        for row in output:
            # YOLO format: [x_center, y_center, width, height, class_scores...]
            if len(row) < 5:
                continue

            x_center, y_center, width, height = row[:4]
            class_scores = row[4:]

            # Get best class
            class_id = np.argmax(class_scores)
            confidence = class_scores[class_id]

            if confidence < self.config.confidence_threshold:
                continue

            # Convert to corner format and scale
            x1 = (x_center - width / 2) * scale_x
            y1 = (y_center - height / 2) * scale_y
            x2 = (x_center + width / 2) * scale_x
            y2 = (y_center + height / 2) * scale_y

            # Clamp to image bounds
            x1 = max(0, min(orig_w, x1))
            y1 = max(0, min(orig_h, y1))
            x2 = max(0, min(orig_w, x2))
            y2 = max(0, min(orig_h, y2))

            detections.append({
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "class_id": int(class_id),
                "class_name": self._class_names.get(int(class_id), f"class_{class_id}"),
                "confidence": float(confidence),
            })

        # Apply NMS
        detections = self._apply_nms(detections)

        return detections

    def _apply_nms(
        self,
        detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
            self.config.iou_threshold
        )

        if len(indices) == 0:
            return []

        indices = indices.flatten()
        return [detections[i] for i in indices]

    def set_class_names(self, class_names: Dict[int, str]) -> None:
        """Set class names for detection output."""
        self._class_names = class_names

    def get_model_info(self) -> Dict[str, Any]:
        """Get ONNX model information."""
        if not self._is_loaded or self._session is None:
            return {}

        inputs = self._session.get_inputs()
        outputs = self._session.get_outputs()

        return {
            "inputs": [
                {"name": i.name, "shape": i.shape, "type": i.type}
                for i in inputs
            ],
            "outputs": [
                {"name": o.name, "shape": o.shape, "type": o.type}
                for o in outputs
            ],
            "providers": self._session.get_providers(),
        }
        "providers": self._session.get_providers(),
        }
