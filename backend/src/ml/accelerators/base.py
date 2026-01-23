"""
Base classes for hardware accelerator backends.
"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from ..base import HardwareAccelerator


@dataclass
class DeviceInfo:
    """Information about a hardware device."""
    name: str
    accelerator_type: HardwareAccelerator
    memory_total_mb: int = 0
    memory_available_mb: int = 0
    compute_capability: Optional[str] = None
    driver_version: Optional[str] = None
    is_available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class AcceleratorBackend(ABC):
    """
    Abstract base class for hardware accelerator backends.

    Each backend is responsible for:
    - Detecting hardware availability
    - Providing device information
    - Optimizing models for the specific hardware
    """

    accelerator_type: HardwareAccelerator = HardwareAccelerator.CPU

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this accelerator is available on the system."""
        pass

    @abstractmethod
    def get_device_info(self) -> DeviceInfo:
        """Get information about the accelerator device."""
        pass

    @abstractmethod
    def get_device_count(self) -> int:
        """Get the number of available devices."""
        pass

    def optimize_model(
        self,
        model_path: str,
        output_path: str,
        **kwargs
    ) -> Optional[str]:
        """
        Optimize a model for this accelerator.

        Args:
            model_path: Path to the original model
            output_path: Path to save optimized model
            **kwargs: Backend-specific optimization options

        Returns:
            Path to the optimized model, or None if optimization not supported
        """
        return None  # Default: no optimization

    def setup_environment(self) -> None:
        """
        Set up any required environment variables or configurations.

        Override this in subclasses for hardware-specific setup.
        """
        pass

    def get_optimal_batch_size(self, model_size_mb: int) -> int:
        """
        Calculate optimal batch size based on available memory.

        Args:
            model_size_mb: Model size in megabytes

        Returns:
            Recommended batch size
        """
        device_info = self.get_device_info()
        available_memory = device_info.memory_available_mb

        if available_memory <= 0:
            return 1

        # Simple heuristic: reserve 30% of memory for overhead
        usable_memory = available_memory * 0.7

        # Estimate batch size (assume each image adds ~10% to model memory)
        estimated_per_image = model_size_mb * 0.1
        batch_size = max(1, int(usable_memory / (model_size_mb + estimated_per_image * 4)))

        return min(batch_size, 32)  # Cap at 32
        # Estimate batch size (assume each image adds ~10% to model memory)
        estimated_per_image = model_size_mb * 0.1
        batch_size = max(1, int(usable_memory / (model_size_mb + estimated_per_image * 4)))

        return min(batch_size, 32)  # Cap at 32
