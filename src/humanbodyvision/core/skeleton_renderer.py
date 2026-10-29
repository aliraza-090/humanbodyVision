"""Green skeleton rendering on top of the live camera image.

Landmarks arrive in MediaPipe normalized coordinates for the un-mirrored frame.
When the preview is mirrored, x coordinates are mapped so the skeleton aligns
with the user's real body on screen. Only connections whose endpoints are both
sufficiently visible are drawn, preventing misleading "ghost" limbs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Sequence

import cv2
import numpy as np

# Standard MediaPipe Pose connections (no face mesh, no duplicate edges).
POSE_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 7),
    (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10),
    (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (12, 14), (14, 16), (16, 18), (16, 20), (16, 22),
    (11, 23), (12, 24), (23, 24),
    (23, 25), (25, 27), (27, 29), (29, 31),
    (24, 26), (26, 28), (28, 30), (30, 32),
    (27, 31), (28, 32),
)

HEAD_JOINTS = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}
UPPER_BODY_JOINTS = {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22}
LOWER_BODY_JOINTS = {23, 24, 25, 26, 27, 28, 29, 30, 31, 32}
KEY_JOINTS = {11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28}

COLOR_GREEN = (0, 255, 0)
COLOR_CYAN = (255, 255, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_ORANGE = (0, 165, 255)
COLOR_RED = (0, 0, 255)
COLOR_WHITE = (245, 245, 245)
COLOR_DARK = (22, 24, 30)


@dataclass
class SkeletonStyle:
    line_thickness: int = 3
    dot_size: int = 4
    visibility_threshold: float = 0.5
    visible: bool = True
    line_color: tuple[int, int, int] = COLOR_GREEN
    joint_color: tuple[int, int, int] = COLOR_CYAN
    active_color: tuple[int, int, int] = COLOR_YELLOW
    warning_color: tuple[int, int, int] = COLOR_RED
    highlight_active: bool = True


def _visibility(point: Any) -> float:
    value = getattr(point, "visibility", None)
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _pixel(point: Any, width: int, height: int, mirror: bool) -> tuple[int, int]:
    x = float(getattr(point, "x", 0.0))
    y = float(getattr(point, "y", 0.0))
    if mirror:
        x = 1.0 - x
    return int(round(x * width)), int(round(y * height))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def draw_skeleton(
    frame: np.ndarray,
    landmarks: Optional[Sequence[Any]],
    style: Optional[SkeletonStyle] = None,
    mirror: bool = True,
    active_joints: Iterable[int] | None = None,
    warning_joints: Iterable[int] | None = None,
) -> np.ndarray:
    """Draw the skeleton onto ``frame`` in place and return it."""
    if frame is None or landmarks is None:
        return frame
    style = style or SkeletonStyle()
    if not style.visible:
        return frame

    height, width = frame.shape[:2]
    active = set(active_joints or ())
    warning = set(warning_joints or ())
    threshold = _clamp01(style.visibility_threshold)

    # Lines first, then joints, so circles sit cleanly on top of the bones.
    for start_index, end_index in POSE_CONNECTIONS:
        if start_index >= len(landmarks) or end_index >= len(landmarks):
            continue
        start = landmarks[start_index]
        end = landmarks[end_index]
        if _visibility(start) < threshold or _visibility(end) < threshold:
            continue
        p1 = _pixel(start, width, height, mirror)
        p2 = _pixel(end, width, height, mirror)
        if not _inside(p1, width, height) or not _inside(p2, width, height):
            continue
        cv2.line(frame, p1, p2, style.line_color, style.line_thickness, cv2.LINE_AA)

    for index, point in enumerate(landmarks):
        if _visibility(point) < threshold:
            continue
        center = _pixel(point, width, height, mirror)
        if not _inside(center, width, height):
            continue

        radius = max(2, style.dot_size + (1 if index in KEY_JOINTS else 0))
        color = style.joint_color
        if style.highlight_active and index in active:
            color = style.active_color
            radius += 2
        if index in warning:
            color = style.warning_color
            radius += 2

        cv2.circle(frame, center, radius + 1, COLOR_DARK, -1, cv2.LINE_AA)
        cv2.circle(frame, center, radius, color, -1, cv2.LINE_AA)
        if index in KEY_JOINTS or index in active:
            cv2.circle(frame, center, radius + 3, color, 1, cv2.LINE_AA)

    return frame


def _inside(point: tuple[int, int], width: int, height: int) -> bool:
    return -50 <= point[0] <= width + 50 and -50 <= point[1] <= height + 50


def _text_with_background(
    frame: np.ndarray,
    text: str,
    origin: tuple[int, int],
    scale: float,
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    if not text:
        return
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thickness)
    x, y = origin
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (x - 6, y - text_h - 6),
        (x + text_w + 6, y + baseline + 6),
        COLOR_DARK,
        -1,
    )
    cv2.addWeighted(overlay, 0.62, frame, 0.38, 0, frame)
    cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def draw_hud(
    frame: np.ndarray,
    activity: str | None = None,
    fps: float | None = None,
    detected: bool = False,
    status: str | None = None,
    secondary: str | None = None,
    warning: str | None = None,
) -> np.ndarray:
    """Draw compact, readable status text over the preview."""
    if frame is None or frame.size == 0:
        return frame
    height, width = frame.shape[:2]
    scale = max(0.45, min(0.72, width / 1100))
    thickness = 1 if width < 1000 else 2
    margin = max(8, int(width * 0.014))

    if activity:
        _text_with_background(
            frame, activity, (margin, margin + int(24 * scale)),
            scale, COLOR_WHITE, thickness,
        )
    if fps is not None:
        text = f"{fps:4.1f} FPS"
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_w, _), _ = cv2.getTextSize(text, font, scale, thickness)
        _text_with_background(
            frame, text, (width - margin - text_w, margin + int(24 * scale)),
            scale, COLOR_GREEN if fps >= 20 else COLOR_ORANGE, thickness,
        )
    if not detected:
        text = "No body detected - step into view"
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_w, _), _ = cv2.getTextSize(text, font, scale, thickness)
        _text_with_background(
            frame, text, ((width - text_w) // 2, height - margin),
            scale, COLOR_ORANGE, thickness,
        )
    if warning:
        _text_with_background(
            frame, warning, (margin, height - margin), scale, COLOR_RED, thickness
        )
    elif secondary:
        _text_with_background(
            frame, secondary, (margin, height - margin), scale, COLOR_WHITE, thickness
        )
    if status:
        font = cv2.FONT_HERSHEY_SIMPLEX
        (text_w, _), _ = cv2.getTextSize(status, font, scale, thickness)
        _text_with_background(
            frame, status, ((width - text_w) // 2, margin + int(24 * scale)),
            scale, COLOR_CYAN, thickness,
        )
    return frame


def render_placeholder(
    width: int = 1280,
    height: int = 720,
    message: str = "Camera stopped",
    detail: str | None = None,
) -> np.ndarray:
    """Create a dark placeholder image for the stopped/error camera state."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (18, 20, 26)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = max(0.7, width / 1200)
    (text_w, text_h), baseline = cv2.getTextSize(message, font, scale, 2)
    cv2.putText(
        frame, message,
        ((width - text_w) // 2, (height + text_h) // 2),
        font, scale, COLOR_WHITE, 2, cv2.LINE_AA,
    )
    if detail:
        detail_scale = scale * 0.62
        (detail_w, detail_h), _ = cv2.getTextSize(detail, font, detail_scale, 1)
        cv2.putText(
            frame, detail,
            ((width - detail_w) // 2, (height + text_h) // 2 + baseline + int(30 * scale)),
            font, detail_scale, (170, 176, 190), 1, cv2.LINE_AA,
        )
    return frame
