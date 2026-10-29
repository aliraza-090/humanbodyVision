"""Scale-invariant temporal motion features.

Features are computed over a short rolling window so activity recognition can
distinguish static poses from motion (for example walking in place) without
depending on the camera distance or absolute pixel size.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from . import landmark_geometry as geo


@dataclass
class MotionFeatures:
    valid: bool = False
    duration: float = 0.0
    hip_vertical_speed: float = 0.0   # positive = moving down, torso units/s
    hip_vertical_range: float = 0.0
    motion_energy: float = 0.0        # torso units/s across core joints
    ankle_alternation_hz: float = 0.0
    ankle_lift_range: float = 0.0
    wrist_lift_range: float = 0.0
    torso_angle_range: float = 0.0
    knee_angle_range: float = 0.0

    @property
    def is_walking_like(self) -> bool:
        return (
            self.valid
            and 0.7 <= self.ankle_alternation_hz <= 4.5
            and self.ankle_lift_range >= 0.16
            and self.motion_energy >= 0.18
        )


class MotionTracker:
    """Stores pose samples and derives motion features."""

    def __init__(self, window_seconds: float = 1.8, max_samples: int = 90) -> None:
        self.window_seconds = float(window_seconds)
        self.max_samples = int(max_samples)
        self._samples: deque[tuple[float, list[Any]]] = deque(maxlen=max_samples)
        self._last_timestamp: float | None = None

    def reset(self) -> None:
        self._samples.clear()
        self._last_timestamp = None

    def update(
        self, landmarks: Optional[Sequence[Any]], timestamp: float
    ) -> MotionFeatures:
        if landmarks is None or len(landmarks) < 25:
            # A missing frame is a gap, not motion; drop stale samples gradually.
            self._prune(timestamp)
            return self.features()

        timestamp = float(timestamp)
        # Guard against duplicate timestamps from paused/replayed frames.
        if self._last_timestamp is not None and timestamp <= self._last_timestamp:
            timestamp = self._last_timestamp + 1e-3
        self._last_timestamp = timestamp
        self._samples.append((timestamp, list(landmarks)))
        self._prune(timestamp)
        return self.features()

    def _prune(self, now: float) -> None:
        while self._samples and now - self._samples[0][0] > self.window_seconds:
            self._samples.popleft()

    def features(self) -> MotionFeatures:
        if len(self._samples) < 4:
            return MotionFeatures()

        times = [sample[0] for sample in self._samples]
        duration = max(times[-1] - times[0], 1e-3)

        hip_y: list[float] = []
        hip_x: list[float] = []
        left_ankle_y: list[float] = []
        right_ankle_y: list[float] = []
        wrist_y: list[float] = []
        alternation: list[float] = []
        torso: list[float] = []
        knees: list[float] = []
        center_motion = 0.0

        tracked = (0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)
        previous: dict[int, tuple[float, float]] = {}
        previous_t: float | None = None

        for timestamp, points in self._samples:
            hips = geo.hip_center(points)
            scale = geo.body_scale(points)
            if hips is not None:
                hip_y.append(hips[1])
                hip_x.append(hips[0])
            left_ankle = geo.landmark(points, geo.LEFT_ANKLE)
            right_ankle = geo.landmark(points, geo.RIGHT_ANKLE)
            if left_ankle is not None:
                left_ankle_y.append(float(left_ankle.y))
            if right_ankle is not None:
                right_ankle_y.append(float(right_ankle.y))
            if left_ankle is not None and right_ankle is not None:
                alternation.append(
                    (float(left_ankle.y) - float(right_ankle.y)) / max(scale, 1e-4)
                )
            wrists = [
                geo.landmark(points, geo.LEFT_WRIST),
                geo.landmark(points, geo.RIGHT_WRIST),
            ]
            wrist_values = [float(w.y) for w in wrists if w is not None]
            if wrist_values:
                wrist_y.append(sum(wrist_values) / len(wrist_values))
            inclination = geo.torso_inclination(points)
            if inclination is not None:
                torso.append(inclination)
            knee = geo.knee_angle(points)
            if knee is not None:
                knees.append(knee)

            if previous_t is not None and timestamp > previous_t:
                dt = timestamp - previous_t
                displacement = 0.0
                count = 0
                for index in tracked:
                    point = geo.landmark(points, index)
                    if point is None or not geo.is_visible(point, 0.4):
                        continue
                    current = (float(point.x), float(point.y))
                    if index in previous:
                        old = previous[index]
                        displacement += math.hypot(current[0] - old[0], current[1] - old[1])
                        count += 1
                    previous[index] = current
                if count:
                    center_motion += (displacement / count) / scale / dt
            previous_t = timestamp

        last_scale = max(geo.body_scale(self._samples[-1][1]), 1e-4)
        hip_speed = _slope(times, hip_y) / last_scale
        ankle_lift = max(
            _range(left_ankle_y), _range(right_ankle_y)
        ) / last_scale
        alternation_hz = _zero_crossing_rate(alternation, duration)
        features = MotionFeatures(
            valid=True,
            duration=duration,
            hip_vertical_speed=hip_speed,
            hip_vertical_range=_range(hip_y) / last_scale,
            motion_energy=center_motion / max(1, len(self._samples)),
            ankle_alternation_hz=alternation_hz,
            ankle_lift_range=ankle_lift,
            wrist_lift_range=_range(wrist_y) / last_scale,
            torso_angle_range=_range(torso),
            knee_angle_range=_range(knees),
        )
        return features


def _range(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return max(values) - min(values)


def _slope(times: list[float], values: list[float]) -> float:
    """Least-squares slope of values over time (units per second)."""
    if len(values) < 2 or len(times) != len(values):
        return 0.0
    n = len(values)
    mean_t = sum(times) / n
    mean_v = sum(values) / n
    numerator = sum((t - mean_t) * (v - mean_v) for t, v in zip(times, values))
    denominator = sum((t - mean_t) ** 2 for t in times)
    if denominator <= 1e-9:
        return 0.0
    return numerator / denominator


def _zero_crossing_rate(values: list[float], duration: float) -> float:
    if len(values) < 3 or duration <= 0:
        return 0.0
    crossings = 0
    previous_sign = 0
    for value in values:
        sign = 1 if value > 0.03 else (-1 if value < -0.03 else 0)
        if sign and previous_sign and sign != previous_sign:
            crossings += 1
        if sign:
            previous_sign = sign
    return crossings / (2.0 * duration)
