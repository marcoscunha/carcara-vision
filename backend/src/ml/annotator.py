"""
Frame Annotator — draws YOLO results on NumPy frames with OpenCV.

Design notes:
- All methods are static; no instantiation needed.
- Each method accepts a raw detection list (plain dicts) produced by
  ObjectDetectionService / YOLOEngine, so the annotator has no coupling
  to ultralytics or any specific engine.
- Returns the annotated frame in-place (also returns it for chaining).

Detection dict shape (all task types share the bbox / class fields):
  {
      "bbox":        [x1, y1, x2, y2],       # pixel coords
      "class_name":  str,
      "class_id":    int,
      "confidence":  float,
      # Detection task only: ─────────────────
      "track_id":    int | None,              # optional ByteTrack ID
      # Pose task only: ──────────────────────
      "keypoints":   list[[x, y, conf], ...], # 17 joints (COCO format)
      # Segmentation task only: ───────────────
      "mask_polygon":list[[x, y], ...],       # polygon points
  }
"""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# COCO 17-keypoint skeleton: list of (joint_a_idx, joint_b_idx) pairs
_COCO_SKELETON: list[tuple[int, int]] = [
    (0, 1),
    (0, 2),  # nose → eyes
    (1, 3),
    (2, 4),  # eyes → ears
    (5, 6),  # shoulders
    (5, 7),
    (7, 9),  # left arm
    (6, 8),
    (8, 10),  # right arm
    (5, 11),
    (6, 12),  # torso
    (11, 12),  # hips
    (11, 13),
    (13, 15),  # left leg
    (12, 14),
    (14, 16),  # right leg
]


def _class_colour(class_id: int) -> tuple[int, int, int]:
    """Deterministic BGR colour from class ID (HSV wheel)."""
    hue = (class_id * 37) % 180  # spread hues evenly
    hsv = np.uint8([[[hue, 220, 200]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0][0]
    return int(bgr[0]), int(bgr[1]), int(bgr[2])


class FrameAnnotator:
    """
    Stateless utility class for drawing YOLO results on video frames.

    Usage::

        annotated = FrameAnnotator.draw_detections(frame, detections)
        annotated = FrameAnnotator.draw_pose(frame, detections)
        annotated = FrameAnnotator.draw_segmentation(frame, detections)
    """

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @staticmethod
    def draw_detections(
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        *,
        line_thickness: int = 2,
        font_scale: float = 0.55,
    ) -> np.ndarray:
        """
        Draw bounding boxes and labels for object-detection results.

        Supports optional ``track_id`` field — appended to the label when
        present.
        """
        for det in detections:
            x1, y1, x2, y2 = (int(v) for v in det["bbox"])
            class_id = det.get("class_id", 0)
            colour = _class_colour(class_id)

            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, line_thickness)

            label = f"{det['class_name']} {det['confidence']:.2f}"
            if det.get("track_id") is not None:
                label = f"#{det['track_id']} {label}"

            FrameAnnotator._draw_label(frame, label, (x1, y1), colour, font_scale)

        return frame

    @staticmethod
    def draw_pose(
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        *,
        kpt_radius: int = 4,
        line_thickness: int = 2,
        conf_threshold: float = 0.3,
    ) -> np.ndarray:
        """
        Draw bounding boxes + COCO 17-keypoint skeleton.

        Each detection must include a ``keypoints`` field:
        ``[[x, y, conf], ...]`` for the 17 COCO joints.
        """
        for det in detections:
            # Draw bounding box
            x1, y1, x2, y2 = (int(v) for v in det["bbox"])
            class_id = det.get("class_id", 0)
            colour = _class_colour(class_id)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, line_thickness)
            FrameAnnotator._draw_label(frame, det["class_name"], (x1, y1), colour)

            keypoints: list[list[float]] = det.get("keypoints") or []
            if not keypoints:
                continue

            # Draw joints
            kpt_coords: list[tuple[int, int] | None] = []
            for kpt in keypoints:
                if len(kpt) < 3:
                    kpt_coords.append(None)
                    continue
                kx, ky, kc = kpt[0], kpt[1], kpt[2]
                if kc < conf_threshold:
                    kpt_coords.append(None)
                    continue
                pt = (int(kx), int(ky))
                cv2.circle(frame, pt, kpt_radius, (0, 255, 0), -1)
                kpt_coords.append(pt)

            # Draw skeleton bones
            for idx_a, idx_b in _COCO_SKELETON:
                if idx_a >= len(kpt_coords) or idx_b >= len(kpt_coords):
                    continue
                pa, pb = kpt_coords[idx_a], kpt_coords[idx_b]
                if pa is not None and pb is not None:
                    cv2.line(frame, pa, pb, (0, 200, 255), line_thickness)

        return frame

    @staticmethod
    def draw_segmentation(
        frame: np.ndarray,
        detections: list[dict[str, Any]],
        *,
        alpha: float = 0.35,
        line_thickness: int = 2,
    ) -> np.ndarray:
        """
        Draw semi-transparent filled masks + bounding boxes.

        Each detection must include a ``mask_polygon`` field: a list of
        ``[x, y]`` polygon vertices in pixel coordinates.
        """
        overlay = frame.copy()

        for det in detections:
            class_id = det.get("class_id", 0)
            colour = _class_colour(class_id)

            polygon: list[list[float]] = det.get("mask_polygon") or []
            if polygon:
                pts = np.array([[int(p[0]), int(p[1])] for p in polygon], dtype=np.int32)
                cv2.fillPoly(overlay, [pts], colour)

        # Blend overlay with original
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

        # Draw bounding boxes and labels on top
        for det in detections:
            x1, y1, x2, y2 = (int(v) for v in det["bbox"])
            class_id = det.get("class_id", 0)
            colour = _class_colour(class_id)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, line_thickness)
            label = f"{det['class_name']} {det['confidence']:.2f}"
            FrameAnnotator._draw_label(frame, label, (x1, y1), colour)

        return frame

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _draw_label(
        frame: np.ndarray,
        text: str,
        origin: tuple[int, int],
        colour: tuple[int, int, int],
        font_scale: float = 0.55,
    ) -> None:
        """Draw a filled-background label above ``origin``."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 1
        (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)

        x, y = origin
        top_left = (x, max(y - th - baseline - 4, 0))
        bottom_right = (x + tw + 4, max(y, th + baseline + 4))

        # Background rectangle
        cv2.rectangle(frame, top_left, bottom_right, colour, cv2.FILLED)

        # White text on coloured background
        text_y = max(y - baseline - 2, th + 2)
        cv2.putText(frame, text, (x + 2, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
