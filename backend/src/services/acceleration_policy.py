"""Acceleration capability probing and mode resolution.

This module centralizes conditional activation for accelerated paths.
All selection is capability-driven and always supports graceful fallback.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

from ..ml.accelerators.detector import HardwareDetector
from ..ml.base import HardwareAccelerator

_PREPROCESS_MODES = {"auto", "cuda", "simd", "python"}
_POSTPROCESS_MODES = {"auto", "cuda", "simd", "python"}
_ANNOTATE_MODES = {"auto", "cuda", "cpu"}
_ENCODER_MODES = {"auto", "nvenc", "jetson", "v4l2", "x264"}


def _normalize_mode(value: str, allowed: set[str], default: str) -> str:
    candidate = (value or default).strip().lower()
    if candidate in allowed:
        return candidate
    return default


def _has_ffmpeg_encoder(encoder_name: str) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return False
    return encoder_name in result.stdout


@dataclass(frozen=True)
class HardwareCapabilities:
    cuda: bool
    tensorrt: bool
    jetson: bool
    raspberry_pi: bool
    coral_tpu: bool
    hailo: bool
    openvino: bool
    nvenc: bool
    v4l2_encoder: bool


@dataclass(frozen=True)
class AccelerationPolicyConfig:
    preprocess_mode: str = "auto"
    postprocess_mode: str = "auto"
    annotate_mode: str = "auto"
    encoder_mode: str = "auto"
    strict: bool = False


@dataclass(frozen=True)
class ResolvedAccelerationPolicy:
    requested_preprocess_mode: str
    requested_postprocess_mode: str
    requested_annotate_mode: str
    requested_encoder_mode: str
    strict: bool
    selected_preprocess_mode: str
    selected_postprocess_mode: str
    selected_annotate_mode: str
    selected_encoder_mode: str
    profile: str
    capabilities: HardwareCapabilities


def detect_capabilities(refresh: bool = False) -> HardwareCapabilities:
    detected = HardwareDetector.detect_all(refresh=refresh)
    is_jetson = HardwareDetector.is_jetson()
    is_rpi = HardwareDetector.is_raspberry_pi()

    has_cuda = bool(detected.get(HardwareAccelerator.CUDA, False) or detected.get(HardwareAccelerator.JETSON, False))
    has_tensorrt = bool(detected.get(HardwareAccelerator.TENSORRT, False))
    has_openvino = bool(detected.get(HardwareAccelerator.OPENVINO, False))
    has_coral = bool(detected.get(HardwareAccelerator.CORAL_TPU, False) or HardwareDetector.detect_coral_tpu())
    has_hailo = bool(detected.get(HardwareAccelerator.HAILO, False) or HardwareDetector.detect_hailo())

    # NVENC is generally exposed through NVIDIA ffmpeg encoders.
    has_nvenc = bool(has_cuda and (_has_ffmpeg_encoder("h264_nvenc") or _has_ffmpeg_encoder("hevc_nvenc")))

    # V4L2 mem2mem encoder is common on SBCs such as Raspberry Pi.
    has_v4l2_encoder = bool(
        os.path.exists("/dev/video10") or os.path.exists("/dev/video11") or _has_ffmpeg_encoder("h264_v4l2m2m")
    )

    return HardwareCapabilities(
        cuda=has_cuda,
        tensorrt=has_tensorrt,
        jetson=is_jetson,
        raspberry_pi=is_rpi,
        coral_tpu=has_coral,
        hailo=has_hailo,
        openvino=has_openvino,
        nvenc=has_nvenc,
        v4l2_encoder=has_v4l2_encoder,
    )


def _resolve_preprocess(requested: str, caps: HardwareCapabilities, strict: bool) -> str:
    if requested == "auto":
        if caps.cuda:
            return "cuda"
        return "simd"

    if requested == "cuda":
        if caps.cuda:
            return "cuda"
        if strict:
            raise ValueError("ACCEL_PREPROCESS_MODE=cuda requested but CUDA is unavailable")
        return "simd"

    if requested == "simd":
        return "simd"

    return "python"


def _resolve_postprocess(requested: str, caps: HardwareCapabilities, strict: bool) -> str:
    if requested == "auto":
        if caps.cuda:
            return "cuda"
        return "simd"

    if requested == "cuda":
        if caps.cuda:
            return "cuda"
        if strict:
            raise ValueError("ACCEL_POSTPROCESS_MODE=cuda requested but CUDA is unavailable")
        return "simd"

    if requested == "simd":
        return "simd"

    return "python"


def _resolve_annotate(requested: str, caps: HardwareCapabilities, strict: bool) -> str:
    if requested == "auto":
        return "cuda" if caps.cuda else "cpu"

    if requested == "cuda":
        if caps.cuda:
            return "cuda"
        if strict:
            raise ValueError("ACCEL_ANNOTATE_MODE=cuda requested but CUDA is unavailable")
        return "cpu"

    return "cpu"


def _resolve_encoder(requested: str, caps: HardwareCapabilities, strict: bool) -> str:
    if requested == "auto":
        if caps.nvenc:
            return "nvenc"
        if caps.jetson:
            return "jetson"
        if caps.v4l2_encoder:
            return "v4l2"
        return "x264"

    if requested == "nvenc":
        if caps.nvenc:
            return "nvenc"
        if strict:
            raise ValueError("ACCEL_ENCODER_MODE=nvenc requested but NVENC is unavailable")
        return _resolve_encoder("auto", caps, strict=False)

    if requested == "jetson":
        if caps.jetson:
            return "jetson"
        if strict:
            raise ValueError("ACCEL_ENCODER_MODE=jetson requested but Jetson encoder is unavailable")
        return _resolve_encoder("auto", caps, strict=False)

    if requested == "v4l2":
        if caps.v4l2_encoder:
            return "v4l2"
        if strict:
            raise ValueError("ACCEL_ENCODER_MODE=v4l2 requested but V4L2 encoder is unavailable")
        return "x264"

    return "x264"


def _resolve_profile(caps: HardwareCapabilities) -> str:
    if caps.jetson:
        return "jetson"
    if caps.raspberry_pi:
        return "raspberry_pi"
    if caps.cuda:
        return "nvidia"
    return "generic"


def resolve_policy(config: AccelerationPolicyConfig, refresh_capabilities: bool = False) -> ResolvedAccelerationPolicy:
    caps = detect_capabilities(refresh=refresh_capabilities)

    requested_pre = _normalize_mode(config.preprocess_mode, _PREPROCESS_MODES, "auto")
    requested_post = _normalize_mode(config.postprocess_mode, _POSTPROCESS_MODES, "auto")
    requested_ann = _normalize_mode(config.annotate_mode, _ANNOTATE_MODES, "auto")
    requested_enc = _normalize_mode(config.encoder_mode, _ENCODER_MODES, "auto")

    selected_pre = _resolve_preprocess(requested_pre, caps, config.strict)
    selected_post = _resolve_postprocess(requested_post, caps, config.strict)
    selected_ann = _resolve_annotate(requested_ann, caps, config.strict)
    selected_enc = _resolve_encoder(requested_enc, caps, config.strict)

    return ResolvedAccelerationPolicy(
        requested_preprocess_mode=requested_pre,
        requested_postprocess_mode=requested_post,
        requested_annotate_mode=requested_ann,
        requested_encoder_mode=requested_enc,
        strict=config.strict,
        selected_preprocess_mode=selected_pre,
        selected_postprocess_mode=selected_post,
        selected_annotate_mode=selected_ann,
        selected_encoder_mode=selected_enc,
        profile=_resolve_profile(caps),
        capabilities=caps,
    )
