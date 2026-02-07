"""
Hardware Accelerator Backends for ML Inference.

This module provides detection and management of different hardware accelerators
including CUDA, TensorRT, Jetson Nano, Raspberry Pi, and Edge TPU devices.
"""

from .base import AcceleratorBackend
from .cpu import CPUBackend
from .cuda import CUDABackend
from .detector import HardwareDetector
from .jetson import JetsonBackend
from .raspberry import RaspberryPiBackend

__all__ = [
    "AcceleratorBackend",
    "CPUBackend",
    "CUDABackend",
    "HardwareDetector",
    "JetsonBackend",
    "RaspberryPiBackend",
]
