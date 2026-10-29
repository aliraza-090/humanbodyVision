"""Geometry helpers for MediaPipe pose landmarks.

All functions accept a sequence of landmark-like objects exposing ``x``, ``y``
(optionally ``z`` and ``visibility``) in MediaPipe's normalized image space.
Pure functions keep this module easy to unit test with synthetic landmarks.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional, Sequence

import numpy as np

# MediaPipe Pose landmark indices.
NOSE = 0
LEFT_EYE_INNER = 1
LEFT_EYE = 2
LEFT_EYE_OUTER = 3
RIGHT_EYE_INNER = 4
RIGHT_EYE = 5
RIGHT_EYE_OUTER = 6
LEFT_EAR = 7
RIGHT_EAR = 8
MOUTH_LEFT = 9
MOUTH_RIGHT = 10
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_ELBOW = 13
RIGHT_ELBOW = 14
LEFT_WRIST = 15
RIGHT_WRIST = 16
LEFT_PINKY = 17
RIGHT_PINKY = 18
LEFT_INDEX = 19
RIGHT_INDEX = 20
LEFT_THUMB = 21
RIGHT_THUMB = 22
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28
LEFT_HEEL = 29
RIGHT_HEEL = 30
LEFT_FOOT_INDEX = 31
RIGHT_FOOT_INDEX = 32

LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]


def landmark(points: Optional[Sequence[Any]], index: int) -> Optional[Any]:
    """Return a landmark by index, or None when unavailable."""
    if points is None:
        return None
    try:
        return points[index]
    except (IndexError, TypeError):
        return None


def visibility(value: Any) -> float:
    """Return a safe visibility score in [0, 1]."""
    raw = getattr(value, "visibility", None)
    if raw is None:
        raw = getattr(value, "presence", None)
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


def is_visible(value: Any, threshold: float = 0.5) -> bool:
    return value is not None and visibility(value) >= threshold


def _missing(value: Any) -> bool:
    """True when a landmark is absent or is a zero-filled placeholder.

    MediaPipe may emit all-zero landmarks with zero visibility for joints it
    could not infer. A real joint at exactly (0, 0) is not useful for body
    geometry, so treating that placeholder as missing avoids bogus angles.
    """
    if value is None:
        return True
    try:
        x = float(getattr(value, "x", 0.0))
        y = float(getattr(value, "y", 0.0))
    except (TypeError, ValueError):
        return True
    return abs(x) < 1e-9 and abs(y) < 1e-9 and visibility(value) <= 0.0


def _xy_any(value: Any) -> tuple[float, float]:
    """Accept either a landmark object or a plain ``(x, y)`` tuple."""
    if isinstance(value, (tuple, list)) and len(value) >= 2:
        return float(value[0]), float(value[1])
    return xy(value)



def xy(value: Any) -> tuple[float, float]:
    return float(getattr(value, "x", 0.0)), float(getattr(value, "y", 0.0))


def point_distance(a: Any, b: Any) -> float:
    ax, ay = xy(a)
    bx, by = xy(b)
    return math.hypot(ax - bx, ay - by)


def midpoint(a: Any, b: Any) -> tuple[float, float]:
    ax, ay = xy(a)
    bx, by = xy(b)
    return (ax + bx) / 2.0, (ay + by) / 2.0


def angle_between(a: Any, b: Any, c: Any) -> Optional[float]:
    """Interior angle ABC in degrees (angle at joint ``b``)."""
    if a is None or b is None or c is None:
        return None
    ax, ay = xy(a)
    bx, by = xy(b)
    cx, cy = xy(c)
    v1 = np.array([ax - bx, ay - by], dtype=float)
    v2 = np.array([cx - bx, cy - by], dtype=float)
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 < 1e-6 or n2 < 1e-6:
        return None
    cosine = float(np.dot(v1, v2) / (n1 * n2))
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def segment_inclination(a: Any, b: Any) -> Optional[float]:
    """Angle of segment a->b relative to vertical downwards, in degrees.

    0 degrees means perfectly vertical (b directly below a), 90 means
    horizontal. The result is unsigned and clamped to 0..180.
    """
    if a is None or b is None:
        return None
    ax, ay = _xy_any(a)
    bx, by = _xy_any(b)
    dx = bx - ax
    dy = by - ay
    if math.hypot(dx, dy) < 1e-6:
        return None
    return abs(math.degrees(math.atan2(dx, dy)))


def shoulder_center(points: Optional[Sequence[Any]]) -> Optional[tuple[float, float]]:
    left = landmark(points, LEFT_SHOULDER)
    right = landmark(points, RIGHT_SHOULDER)
    if _missing(left) or _missing(right):
        return None
    return midpoint(left, right)


def hip_center(points: Optional[Sequence[Any]]) -> Optional[tuple[float, float]]:
    left = landmark(points, LEFT_HIP)
    right = landmark(points, RIGHT_HIP)
    if _missing(left) or _missing(right):
        return None
    return midpoint(left, right)


def knee_center(points: Optional[Sequence[Any]]) -> Optional[tuple[float, float]]:
    left = landmark(points, LEFT_KNEE)
    right = landmark(points, RIGHT_KNEE)
    if _missing(left) or _missing(right):
        return None
    return midpoint(left, right)


def ankle_center(points: Optional[Sequence[Any]]) -> Optional[tuple[float, float]]:
    left = landmark(points, LEFT_ANKLE)
    right = landmark(points, RIGHT_ANKLE)
    if _missing(left) or _missing(right):
        return None
    return midpoint(left, right)


def torso_vector(points: Optional[Sequence[Any]]) -> Optional[tuple[float, float]]:
    shoulders = shoulder_center(points)
    hips = hip_center(points)
    if shoulders is None or hips is None:
        return None
    return hips[0] - shoulders[0], hips[1] - shoulders[1]


def torso_length(points: Optional[Sequence[Any]]) -> float:
    """Shoulder-to-hip distance, used as a scale-invariant body unit."""
    vector = torso_vector(points)
    if vector is None:
        return 1.0
    length = math.hypot(*vector)
    return max(length, 1e-4)


def body_scale(points: Optional[Sequence[Any]]) -> float:
    """Robust body scale in normalized image units."""
    length = torso_length(points)
    if length > 0.02:
        return length
    left = landmark(points, LEFT_SHOULDER)
    right = landmark(points, RIGHT_SHOULDER)
    if left is not None and right is not None:
        return max(point_distance(left, right), 1e-4)
    return 1.0


def shoulder_tilt(points: Optional[Sequence[Any]]) -> Optional[float]:
    """Absolute shoulder-line tilt from horizontal in degrees."""
    left = landmark(points, LEFT_SHOULDER)
    right = landmark(points, RIGHT_SHOULDER)
    if _missing(left) or _missing(right):
        return None
    dx = float(right.x) - float(left.x)
    dy = float(right.y) - float(left.y)
    if math.hypot(dx, dy) < 1e-6:
        return None
    return abs(math.degrees(math.atan2(dy, dx)))


def torso_inclination(points: Optional[Sequence[Any]]) -> Optional[float]:
    """Torso inclination from vertical using the shoulder->hip axis."""
    shoulders = shoulder_center(points)
    hips = hip_center(points)
    if shoulders is None or hips is None:
        return None
    return segment_inclination(shoulders, hips)


def head_offset(points: Optional[Sequence[Any]]) -> Optional[float]:
    """Horizontal nose offset from the shoulder centre, in torso units."""
    nose = landmark(points, NOSE)
    shoulders = shoulder_center(points)
    if _missing(nose) or shoulders is None:
        return None
    dx = float(nose.x) - shoulders[0]
    return dx / body_scale(points)


def joint_angle(
    points: Optional[Sequence[Any]], upper: int, joint: int, lower: int
) -> Optional[float]:
    a = landmark(points, upper)
    b = landmark(points, joint)
    c = landmark(points, lower)
    if _missing(a) or _missing(b) or _missing(c):
        return None
    return angle_between(a, b, c)


def knee_angle(points: Optional[Sequence[Any]], side: str = "average") -> Optional[float]:
    values: list[float] = []
    if side in {"left", "average"}:
        value = joint_angle(points, LEFT_HIP, LEFT_KNEE, LEFT_ANKLE)
        if value is not None:
            values.append(value)
    if side in {"right", "average"}:
        value = joint_angle(points, RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE)
        if value is not None:
            values.append(value)
    return sum(values) / len(values) if values else None


def elbow_angle(points: Optional[Sequence[Any]], side: str = "right") -> Optional[float]:
    if side == "left":
        return joint_angle(points, LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST)
    return joint_angle(points, RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST)


def hip_angle(points: Optional[Sequence[Any]], side: str = "average") -> Optional[float]:
    """Angle at the hip between torso and thigh (180 = straight)."""
    values: list[float] = []
    shoulder = landmark(points, LEFT_SHOULDER)
    hip = landmark(points, LEFT_HIP)
    knee = landmark(points, LEFT_KNEE)
    if side in {"left", "average"}:
        value = angle_between(shoulder, hip, knee)
        if value is not None:
            values.append(value)
    if side in {"right", "average"}:
        value = angle_between(
            landmark(points, RIGHT_SHOULDER),
            landmark(points, RIGHT_HIP),
            landmark(points, RIGHT_KNEE),
        )
        if value is not None:
            values.append(value)
    return sum(values) / len(values) if values else None


def leg_vertical_ratio(points: Optional[Sequence[Any]]) -> Optional[float]:
    """Vertical hip-to-ankle distance in torso units (small when crouched)."""
    hips = hip_center(points)
    ankles = ankle_center(points)
    if hips is None or ankles is None:
        return None
    return (ankles[1] - hips[1]) / body_scale(points)


def ankle_spread(points: Optional[Sequence[Any]]) -> Optional[float]:
    """Horizontal distance between ankles in torso units."""
    left = landmark(points, LEFT_ANKLE)
    right = landmark(points, RIGHT_ANKLE)
    if _missing(left) or _missing(right):
        return None
    return abs(float(left.x) - float(right.x)) / body_scale(points)


def wrist_above_shoulder(
    points: Optional[Sequence[Any]], side: str = "average", margin: float = 0.02
) -> Optional[bool]:
    shoulder = landmark(points, LEFT_SHOULDER if side == "left" else RIGHT_SHOULDER)
    wrist = landmark(points, LEFT_WRIST if side == "left" else RIGHT_WRIST)
    if _missing(shoulder) or _missing(wrist):
        return None
    return float(wrist.y) < float(shoulder.y) - margin


def mean_visible_confidence(points: Optional[Sequence[Any]], indices: Iterable[int]) -> float:
    values = [visibility(landmark(points, i)) for i in indices]
    values = [v for v in values if v > 0]
    return sum(values) / len(values) if values else 0.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
