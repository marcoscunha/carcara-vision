"""
Vision Language Model (VLM) Engine - Support for multimodal AI models.

Supports:
- Local models via Ollama (LLaVA, Llama 3.2 Vision, etc.)
- Cloud APIs (OpenAI GPT-4V, Claude, etc.)
- Custom VLM implementations
"""

import base64
import logging
import time
from abc import abstractmethod
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


class VLMEngine(BaseInferenceEngine):
    """
    Abstract base class for Vision Language Model engines.

    VLMs can analyze images and provide natural language descriptions,
    answer questions about visual content, and perform complex reasoning.
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)

        # Default prompt for object detection tasks
        if not config.vlm_prompt:
            config.vlm_prompt = (
                "Analyze this image and list all objects you can see. "
                "For each object, provide: name, approximate location "
                "(top-left, center, bottom-right, etc.), and confidence level "
                "(high, medium, low). Format as a structured list."
            )

    def get_supported_accelerators(self) -> List[HardwareAccelerator]:
        """VLMs typically run on CPU or CUDA."""
        return [
            HardwareAccelerator.CPU,
            HardwareAccelerator.CUDA,
        ]

    @abstractmethod
    def query(
        self,
        image: np.ndarray,
        prompt: str,
        **kwargs
    ) -> str:
        """
        Query the VLM with an image and prompt.

        Args:
            image: Input image
            prompt: Text prompt/question
            **kwargs: Additional parameters

        Returns:
            Text response from the model
        """
        pass

    def infer(
        self,
        image: np.ndarray,
        prompt: Optional[str] = None,
        **kwargs
    ) -> InferenceResult:
        """
        Run VLM inference on an image.

        Args:
            image: Input image (BGR, HWC format)
            prompt: Custom prompt (uses config default if None)
            **kwargs: Additional parameters

        Returns:
            InferenceResult with text_response
        """
        if not self._is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        start_time = time.perf_counter()

        # Use provided prompt or default
        query_prompt = prompt or self.config.vlm_prompt

        # Query the model
        response = self.query(image, query_prompt, **kwargs)

        inference_time = (time.perf_counter() - start_time) * 1000

        result = InferenceResult(
            model_name=self.config.model_name,
            inference_time_ms=inference_time,
            hardware_used=self._current_accelerator or HardwareAccelerator.CPU,
            text_response=response,
        )

        # Try to parse structured detections from response
        detections = self._parse_detections(response)
        for det in detections:
            result.add_detection(**det)

        return result

    def _parse_detections(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse object detections from VLM response.

        Override this for model-specific parsing.
        """
        # Basic parsing - can be enhanced with structured output
        detections = []

        # This is a simple heuristic parser
        # For production, use structured prompts or JSON mode

        return detections

    def _encode_image_base64(self, image: np.ndarray) -> str:
        """Encode image to base64 string."""
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Encode as JPEG
        _, buffer = cv2.imencode(".jpg", rgb_image)

        # Convert to base64
        return base64.b64encode(buffer).decode("utf-8")


class OllamaVLMEngine(VLMEngine):
    """
    VLM engine using Ollama for local model inference.

    Supports models like:
    - llava (LLaVA)
    - llama3.2-vision
    - bakllava
    - moondream
    """

    def __init__(
        self,
        config: ModelConfig,
        ollama_host: str = "http://localhost:11434"
    ):
        super().__init__(config)
        self.ollama_host = ollama_host
        self._client = None

    def load(self) -> bool:
        """Initialize Ollama client and pull model if needed."""
        try:
            import ollama

            self._client = ollama.Client(host=self.ollama_host)

            # Check if model exists, pull if not
            try:
                self._client.show(self.config.model_name)
                logger.info(f"Model {self.config.model_name} found")
            except Exception:
                logger.info(f"Pulling model {self.config.model_name}...")
                self._client.pull(self.config.model_name)

            self._is_loaded = True
            self._current_accelerator = HardwareAccelerator.CPU  # Ollama manages device

            logger.info(f"Ollama VLM loaded: {self.config.model_name}")
            return True

        except ImportError:
            logger.error("ollama package not installed. Run: pip install ollama")
            return False
        except Exception as e:
            logger.error(f"Failed to load Ollama VLM: {e}")
            return False

    def unload(self) -> None:
        """Release Ollama resources."""
        self._client = None
        self._is_loaded = False
        logger.info("Ollama VLM unloaded")

    def query(
        self,
        image: np.ndarray,
        prompt: str,
        stream: bool = False,
        **kwargs
    ) -> str:
        """
        Query Ollama VLM with image and prompt.

        Args:
            image: Input image
            prompt: Text prompt
            stream: Enable streaming response
            **kwargs: Additional Ollama options

        Returns:
            Model response text
        """
        if not self._is_loaded or self._client is None:
            raise RuntimeError("Model not loaded")

        # Encode image
        image_b64 = self._encode_image_base64(image)

        # Build message
        messages = [
            {
                "role": "user",
                "content": prompt,
                "images": [image_b64]
            }
        ]

        # Query model
        response = self._client.chat(
            model=self.config.model_name,
            messages=messages,
            options={
                "temperature": self.config.vlm_temperature,
                "num_predict": self.config.vlm_max_tokens,
            },
            **kwargs
        )

        return response["message"]["content"]

    def list_available_models(self) -> List[str]:
        """List available Ollama models."""
        if not self._client:
            return []

        try:
            models = self._client.list()
            return [m["name"] for m in models.get("models", [])]
        except Exception:
            return []


class OpenAIVLMEngine(VLMEngine):
    """
    VLM engine using OpenAI API (GPT-4V, GPT-4o).

    Requires OPENAI_API_KEY environment variable.
    """

    def __init__(
        self,
        config: ModelConfig,
        api_key: Optional[str] = None
    ):
        super().__init__(config)
        self.api_key = api_key
        self._client = None

    def load(self) -> bool:
        """Initialize OpenAI client."""
        try:
            import os

            from openai import OpenAI

            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY not set")
                return False

            self._client = OpenAI(api_key=api_key)
            self._is_loaded = True
            self._current_accelerator = HardwareAccelerator.CPU  # Cloud API

            logger.info(f"OpenAI VLM loaded: {self.config.model_name}")
            return True

        except ImportError:
            logger.error("openai package not installed. Run: pip install openai")
            return False
        except Exception as e:
            logger.error(f"Failed to load OpenAI VLM: {e}")
            return False

    def unload(self) -> None:
        """Release OpenAI client."""
        self._client = None
        self._is_loaded = False
        logger.info("OpenAI VLM unloaded")

    def query(
        self,
        image: np.ndarray,
        prompt: str,
        detail: str = "auto",
        **kwargs
    ) -> str:
        """
        Query OpenAI VLM with image and prompt.

        Args:
            image: Input image
            prompt: Text prompt
            detail: Image detail level ("low", "high", "auto")
            **kwargs: Additional options

        Returns:
            Model response text
        """
        if not self._is_loaded or self._client is None:
            raise RuntimeError("Model not loaded")

        # Encode image
        image_b64 = self._encode_image_base64(image)

        # Build message
        response = self._client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                                "detail": detail
                            }
                        }
                    ]
                }
            ],
            max_tokens=self.config.vlm_max_tokens,
            temperature=self.config.vlm_temperature,
            **kwargs
        )

        return response.choices[0].message.content


class LocalVLMEngine(VLMEngine):
    """
    VLM engine for local transformers-based models.

    Supports HuggingFace models like:
    - llava-hf/llava-v1.6-mistral-7b-hf
    - microsoft/Florence-2-large
    - Qwen/Qwen2-VL-7B-Instruct
    """

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._processor = None

    def load(self) -> bool:
        """Load local VLM using transformers."""
        try:
            import torch
            from transformers import AutoModelForVision2Seq
            from transformers import AutoProcessor

            device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info(f"Loading local VLM: {self.config.model_path}")

            self._processor = AutoProcessor.from_pretrained(self.config.model_path)
            self._model = AutoModelForVision2Seq.from_pretrained(
                self.config.model_path,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None,
            )

            if device == "cpu":
                self._model = self._model.to(device)

            self._is_loaded = True
            self._current_accelerator = (
                HardwareAccelerator.CUDA if device == "cuda"
                else HardwareAccelerator.CPU
            )

            logger.info(f"Local VLM loaded on {device}")
            return True

        except ImportError:
            logger.error("transformers not installed. Run: pip install transformers")
            return False
        except Exception as e:
            logger.error(f"Failed to load local VLM: {e}")
            return False

    def unload(self) -> None:
        """Release model resources."""
        if self._model is not None:
            del self._model
            self._model = None

        if self._processor is not None:
            del self._processor
            self._processor = None

        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

        self._is_loaded = False
        logger.info("Local VLM unloaded")

    def query(
        self,
        image: np.ndarray,
        prompt: str,
        **kwargs
    ) -> str:
        """Query local VLM with image and prompt."""
        if not self._is_loaded:
            raise RuntimeError("Model not loaded")

        import torch
        from PIL import Image

        # Convert to PIL Image
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(rgb_image)

        # Process inputs
        inputs = self._processor(
            text=prompt,
            images=pil_image,
            return_tensors="pt"
        )

        # Move to device
        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # Generate
        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self.config.vlm_max_tokens,
                temperature=self.config.vlm_temperature,
                do_sample=self.config.vlm_temperature > 0,
            )

        # Decode
        response = self._processor.decode(outputs[0], skip_special_tokens=True)

        return response
        response = self._processor.decode(outputs[0], skip_special_tokens=True)

        return response
