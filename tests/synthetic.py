"""Synthetic MediaPipe-style landmarks for deterministic tests.

The helper builds a plausible 33-point body with controllable knee/elbow angles,
torso lean, ankle spread and hip height. It is used only by the automated test
suite; no synthetic data is presented as real camera validation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable


@dataclass
class Lm:
    x: float
    y: float
    z: float = 0.0
    visibility: float = 0.99


def _joint(anchor: tuple[float, float], target: tuple[float, float], angle: float, side: int) -> tuple[float, float]:
    ax, ay = anchor
    bx, by = target
    dx, dy = bx - ax, by - ay
    distance = math.hypot(dx, dy)
    mx, my = (ax + bx) / 2.0, (ay + by) / 2.0
    if distance < 1e-9:
        return mx, my
    angle = max(5.0, min(179.5, float(angle)))
    m = (distance / 2.0) / math.tan(math.radians(angle / 2.0))
    # Perpendicular pointing mostly horizontally for a vertical limb.
    px, py = dy / distance, -dx / distance
    return mx + px * m * side, my + py * m * side


def make_pose(
    knee_angle: float = 175.0,
    elbow_angle: float = 175.0,
    lean: float = 0.0,
    hip_y: float = 0.55,
    shoulder_y: float = 0.32,
    ankle_y: float = 0.90,
    ankle_spread: float = 0.08,
    wrist_y: float | None = None,
    wrists_up: bool = False,
    head_offset: float = 0.0,
    hip_x: float = 0.5,
    visibility: float = 0.99,
    hidden: Iterable[int] = (),
    left_ankle_lift: float = 0.0,
    right_ankle_lift: float = 0.0,
) -> list[Lm]:
    points = [Lm(0.5, 0.5, 0.0, 0.0) for _ in range(33)]
    for index in range(33):
        points[index] = Lm(0.5, 0.5, 0.0, visibility)

    dy = hip_y - shoulder_y
    lean_dx = math.tan(math.radians(max(-80.0, min(80.0, lean)))) * dy
    shoulder_cx = hip_x + lean_dx
    shoulder_cy = shoulder_y

    # Head follows the shoulders so the neck/torso stays consistent.
    points[0] = Lm(shoulder_cx + head_offset, shoulder_cy - 0.10, visibility=visibility)
    points[1] = Lm(shoulder_cx + head_offset - 0.018, shoulder_cy - 0.128, visibility)
    points[2] = Lm(shoulder_cx + head_offset - 0.026, shoulder_cy - 0.124, visibility)
    points[3] = Lm(shoulder_cx + head_offset - 0.034, shoulder_cy - 0.118, visibility)
    points[4] = Lm(shoulder_cx + head_offset + 0.018, shoulder_cy - 0.128, visibility)
    points[5] = Lm(shoulder_cx + head_offset + 0.026, shoulder_cy - 0.124, visibility)
    points[6] = Lm(shoulder_cx + head_offset + 0.034, shoulder_cy - 0.118, visibility)
    points[7] = Lm(shoulder_cx + head_offset - 0.05, shoulder_cy - 0.105, visibility)
    points[8] = Lm(shoulder_cx + head_offset + 0.05, shoulder_cy - 0.105, visibility)
    points[9] = Lm(shoulder_cx + head_offset - 0.018, shoulder_cy - 0.055, visibility)
    points[10] = Lm(shoulder_cx + head_offset + 0.018, shoulder_cy - 0.055, visibility)

    left_shoulder = (shoulder_cx - 0.09, shoulder_cy)
    right_shoulder = (shoulder_cx + 0.09, shoulder_cy)
    points[11] = Lm(*left_shoulder, visibility=visibility)
    points[12] = Lm(*right_shoulder, visibility=visibility)

    if wrists_up:
        wrist_cy = wrist_y if wrist_y is not None else shoulder_cy - 0.14
    else:
        wrist_cy = wrist_y if wrist_y is not None else hip_y + 0.07

    for side, shoulder, wrist_index, elbow_index, hand_base in (
        (-1, left_shoulder, 15, 13, 17),
        (1, right_shoulder, 16, 14, 18),
    ):
        wrist = (shoulder[0] + side * 0.005, wrist_cy)
        points[wrist_index] = Lm(*wrist, visibility=visibility)
        elbow = _joint(shoulder, wrist, elbow_angle, side)
        points[elbow_index] = Lm(*elbow, visibility=visibility)
        # Hand landmarks near the wrist.
        for offset, index in enumerate((hand_base, hand_base + 2, hand_base + 4)):
            points[index] = Lm(
                wrist[0] + side * (0.012 + offset * 0.004),
                wrist[1] - 0.008,
                visibility=visibility,
            )

    left_hip = (hip_x - 0.06, hip_y)
    right_hip = (hip_x + 0.06, hip_y)
    points[23] = Lm(*left_hip, visibility=visibility)
    points[24] = Lm(*right_hip, visibility=visibility)

    for side, hip, ankle_index, knee_index, heel_index, foot_index in (
        (-1, left_hip, 27, 25, 29, 31),
        (1, right_hip, 28, 26, 30, 32),
    ):
        lift = left_ankle_lift if side < 0 else right_ankle_lift
        ankle = (hip_x + side * ankle_spread / 2.0, ankle_y - lift)
        points[ankle_index] = Lm(*ankle, visibility=visibility)
        knee = _joint(hip, ankle, knee_angle, side)
        points[knee_index] = Lm(*knee, visibility=visibility)
        points[heel_index] = Lm(ankle[0], ankle[1] + 0.025, visibility=visibility)
        points[foot_index] = Lm(ankle[0] + side * 0.015, ankle[1] + 0.04, visibility=visibility)

    for index in hidden:
        points[index] = Lm(0.0, 0.0, 0.0, 0.0)

    return points


def with_visibility(points: list[Lm], indices: Iterable[int], value: float) -> list[Lm]:
    for index in indices:
        points[index].visibility = value
    return points


STANDING = dict(knee_angle=175, elbow_angle=175, lean=0)
