"""Experimental fall detection using multiple temporal signals.

This module is a heuristic safety aid, NOT a medical device and NOT an emergency
service. It combines a rapid hip drop, a change from upright to horizontal torso
orientation, and sustained low posture. Normal sitting and bending are rejected
by requiring multiple concurrent signals, but false positives and false
negatives are expected.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from . import landmark_geometry as geo

_SENSITIVITY = {
    # name: (hip drop threshold in frame heights/s, horizontal angle, cooldown seconds)
    "Relaxed": (1.1, 52.0, 8.0),
    "Balanced": (1.6, 58.0, 10.0),
    "Strict": (2.2, 64.0, 12.0),
}


@dataclass
class FallResult:
    enabled: bool = True
    alert_active: bool = False
    new_alert: bool = False
    message: str = ""
    signals: tuple[str, ...] = ()
    torso_inclination: Optional[float] = None
    hip_y: Optional[float] = None
    rapid_drop: float = 0.0
    monitored: bool = True


@dataclass
class _Sample:
    timestamp: float
    hip_y: float
    hip_x: float
    torso: float
    scale: float


class FallDetector:
    def __init__(self, sensitivity: str = "Balanced", cooldown_seconds: float = 10.0) -> None:
        self.sensitivity = sensitivity if sensitivity in _SENSITIVITY else "Balanced"
        self.cooldown_seconds = cooldown_seconds
        self._samples: deque[_Sample] = deque(maxlen=120)
        self.active = False
        self._new_alert = False
        self._last_alert: float | None = None
        self._low_since: float | None = None
        self._alert_started: float = 0.0
        self._dismissed_at: float | None = None
        self._last_signals: tuple[str, ...] = ()
        self._last_torso: Optional[float] = None
        self._last_hip_y: Optional[float] = None
        self._last_drop: float = 0.0

    def set_sensitivity(self, sensitivity: str) -> None:
        if sensitivity in _SENSITIVITY:
            self.sensitivity = sensitivity

    def reset(self) -> None:
        self._samples.clear()
        self.active = False
        self._new_alert = False
        self._last_alert = None
        self._low_since = None
        self._dismissed_at = None
        self._last_signals = ()
        self._last_drop = 0.0

    def dismiss(self, timestamp: float) -> None:
        self.active = False
        self._dismissed_at = float(timestamp)
        self._low_since = None

    def update(
        self,
        landmarks: Optional[Sequence[Any]],
        timestamp: float,
        enabled: bool = True,
    ) -> FallResult:
        timestamp = float(timestamp)
        self._new_alert = False
        if not enabled:
            self.active = False
            self._samples.clear()
            return FallResult(
                enabled=False, alert_active=False, message="Fall detection is disabled.",
                monitored=False,
            )

        if landmarks is None or len(landmarks) < 25:
            self._samples.clear()
            return FallResult(
                enabled=True,
                alert_active=self.active,
                message="Monitoring paused - no body visible." if not self.active else self.message,
                signals=self._last_signals,
                torso_inclination=self._last_torso,
                hip_y=self._last_hip_y,
                rapid_drop=self._last_drop,
                monitored=False,
            )

        hips = geo.hip_center(landmarks)
        torso = geo.torso_inclination(landmarks)
        if hips is None or torso is None:
            return FallResult(
                enabled=True,
                alert_active=self.active,
                message="Monitoring paused - hips are not visible.",
                signals=self._last_signals,
                monitored=False,
            )

        scale = max(geo.body_scale(landmarks), 1e-4)
        self._samples.append(_Sample(timestamp, hips[1], hips[0], torso, scale))
        while self._samples and timestamp - self._samples[0].timestamp > 3.0:
            self._samples.popleft()

        drop_threshold, horizontal_threshold, cooldown = _SENSITIVITY[self.sensitivity]
        drop_speed = self._recent_drop_speed(timestamp)
        self._last_drop = drop_speed
        self._last_torso = torso
        self._last_hip_y = hips[1]

        signals: list[str] = []
        if drop_speed >= drop_threshold:
            signals.append("Rapid downward movement")

        # Upright -> horizontal transition within the recent window.
        recent_torso = [s.torso for s in self._samples if timestamp - s.timestamp <= 1.6]
        was_upright = bool(recent_torso) and min(recent_torso) < 32
        if torso >= horizontal_threshold and was_upright:
            signals.append("Torso changed from upright to horizontal")

        low_posture = hips[1] > 0.62 and torso > 45
        if low_posture:
            if self._low_since is None:
                self._low_since = timestamp
            if timestamp - self._low_since >= 0.8:
                signals.append("Sustained low posture")
        else:
            self._low_since = None

        # Require at least two independent signals and a horizontal/low body.
        strong_pose = torso >= horizontal_threshold or low_posture
        candidate = len(signals) >= 2 and strong_pose

        if candidate:
            dismissed_recently = (
                self._dismissed_at is not None and timestamp - self._dismissed_at < 4.0
            )
            cooled_down = (
                self._last_alert is None or timestamp - self._last_alert >= cooldown
            )
            if not dismissed_recently and cooled_down and not self.active:
                self.active = True
                self._new_alert = True
                self._last_alert = timestamp
                self._alert_started = timestamp
                self._last_signals = tuple(signals)

        if self.active:
            signals = list(self._last_signals) or signals

        return FallResult(
            enabled=True,
            alert_active=self.active,
            new_alert=self._new_alert,
            message=(
                "Possible fall detected. Please check on the person."
                if self.active
                else "Monitoring for falls."
            ),
            signals=tuple(signals),
            torso_inclination=round(torso, 1),
            hip_y=round(hips[1], 2),
            rapid_drop=round(drop_speed, 2),
            monitored=True,
        )

    @property
    def message(self) -> str:
        return (
            "Possible fall detected. Please check on the person."
            if self.active
            else "Monitoring for falls."
        )

    def _recent_drop_speed(self, timestamp: float) -> float:
        window = [s for s in self._samples if timestamp - s.timestamp <= 0.6]
        if len(window) < 3:
            return 0.0
        # Use the largest positive hip-y slope in a short sliding window,
        # normalized by the current body scale (positive means downward).
        best = 0.0
        for start in range(len(window) - 2):
            subset = window[start:]
            elapsed = subset[-1].timestamp - subset[0].timestamp
            if elapsed < 0.08:
                continue
            slope = (subset[-1].hip_y - subset[0].hip_y) / elapsed
            best = max(best, slope)
        return max(0.0, best)
