"""Heuristic, temporal human activity recognition.

This is a rule-based classifier built on pose geometry and short-term motion
features. It deliberately reports qualitative evidence ("Strong", "Moderate",
"Weak") instead of inventing statistical confidence percentages. The rules are
interpretable but not clinically or scientifically validated.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from . import landmark_geometry as geo
from .motion_tracker import MotionFeatures

STANDING = "Standing"
SITTING = "Sitting"
WALKING = "Walking in place"
RAISING_ARM = "Raising arm"
SQUATTING = "Squatting"
BENDING = "Bending"
UNKNOWN = "Unknown"

ACTIVITY_LABELS = (STANDING, SITTING, WALKING, RAISING_ARM, SQUATTING, BENDING, UNKNOWN)

_JOINTS = {
    RAISING_ARM: (11, 12, 13, 14, 15, 16),
    BENDING: (11, 12, 23, 24),
    SQUATTING: (23, 24, 25, 26, 27, 28),
    SITTING: (23, 24, 25, 26),
    WALKING: (25, 26, 27, 28),
    STANDING: (11, 12, 23, 24),
    UNKNOWN: (),
}


@dataclass
class ActivityResult:
    label: str = UNKNOWN
    evidence: str = "None"
    detail: str = "Insufficient visibility"
    raw_label: str = UNKNOWN
    active_joints: tuple[int, ...] = ()
    stability: float = 0.0

    @property
    def is_known(self) -> bool:
        return self.label != UNKNOWN


@dataclass
class _Vote:
    label: str
    score: float
    timestamp: float


@dataclass
class _RawClassification:
    label: str
    score: float
    detail: str


class ActivityRecognizer:
    """Classifies activities with hysteresis over a rolling time window."""

    def __init__(
        self,
        smoothing_window: float = 0.9,
        switch_hold: float = 0.45,
        visibility_threshold: float = 0.5,
    ) -> None:
        self.smoothing_window = float(smoothing_window)
        self.switch_hold = float(switch_hold)
        self.visibility_threshold = float(visibility_threshold)
        self._votes: deque[_Vote] = deque(maxlen=120)
        self._label = UNKNOWN
        self._evidence = "None"
        self._detail = "Insufficient visibility"
        self._last_switch = 0.0
        self._last_body_time: float | None = None
        self._stability = 0.0

    def reset(self) -> None:
        self._votes.clear()
        self._label = UNKNOWN
        self._evidence = "None"
        self._detail = "Insufficient visibility"
        self._last_switch = 0.0
        self._last_body_time = None
        self._stability = 0.0

    # ---------------------------------------------------------------- update
    def update(
        self,
        landmarks: Optional[Sequence[Any]],
        motion: MotionFeatures,
        timestamp: float,
    ) -> ActivityResult:
        timestamp = float(timestamp)
        if not _usable(landmarks, self.visibility_threshold):
            if self._last_body_time is None or timestamp - self._last_body_time > 0.35:
                self._label = UNKNOWN
                self._evidence = "None"
                self._detail = "No body detected or insufficient landmark visibility"
            return self._snapshot(UNKNOWN)

        self._last_body_time = timestamp
        raw = self._classify(landmarks, motion)
        self._votes.append(_Vote(raw.label, raw.score, timestamp))
        while self._votes and timestamp - self._votes[0].timestamp > self.smoothing_window:
            self._votes.popleft()

        self._apply_smoothing(raw, timestamp)
        return self._snapshot(raw.label)

    # ----------------------------------------------------------------- rules
    def _classify(
        self, landmarks: Sequence[Any], motion: MotionFeatures
    ) -> _RawClassification:
        knee = geo.knee_angle(landmarks)
        inclination = geo.torso_inclination(landmarks)
        leg_ratio = geo.leg_vertical_ratio(landmarks)
        shoulder = geo.shoulder_center(landmarks)
        nose = geo.landmark(landmarks, geo.NOSE)
        left_wrist = geo.landmark(landmarks, geo.LEFT_WRIST)
        right_wrist = geo.landmark(landmarks, geo.RIGHT_WRIST)
        left_shoulder = geo.landmark(landmarks, geo.LEFT_SHOULDER)
        right_shoulder = geo.landmark(landmarks, geo.RIGHT_SHOULDER)
        spread = geo.ankle_spread(landmarks)

        wrists_up = 0
        if left_wrist is not None and left_shoulder is not None:
            if float(left_wrist.y) < float(left_shoulder.y) - 0.02:
                wrists_up += 1
        if right_wrist is not None and right_shoulder is not None:
            if float(right_wrist.y) < float(right_shoulder.y) - 0.02:
                wrists_up += 1

        # Deep torso lean, or the head has dropped below shoulder level.
        if inclination is not None and inclination >= 48:
            score = min(1.0, 0.55 + (inclination - 48) / 60)
            return _RawClassification(BENDING, score, f"Torso leaning {inclination:.0f} degrees")
        if nose is not None and shoulder is not None and float(nose.y) > shoulder[1] + 0.02:
            return _RawClassification(BENDING, 0.8, "Head below shoulder level")

        # Arms raised overhead (but not clearly a jumping jack stance).
        if wrists_up >= 1:
            both = wrists_up == 2
            arms_open = spread is not None and spread > 0.8
            if not (both and arms_open and motion.ankle_lift_range > 0.1):
                score = 0.62 + (0.18 if both else 0.0)
                detail = "Both arms raised" if both else "One arm raised"
                return _RawClassification(RAISING_ARM, score, detail)

        # Deep, upright knee bend: squat. A held squat is intentionally treated
        # as squatting while a shallow bend is split between sitting/standing.
        if knee is not None and inclination is not None:
            if knee < 100 and inclination < 42:
                score = min(1.0, 0.65 + (110 - knee) / 120)
                return _RawClassification(SQUATTING, score, f"Deep knee bend ({knee:.0f} degrees)")
            if (
                knee < 115
                and leg_ratio is not None
                and leg_ratio < 1.2
                and inclination < 38
                and (motion.hip_vertical_range > 0.08 or motion.knee_angle_range > 15)
            ):
                score = 0.62 + min(0.2, abs(motion.hip_vertical_speed) / 4)
                return _RawClassification(SQUATTING, score, "Hips lowered with bent knees")

        # Alternating ankle motion = walking/marching in place.
        if motion.is_walking_like and (inclination is None or inclination < 32):
            score = min(1.0, 0.55 + motion.ankle_alternation_hz / 8)
            return _RawClassification(WALKING, score, "Alternating leg movement detected")

        # Seated: moderate knee flexion and a compressed hip-to-ankle span.
        if knee is not None and 78 <= knee < 138:
            torso_ok = inclination is None or inclination < 36
            compressed = leg_ratio is not None and leg_ratio < 1.9
            if torso_ok and compressed and not motion.is_walking_like:
                score = 0.55 + (0.2 if leg_ratio is not None and leg_ratio < 1.55 else 0.0)
                return _RawClassification(SITTING, score, "Knees bent, hips lowered and stable")

        # Upright standing.
        if inclination is not None and inclination < 22:
            straight_legs = knee is None or knee > 148
            if straight_legs:
                score = 0.86 if (knee is not None and knee > 160) else 0.72
                return _RawClassification(STANDING, score, "Upright torso, extended legs")
            if knee >= 138:
                return _RawClassification(STANDING, score=0.55, detail="Partially bent knees")
            return _RawClassification(UNKNOWN, 0.2, "Pose between common activity patterns")

        return _RawClassification(UNKNOWN, 0.15, "Insufficient evidence for a known activity")

    # -------------------------------------------------------------- smoothing
    def _apply_smoothing(self, raw: _RawClassification, timestamp: float) -> None:
        if not self._votes:
            return
        counts: dict[str, int] = {}
        score_sums: dict[str, float] = {}
        for vote in self._votes:
            counts[vote.label] = counts.get(vote.label, 0) + 1
            score_sums[vote.label] = score_sums.get(vote.label, 0.0) + vote.score
        total = len(self._votes)

        if total < 3:
            if self._label == UNKNOWN:
                self._label = raw.label
                self._evidence = "Weak" if raw.label != UNKNOWN else "None"
                self._detail = raw.detail
            return

        dominant = max(counts, key=lambda label: (counts[label], score_sums[label]))
        share = counts[dominant] / total
        stability = share
        can_switch = timestamp - self._last_switch >= self.switch_hold

        should_switch = (
            dominant != self._label
            and share >= 0.6
            and counts[dominant] >= 3
            and can_switch
        )
        if self._label == UNKNOWN:
            should_switch = share >= 0.5 and counts[dominant] >= 2 and can_switch

        if should_switch:
            self._label = dominant
            self._last_switch = timestamp

        if dominant == self._label:
            self._detail = raw.detail if raw.label == self._label else self._detail
            if self._evidence == "None":
                self._evidence = "Weak"
        if share >= 0.82 and score_sums[dominant] / max(counts[dominant], 1) >= 0.7:
            self._evidence = "Strong"
        elif share >= 0.62:
            self._evidence = "Moderate"
        elif share >= 0.45:
            self._evidence = "Weak"

        if self._label == UNKNOWN:
            self._evidence = "None"
        self._stability = stability

    def _snapshot(self, raw_label: str) -> ActivityResult:
        return ActivityResult(
            label=self._label,
            evidence=self._evidence,
            detail=self._detail,
            raw_label=raw_label,
            active_joints=_JOINTS.get(self._label, ()),
            stability=getattr(self, "_stability", 0.0),
        )


def _usable(landmarks: Optional[Sequence[Any]], threshold: float) -> bool:
    if landmarks is None or len(landmarks) < 29:
        return False
    core = (11, 12, 23, 24, 25, 26)
    visible = sum(1 for index in core if geo.is_visible(geo.landmark(landmarks, index), threshold))
    return visible >= 4
