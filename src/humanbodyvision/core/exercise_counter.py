"""State-machine based exercise repetition counting.

Counters consume joint angles extracted from pose landmarks. Repetitions are
only counted after the full required range of motion has been reached and the
counter has returned to its start position, which rejects most partial reps.
These are fitness aids, not clinically validated movement assessments.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field, replace
from typing import Any, Optional, Sequence

from . import landmark_geometry as geo
from ..config.defaults import EXERCISES

SQUATS = "Squats"
BICEP_CURLS = "Bicep Curls"
JUMPING_JACKS = "Jumping Jacks"


@dataclass
class ExerciseState:
    exercise: str = SQUATS
    running: bool = False
    reps: int = 0
    phase: str = "Ready"
    angle: Optional[float] = None
    feedback: str = "Press Start to begin"
    elapsed: float = 0.0
    completed_rep: bool = False
    active_joints: tuple[int, ...] = ()
    visibility_warning: str | None = None

    def with_session(self, running: bool, elapsed: float) -> "ExerciseState":
        return replace(self, running=running, elapsed=elapsed)


_THRESHOLDS = {
    "Squats": {
        "Relaxed": (118.0, 152.0),
        "Balanced": (108.0, 160.0),
        "Strict": (95.0, 168.0),
    },
    "Bicep Curls": {
        "Relaxed": (58.0, 142.0),
        "Balanced": (50.0, 152.0),
        "Strict": (42.0, 162.0),
    },
    "Jumping Jacks": {
        "Relaxed": (0.75, 0.55),
        "Balanced": (0.9, 0.45),
        "Strict": (1.0, 0.38),
    },
}


class BaseCounter:
    name = ""
    active_joints: tuple[int, ...] = ()

    def __init__(self, sensitivity: str = "Balanced") -> None:
        self.sensitivity = sensitivity if sensitivity in ("Relaxed", "Balanced", "Strict") else "Balanced"
        self.reps = 0
        self.phase = "Ready"
        self.feedback = "Press Start to begin"
        self._completed = False
        self._last_rep_time: float | None = None
        self._phase_started = 0.0
        self.min_rep_seconds = 0.45

    def reset(self) -> None:
        self.reps = 0
        self.phase = "Ready"
        self.feedback = "Press Start to begin"
        self._completed = False
        self._last_rep_time = None
        self._phase_started = 0.0

    def _set_phase(self, phase: str, timestamp: float) -> None:
        if phase != self.phase:
            self.phase = phase
            self._phase_started = timestamp

    def _count_rep(self, timestamp: float) -> bool:
        if self._last_rep_time is not None and timestamp - self._last_rep_time < self.min_rep_seconds:
            return False
        self.reps += 1
        self._last_rep_time = timestamp
        self._completed = True
        return True

    def _state(self, angle: Optional[float], warning: str | None = None) -> ExerciseState:
        return ExerciseState(
            exercise=self.name,
            reps=self.reps,
            phase=self.phase,
            angle=angle,
            feedback=self.feedback,
            completed_rep=self._completed,
            active_joints=self.active_joints,
            visibility_warning=warning,
        )


class SquatCounter(BaseCounter):
    name = SQUATS
    active_joints = (23, 24, 25, 26, 27, 28)

    def __init__(self, sensitivity: str = "Balanced") -> None:
        super().__init__(sensitivity)
        self._bottom_time: float | None = None

    def reset(self) -> None:
        super().reset()
        self._bottom_time = None

    def update(self, landmarks: Optional[Sequence[Any]], timestamp: float) -> ExerciseState:
        self._completed = False
        angle = geo.knee_angle(landmarks)
        if angle is None:
            self.feedback = "Knees are not visible - step back until your legs are in frame"
            return self._state(None, "Knees not visible")
        down, up = _THRESHOLDS[SQUATS][self.sensitivity]

        if self.phase in {"Ready", "Descending"}:
            if angle <= down:
                self._set_phase("Bottom", timestamp)
                self._bottom_time = timestamp
                self.feedback = "Good depth - now stand up to complete the rep"
            elif angle < up - 12:
                if self.phase != "Descending":
                    self._set_phase("Descending", timestamp)
                self.feedback = "Lower down until your knees are bent"
            else:
                self._set_phase("Ready", timestamp)
                self.feedback = "Stand tall, then lower for the next rep"
        elif self.phase == "Bottom":
            if angle >= up:
                # A quick return from the bottom straight to standing can skip
                # the intermediate "Ascending" sample; count it if the bottom
                # position was actually held.
                held = (
                    self._bottom_time is not None
                    and timestamp - self._bottom_time >= 0.12
                )
                if held and self._count_rep(timestamp):
                    self.feedback = "Rep counted - keep your knees tracking over your toes"
                else:
                    self.feedback = "Stand tall, then lower for the next rep"
                self._set_phase("Ready", timestamp)
                self._bottom_time = None
            elif angle > down + 8:
                self._set_phase("Ascending", timestamp)
                self.feedback = "Drive up through your heels"
            else:
                self.feedback = "Hold the bottom position briefly"
        elif self.phase == "Ascending":
            if angle >= up:
                held = (
                    self._bottom_time is not None
                    and timestamp - self._bottom_time >= 0.12
                )
                if held and self._count_rep(timestamp):
                    self.feedback = "Rep counted - keep your knees tracking over your toes"
                else:
                    self.feedback = "Stand tall, then lower for the next rep"
                self._set_phase("Ready", timestamp)
                self._bottom_time = None
            elif angle <= down:
                self._set_phase("Bottom", timestamp)
                self._bottom_time = timestamp
                self.feedback = "Good depth - now stand up to complete the rep"
            else:
                self.feedback = "Keep standing up"
        return self._state(angle)


class BicepCurlCounter(BaseCounter):
    name = BICEP_CURLS

    def __init__(self, sensitivity: str = "Balanced", arm: str = "Right arm") -> None:
        super().__init__(sensitivity)
        self.arm = arm
        self.active_joints = (11, 13, 15) if arm == "Left arm" else (12, 14, 16)
        self._top_time: float | None = None

    def reset(self) -> None:
        super().reset()
        self._top_time = None

    def update(self, landmarks: Optional[Sequence[Any]], timestamp: float) -> ExerciseState:
        self._completed = False
        side = "left" if self.arm == "Left arm" else "right"
        angle = geo.elbow_angle(landmarks, side)
        if angle is None:
            self.feedback = f"{self.arm} is not visible - face the camera and show your arm"
            return self._state(None, "Elbow not visible")
        flex, extend = _THRESHOLDS[BICEP_CURLS][self.sensitivity]

        if self.phase in {"Ready", "Curling"}:
            if angle <= flex:
                self._set_phase("Flexed", timestamp)
                self._top_time = timestamp
                self.feedback = "Squeeze at the top, then lower slowly"
            elif angle < extend - 10:
                if self.phase != "Curling":
                    self._set_phase("Curling", timestamp)
                self.feedback = "Curl your hand toward your shoulder"
            else:
                self._set_phase("Ready", timestamp)
                self.feedback = "Fully extended - curl up for the next rep"
        elif self.phase == "Flexed":
            if angle > flex + 8:
                self._set_phase("Lowering", timestamp)
                self.feedback = "Lower slowly under control"
            else:
                self.feedback = "Hold the top position briefly"
        elif self.phase == "Lowering":
            if angle >= extend:
                held = self._top_time is not None and timestamp - self._top_time >= 0.12
                if held and self._count_rep(timestamp):
                    self.feedback = "Rep counted - keep your elbow still"
                else:
                    self.feedback = "Fully extended - curl up for the next rep"
                self._set_phase("Ready", timestamp)
                self._top_time = None
            elif angle <= flex:
                self._set_phase("Flexed", timestamp)
                self._top_time = timestamp
                self.feedback = "Squeeze at the top, then lower slowly"
            else:
                self.feedback = "Lower your hand slowly"
        return self._state(angle)


class JumpingJackCounter(BaseCounter):
    name = JUMPING_JACKS
    active_joints = (11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)

    def update(self, landmarks: Optional[Sequence[Any]], timestamp: float) -> ExerciseState:
        self._completed = False
        spread = geo.ankle_spread(landmarks)
        left_wrist = geo.landmark(landmarks, geo.LEFT_WRIST)
        right_wrist = geo.landmark(landmarks, geo.RIGHT_WRIST)
        left_shoulder = geo.landmark(landmarks, geo.LEFT_SHOULDER)
        right_shoulder = geo.landmark(landmarks, geo.RIGHT_SHOULDER)
        hips = geo.hip_center(landmarks)

        if None in (spread, left_wrist, right_wrist, left_shoulder, right_shoulder, hips):
            self.feedback = "Full body is not visible - step back to show arms and feet"
            return self._state(None, "Full body not visible")

        wrists_up = (
            float(left_wrist.y) < float(left_shoulder.y) - 0.02
            and float(right_wrist.y) < float(right_shoulder.y) - 0.02
        )
        wrists_down = (
            float(left_wrist.y) > hips[1] + 0.02 and float(right_wrist.y) > hips[1] + 0.02
        )
        open_legs, closed_legs = _THRESHOLDS[JUMPING_JACKS][self.sensitivity]
        is_open = wrists_up and spread >= open_legs
        is_closed = wrists_down and spread <= closed_legs
        angle = spread

        if self.phase in {"Ready", "Opening", "Closing"}:
            if is_open and self.phase in {"Ready", "Opening"}:
                self._set_phase("Open", timestamp)
                self.feedback = "Arms up and feet apart - now close to count"
            elif self.phase == "Ready" and (wrists_up or spread > closed_legs + 0.2):
                self._set_phase("Opening", timestamp)
                self.feedback = "Raise both arms and jump your feet apart"
            elif self.phase in {"Opening", "Closing"} and is_closed:
                if self.phase == "Closing":
                    if timestamp - self._phase_started >= 0.12:
                        if self._count_rep(timestamp):
                            self.feedback = "Rep counted - keep a steady rhythm"
                    self._set_phase("Ready", timestamp)
                else:
                    self._set_phase("Ready", timestamp)
                    self.feedback = "Start with arms down and feet together"
            else:
                self.feedback = "Raise both arms over your head while stepping out"
                if self.phase != "Opening":
                    self._set_phase("Opening", timestamp)
        elif self.phase == "Open":
            if is_closed:
                if timestamp - self._phase_started >= 0.12:
                    if self._count_rep(timestamp):
                        self.feedback = "Rep counted - keep a steady rhythm"
                self._set_phase("Ready", timestamp)
            elif not wrists_up or spread < open_legs - 0.15:
                self._set_phase("Closing", timestamp)
                self.feedback = "Bring your arms down and feet together"
            else:
                self.feedback = "Hold the open position briefly"
        return self._state(angle)


def create_counter(exercise: str, sensitivity: str, arm: str = "Right arm") -> BaseCounter:
    if exercise == BICEP_CURLS:
        return BicepCurlCounter(sensitivity, arm)
    if exercise == JUMPING_JACKS:
        return JumpingJackCounter(sensitivity)
    return SquatCounter(sensitivity)


class ExerciseSession:
    """Thread-safe session wrapper controlling counters and elapsed time."""

    def __init__(
        self,
        exercise: str = SQUATS,
        sensitivity: str = "Balanced",
        arm: str = "Right arm",
    ) -> None:
        self._lock = threading.RLock()
        self.exercise = exercise if exercise in EXERCISES else SQUATS
        self.sensitivity = sensitivity
        self.arm = arm
        self._counter = create_counter(self.exercise, sensitivity, arm)
        self.running = False
        self._started_at: float | None = None
        self._accumulated = 0.0
        self._paused_at: float | None = None

    # ------------------------------------------------------------- controls
    def select(self, exercise: str, sensitivity: str | None = None, arm: str | None = None) -> None:
        with self._lock:
            self.exercise = exercise if exercise in EXERCISES else SQUATS
            if sensitivity is not None:
                self.sensitivity = sensitivity
            if arm is not None:
                self.arm = arm
            self._counter = create_counter(self.exercise, self.sensitivity, self.arm)
            self.running = False
            self._started_at = None
            self._paused_at = None
            self._accumulated = 0.0

    def start(self, timestamp: float) -> None:
        with self._lock:
            if self.running:
                return
            self.running = True
            self._started_at = float(timestamp)
            self._paused_at = None
            self._counter.feedback = "Session started - move through the full range of motion"

    def pause(self, timestamp: float) -> None:
        with self._lock:
            if not self.running:
                return
            self._accumulated += self._elapsed(timestamp)
            self.running = False
            self._paused_at = float(timestamp)
            self._counter.feedback = "Session paused"

    def resume(self, timestamp: float) -> None:
        with self._lock:
            self.start(timestamp)

    def reset(self) -> None:
        with self._lock:
            self._counter.reset()
            self.running = False
            self._started_at = None
            self._paused_at = None
            self._accumulated = 0.0

    # --------------------------------------------------------------- update
    def update(self, landmarks: Optional[Sequence[Any]], timestamp: float) -> ExerciseState:
        with self._lock:
            if self.running:
                state = self._counter.update(landmarks, timestamp)
            else:
                state = self._counter._state(
                    geo.knee_angle(landmarks) if self.exercise == SQUATS else None
                )
                state.feedback = (
                    "Session paused" if self._started_at is not None else "Press Start to begin"
                )
                state.reps = self._counter.reps
            elapsed = self._elapsed(timestamp) if self.running else self._accumulated
            return state.with_session(self.running, elapsed)

    def _elapsed(self, timestamp: float) -> float:
        if self._started_at is None:
            return self._accumulated
        if self.running:
            return self._accumulated + max(0.0, timestamp - self._started_at)
        return self._accumulated

    def snapshot(self, timestamp: float = 0.0) -> ExerciseState:
        with self._lock:
            state = self._counter._state(None)
            return state.with_session(self.running, self._elapsed(timestamp))
