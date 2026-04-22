"""
SDK exception hierarchy.

Every public exception carries a human-readable ``hint`` field that tells
callers how to resolve the problem (missing dependency, wrong path, etc.).
"""

from __future__ import annotations


class InferenceSDKError(Exception):
    """Root exception for all SDK errors."""

    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.hint = hint

    def __str__(self) -> str:
        base = super().__str__()
        if self.hint:
            return f"{base}\n  Hint: {self.hint}"
        return base


class ModelNotFoundError(InferenceSDKError):
    """Raised when a model id or path cannot be resolved."""

    def __init__(self, model: str) -> None:
        super().__init__(
            f"Model '{model}' not found in the registry and is not a valid file path.",
            hint=(
                "Check that the model id is registered in ModelRegistry, or provide an absolute path to the model file."
            ),
        )


class RuntimeNotSupportedError(InferenceSDKError):
    """Raised when the requested runtime is not supported on this machine."""

    def __init__(self, runtime: str, reason: str = "") -> None:
        msg = f"Runtime '{runtime}' is not supported on this machine."
        if reason:
            msg = f"{msg} Reason: {reason}"
        super().__init__(
            msg,
            hint=(
                f"Install the required dependency for '{runtime}', "
                "use device='auto' to let the SDK pick, "
                "or choose a different runtime."
            ),
        )


class DeviceUnavailableError(InferenceSDKError):
    """Raised when the requested device (CUDA, TensorRT, …) is not available."""

    def __init__(self, device: str, reason: str = "") -> None:
        msg = f"Device '{device}' is not available."
        if reason:
            msg = f"{msg} Reason: {reason}"
        super().__init__(
            msg,
            hint=("Check CUDA drivers and toolkit installation, or set device='cpu' / device='auto' as fallback."),
        )


class ProviderInitializationError(InferenceSDKError):
    """Raised when an ORT / TensorRT provider fails to initialise."""

    def __init__(self, provider: str, reason: str = "") -> None:
        msg = f"Provider '{provider}' failed to initialise."
        if reason:
            msg = f"{msg} Reason: {reason}"
        super().__init__(
            msg,
            hint=(
                "Verify the provider library is installed and compatible with your "
                "CUDA / TensorRT version, or remove it from the provider list."
            ),
        )


class InferenceInputError(InferenceSDKError):
    """Raised when the input to a pipeline call is invalid."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            f"Invalid input: {detail}",
            hint="Pass a numpy array (HxWxC, uint8) or a list of such arrays.",
        )
