"""
YOLO Inference Engine - Support for YOLOv5, YOLOv8, and YOLO11 models.
"""

import logging
import time
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import cv2
import numpy as np

from ..base import BaseInferenceEngine
from ..base import HardwareAccelerator
from ..base import InferenceResult
from ..base import ModelConfig

logger = logging.getLogger(__name__)


class YOLOEngine(BaseInferenceEngine):
    """
    YOLO inference engine using Ultralytics.

    Supports:
    - YOLOv5, YOLOv8, YOLO11
    - PyTorch, ONNX, TensorRT, TFLite backends
    - Object detection, segmentation, pose estimation
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._class_names: Dict[int, str] = {}

    def get_supported_accelerators(self) -> List[HardwareAccelerator]:
        """Return supported accelerators for YOLO models."""
        return [
            HardwareAccelerator.CPU,
            HardwareAccelerator.CUDA,
            HardwareAccelerator.TENSORRT,
            HardwareAccelerator.JETSON,
            HardwareAccelerator.OPENVINO,
        ]

    def load(self) -> bool:
        """Load the YOLO model."""
        try:
            from ultralytics import YOLO

            # Determine device
            device = self._resolve_device()

            logger.info(f"Loading YOLO model from {self.config.model_path}")
            logger.info(f"Target device: {device}")

            self._model = YOLO(self.config.model_path)

            # Move to device
            if device != "cpu":
                self._model.to(device)

            # Get class names
            if hasattr(self._model, "names"):
                self._class_names = self._model.names

            self._is_loaded = True
            self._current_accelerator = self.config.preferred_accelerator

            logger.info(f"YOLO model loaded successfully on {device}")
            return True

        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return False

    def _resolve_device(self) -> str:
        """Resolve the device string for PyTorch."""
        accelerator = self.config.preferred_accelerator

        if accelerator in [
            HardwareAccelerator.CUDA,
            HardwareAccelerator.TENSORRT,
            HardwareAccelerator.JETSON,
        ]:
            try:
                import torch
                if torch.cuda.is_available():
                    return "cuda:0"
            except ImportError:
                pass

        return "cpu"

    def unload(self) -> None:
        """Release model resources."""
        if self._model is not None:
            del self._model
            self._model = None

        # Clear CUDA cache if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        self._is_loaded = False
        logger.info("YOLO model unloaded")

    def infer(
        self,
        image: np.ndarray,
        classes: Optional[List[int]] = None,
        **kwargs
    ) -> InferenceResult:
        """
        Run YOLO inference on an image.

        Args:
            image: Input image (BGR, HWC format)
            classes: List of class IDs to detect (None = all)
            **kwargs: Additional parameters passed to YOLO

        Returns:
            InferenceResult with detections
        """
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        start_time = time.perf_counter()

        # Run inference
        results = self._model(
            image,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            max_det=self.config.max_detections,
            classes=classes,
            verbose=False,
            **kwargs
        )

        inference_time = (time.perf_counter() - start_time) * 1000

        # Parse results
        result = InferenceResult(
            model_name=self.config.model_name,
            inference_time_ms=inference_time,
            hardware_used=self._current_accelerator or HardwareAccelerator.CPU,
        )

        # Process detections
        if results and len(results) > 0:
            yolo_result = results[0]

            if hasattr(yolo_result, "boxes") and yolo_result.boxes is not None:
                for box in yolo_result.boxes:
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = self._class_names.get(class_id, f"class_{class_id}")

                    result.add_detection(
                        bbox=bbox,
                        class_name=class_name,
                        class_id=class_id,
                        confidence=confidence
                    )

            # Handle segmentation results
            if hasattr(yolo_result, "masks") and yolo_result.masks is not None:
                result.metadata["has_masks"] = True
                result.raw_output = yolo_result

            # Handle pose results
            if hasattr(yolo_result, "keypoints") and yolo_result.keypoints is not None:
                result.metadata["has_keypoints"] = True
                result.raw_output = yolo_result

        return result

    def infer_batch(
        self,
        images: List[np.ndarray],
        **kwargs
    ) -> List[InferenceResult]:
        """
        Run batch inference on multiple images.

        Args:
            images: List of input images
            **kwargs: Additional parameters

        Returns:
            List of InferenceResult objects
        """
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        start_time = time.perf_counter()

        # Run batch inference
        batch_results = self._model(
            images,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            max_det=self.config.max_detections,
            verbose=False,
            **kwargs
        )

        total_time = (time.perf_counter() - start_time) * 1000
        time_per_image = total_time / len(images)

        results = []
        for i, yolo_result in enumerate(batch_results):
            result = InferenceResult(
                model_name=self.config.model_name,
                inference_time_ms=time_per_image,
                hardware_used=self._current_accelerator or HardwareAccelerator.CPU,
            )

            if hasattr(yolo_result, "boxes") and yolo_result.boxes is not None:
                for box in yolo_result.boxes:
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = self._class_names.get(class_id, f"class_{class_id}")

                    result.add_detection(
                        bbox=bbox,
                        class_name=class_name,
                        class_id=class_id,
                        confidence=confidence
                    )

            results.append(result)

        return results

    def export(
        self,
        format: str = "onnx",
        output_path: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Export model to different formats.

        Args:
            format: Target format ("onnx", "engine", "tflite", "openvino")
            output_path: Custom output path
            **kwargs: Format-specific options

        Returns:
            Path to exported model
        """
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        try:
            export_path = self._model.export(format=format, **kwargs)
            logger.info(f"Model exported to {export_path}")
            return str(export_path)
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return None

    def get_class_names(self) -> Dict[int, str]:
        """Get model class names."""
        return self._class_names.copy()

    def track(
        self,
        image: np.ndarray,
        persist: bool = True,
        tracker: str = "bytetrack.yaml",
        **kwargs
    ) -> InferenceResult:
        """
        Run object tracking on an image.

        Args:
            image: Input image
            persist: Persist tracks across frames
            tracker: Tracker configuration
            **kwargs: Additional parameters

        Returns:
            InferenceResult with track IDs
        """
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        start_time = time.perf_counter()

        results = self._model.track(
            image,
            conf=self.config.confidence_threshold,
            iou=self.config.iou_threshold,
            persist=persist,
            tracker=tracker,
            verbose=False,
            **kwargs
        )

        inference_time = (time.perf_counter() - start_time) * 1000

        result = InferenceResult(
            model_name=self.config.model_name,
            inference_time_ms=inference_time,
            hardware_used=self._current_accelerator or HardwareAccelerator.CPU,
        )

        if results and len(results) > 0:
            yolo_result = results[0]

            if hasattr(yolo_result, "boxes") and yolo_result.boxes is not None:
                for box in yolo_result.boxes:
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    confidence = float(box.conf[0].cpu().numpy())
                    class_id = int(box.cls[0].cpu().numpy())
                    class_name = self._class_names.get(class_id, f"class_{class_id}")

                    # Get track ID if available
                    track_id = None
                    if box.id is not None:
                        track_id = int(box.id[0].cpu().numpy())

                    result.add_detection(
                        bbox=bbox,
                        class_name=class_name,
                        class_id=class_id,
                        confidence=confidence,
                        track_id=track_id
                    )

        return result
        return result
