"""
TensorRT Inference Engine - NVIDIA GPU optimized inference.

Provides high-performance inference using TensorRT engines,
optimized for NVIDIA GPUs including Jetson devices.
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


class TensorRTEngine(BaseInferenceEngine):
    """
    TensorRT inference engine for NVIDIA GPUs.

    Features:
    - Native TensorRT engine loading
    - Dynamic batch size support
    - FP16/INT8 precision
    - Jetson optimization
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._context = None
        self._engine = None
        self._bindings = None
        self._class_names: Dict[int, str] = {}

    def get_supported_accelerators(self) -> List[HardwareAccelerator]:
        """TensorRT only supports NVIDIA GPUs."""
        return [
            HardwareAccelerator.CUDA,
            HardwareAccelerator.TENSORRT,
            HardwareAccelerator.JETSON,
        ]

    def load(self) -> bool:
        """Load TensorRT engine."""
        try:
            import pycuda.autoinit
            import pycuda.driver as cuda
            import tensorrt as trt

            TRT_LOGGER = trt.Logger(trt.Logger.WARNING)

            model_path = Path(self.config.model_path)

            logger.info(f"Loading TensorRT engine from {model_path}")

            # Load engine
            with open(model_path, "rb") as f:
                runtime = trt.Runtime(TRT_LOGGER)
                self._engine = runtime.deserialize_cuda_engine(f.read())

            if self._engine is None:
                logger.error("Failed to deserialize TensorRT engine")
                return False

            # Create execution context
            self._context = self._engine.create_execution_context()

            # Allocate buffers
            self._allocate_buffers()

            self._is_loaded = True
            self._current_accelerator = HardwareAccelerator.TENSORRT

            logger.info("TensorRT engine loaded successfully")
            return True

        except ImportError as e:
            logger.error(f"TensorRT dependencies not available: {e}")
            logger.error("Install with: pip install tensorrt pycuda")
            return False
        except Exception as e:
            logger.error(f"Failed to load TensorRT engine: {e}")
            return False

    def _allocate_buffers(self) -> None:
        """Allocate input/output buffers."""
        import pycuda.driver as cuda

        self._bindings = {
            "inputs": [],
            "outputs": [],
            "input_names": [],
            "output_names": [],
            "stream": cuda.Stream()
        }

        for i in range(self._engine.num_bindings):
            name = self._engine.get_binding_name(i)
            dtype = self._engine.get_binding_dtype(i)
            shape = self._engine.get_binding_shape(i)

            # Calculate size
            size = abs(np.prod(shape))

            # Convert TensorRT dtype to numpy
            if dtype == trt.float32:
                np_dtype = np.float32
            elif dtype == trt.float16:
                np_dtype = np.float16
            elif dtype == trt.int32:
                np_dtype = np.int32
            else:
                np_dtype = np.float32

            # Allocate host and device memory
            host_mem = cuda.pagelocked_empty(size, np_dtype)
            device_mem = cuda.mem_alloc(host_mem.nbytes)

            binding = {
                "name": name,
                "shape": shape,
                "dtype": np_dtype,
                "host": host_mem,
                "device": device_mem,
            }

            if self._engine.binding_is_input(i):
                self._bindings["inputs"].append(binding)
                self._bindings["input_names"].append(name)
            else:
                self._bindings["outputs"].append(binding)
                self._bindings["output_names"].append(name)

    def unload(self) -> None:
        """Release TensorRT resources."""
        if self._bindings:
            # Free device memory
            for binding in self._bindings["inputs"] + self._bindings["outputs"]:
                if "device" in binding:
                    binding["device"].free()
            self._bindings = None

        if self._context:
            del self._context
            self._context = None

        if self._engine:
            del self._engine
            self._engine = None

        self._is_loaded = False
        logger.info("TensorRT engine unloaded")

    def infer(
        self,
        image: np.ndarray,
        **kwargs
    ) -> InferenceResult:
        """
        Run TensorRT inference on an image.

        Args:
            image: Input image (BGR, HWC format)
            **kwargs: Additional parameters

        Returns:
            InferenceResult with detections
        """
        if not self._is_loaded:
            raise RuntimeError("Engine not loaded")

        import pycuda.driver as cuda

        start_time = time.perf_counter()

        # Preprocess
        input_tensor = self._preprocess(image)

        # Copy input to device
        input_binding = self._bindings["inputs"][0]
        np.copyto(input_binding["host"], input_tensor.ravel())
        cuda.memcpy_htod_async(
            input_binding["device"],
            input_binding["host"],
            self._bindings["stream"]
        )

        # Run inference
        bindings = [b["device"] for b in self._bindings["inputs"]]
        bindings += [b["device"] for b in self._bindings["outputs"]]

        self._context.execute_async_v2(
            bindings=bindings,
            stream_handle=self._bindings["stream"].handle
        )

        # Copy outputs to host
        outputs = []
        for output_binding in self._bindings["outputs"]:
            cuda.memcpy_dtoh_async(
                output_binding["host"],
                output_binding["device"],
                self._bindings["stream"]
            )

        # Synchronize
        self._bindings["stream"].synchronize()

        # Collect outputs
        for output_binding in self._bindings["outputs"]:
            output = output_binding["host"].reshape(output_binding["shape"])
            outputs.append(output.copy())

        inference_time = (time.perf_counter() - start_time) * 1000

        # Parse results
        result = InferenceResult(
            model_name=self.config.model_name,
            inference_time_ms=inference_time,
            hardware_used=HardwareAccelerator.TENSORRT,
            raw_output=outputs,
        )

        # Parse detections
        detections = self._parse_yolo_output(outputs, image.shape[:2])
        for det in detections:
            result.add_detection(**det)

        return result

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for TensorRT model."""
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

        return np.ascontiguousarray(tensor, dtype=np.float32)

    def _parse_yolo_output(
        self,
        outputs: List[np.ndarray],
        original_shape: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """Parse YOLO-format TensorRT output."""
        detections = []

        if len(outputs) == 0:
            return detections

        output = outputs[0]

        # Handle different output formats
        if len(output.shape) == 3:
            output = output[0].T
        elif len(output.shape) == 2:
            pass
        else:
            return detections

        orig_h, orig_w = original_shape
        input_w, input_h = self.config.input_size

        scale_x = orig_w / input_w
        scale_y = orig_h / input_h

        for row in output:
            if len(row) < 5:
                continue

            x_center, y_center, width, height = row[:4]
            class_scores = row[4:]

            class_id = np.argmax(class_scores)
            confidence = class_scores[class_id]

            if confidence < self.config.confidence_threshold:
                continue

            x1 = (x_center - width / 2) * scale_x
            y1 = (y_center - height / 2) * scale_y
            x2 = (x_center + width / 2) * scale_x
            y2 = (y_center + height / 2) * scale_y

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
        """Apply Non-Maximum Suppression."""
        if len(detections) == 0:
            return detections

        boxes = np.array([d["bbox"] for d in detections])
        scores = np.array([d["confidence"] for d in detections])

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

    @staticmethod
    def build_engine(
        onnx_path: str,
        engine_path: str,
        fp16: bool = True,
        int8: bool = False,
        max_batch_size: int = 1,
        workspace_gb: int = 4
    ) -> bool:
        """
        Build TensorRT engine from ONNX model.

        Args:
            onnx_path: Path to ONNX model
            engine_path: Path to save TensorRT engine
            fp16: Enable FP16 precision
            int8: Enable INT8 precision
            max_batch_size: Maximum batch size
            workspace_gb: Workspace size in GB

        Returns:
            True if successful
        """
        try:
            import tensorrt as trt

            TRT_LOGGER = trt.Logger(trt.Logger.INFO)

            builder = trt.Builder(TRT_LOGGER)
            network = builder.create_network(
                1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
            )
            parser = trt.OnnxParser(network, TRT_LOGGER)

            # Parse ONNX
            with open(onnx_path, "rb") as f:
                if not parser.parse(f.read()):
                    for error in range(parser.num_errors):
                        logger.error(parser.get_error(error))
                    return False

            # Configure builder
            config = builder.create_builder_config()
            config.max_workspace_size = workspace_gb << 30

            if fp16 and builder.platform_has_fast_fp16:
                config.set_flag(trt.BuilderFlag.FP16)
                logger.info("FP16 enabled")

            if int8 and builder.platform_has_fast_int8:
                config.set_flag(trt.BuilderFlag.INT8)
                logger.info("INT8 enabled")

            # Build engine
            logger.info("Building TensorRT engine...")
            engine = builder.build_engine(network, config)

            if engine is None:
                logger.error("Failed to build engine")
                return False

            # Serialize
            with open(engine_path, "wb") as f:
                f.write(engine.serialize())

            logger.info(f"Engine saved to {engine_path}")
            return True

        except Exception as e:
            logger.error(f"Engine build failed: {e}")
            return False
            logger.error(f"Engine build failed: {e}")
            return False
