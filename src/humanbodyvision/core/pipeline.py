"""Frame analysis pipeline.

Combines pose detection, skeleton rendering and all analysis modules into a
single result object consumed by the GUI. Only the processing worker thread
calls :meth:`Pipeline.process`; control methods are guarded by a lock so the
GUI can issue commands safely.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import cv2
import numpy as np

from . import landmark_geometry as geo
from .activity_recognizer import ActivityRecognizer, ActivityResult
from .exercise_counter import ExerciseSession, ExerciseState
from .fall_detector import FallDetector, FallResult
from .motion_tracker import MotionFeatures, MotionTracker
from .pose_detector import PoseDetector, landmarks_are_usable
from .posture_analyzer import PostureAnalyzer, PostureResult
from .skeleton_renderer import SkeletonStyle, draw_hud, draw_skeleton
from ..utils.logger import get_logger

log = get_logger("pipeline")


@dataclass
class FrameResult:
    frame: Optional[np.ndarray] = None
    frame_id: int = 0
    timestamp: float = 0.0
    fps: float = 0.0
    detected: bool = False
    landmarks: Optional[list[Any]] = None
    landmark_count: int = 0
    landmark_total: int = 0
    activity: ActivityResult = field(default_factory=ActivityResult)
    posture: PostureResult = field(default_factory=PostureResult)
    exercise: ExerciseState = field(default_factory=ExerciseState)
    fall: FallResult = field(default_factory=FallResult)
    motion: MotionFeatures = field(default_factory=MotionFeatures)
    processing_ms: float = 0.0
    rep_event_seq: int = 0
    fall_event_seq: int = 0
    pose_error: str | None = None
    frame_width: int = 0
    frame_height: int = 0


class Pipeline:
    def __init__(
        self,
        detector: Optional[PoseDetector] = None,
        settings: Optional[dict[str, Any]] = None,
        exercise: str = "Squats",
        exercise_arm: str = "Right arm",
    ) -> None:
        self.detector = detector
        self.settings = dict(settings or {})
        self._lock = threading.RLock()

        visibility = float(self.settings.get("landmark_visibility_threshold", 0.5))
        self.style = SkeletonStyle(
            line_thickness=int(self.settings.get("skeleton_line_thickness", 3)),
            dot_size=int(self.settings.get("landmark_dot_size", 4)),
            visibility_threshold=visibility,
            visible=bool(self.settings.get("skeleton_visible", True)),
        )
        self.mirror = bool(self.settings.get("mirror", True))
        self.fall_enabled = bool(self.settings.get("fall_detection_enabled", True))

        self.motion = MotionTracker()
        self.activity = ActivityRecognizer(visibility_threshold=visibility)
        self.posture = PostureAnalyzer(
            calibration=self.settings.get("posture_calibration"),
            visibility_threshold=visibility,
        )
        self.exercise = ExerciseSession(
            exercise=exercise,
            sensitivity=self.settings.get("exercise_sensitivity", "Balanced"),
            arm=exercise_arm,
        )
        self.fall = FallDetector(
            sensitivity=self.settings.get("fall_sensitivity", "Balanced")
        )

        self._frame_id = 0
        self._fps = 0.0
        self._last_process_time: float | None = None
        self._last_landmarks: Optional[list[Any]] = None
        self._rep_seq = 0
        self._fall_seq = 0
        self._last_pose_error: str | None = None

    # -------------------------------------------------------------- settings
    def apply_settings(self, settings: dict[str, Any]) -> None:
        """Hot-apply settings that do not require rebuilding the model/camera."""
        with self._lock:
            self.settings.update(settings)
            visibility = float(settings.get("landmark_visibility_threshold", 0.5))
            self.style.visible = bool(settings.get("skeleton_visible", self.style.visible))
            self.style.line_thickness = int(
                settings.get("skeleton_line_thickness", self.style.line_thickness)
            )
            self.style.dot_size = int(settings.get("landmark_dot_size", self.style.dot_size))
            self.style.visibility_threshold = visibility
            self.mirror = bool(settings.get("mirror", self.mirror))
            self.fall_enabled = bool(
                settings.get("fall_detection_enabled", self.fall_enabled)
            )
            if "fall_sensitivity" in settings:
                self.fall.set_sensitivity(settings["fall_sensitivity"])
            if "posture_calibration" in settings:
                self.posture.set_calibration(settings.get("posture_calibration"))
            self.activity.visibility_threshold = visibility
            self.posture.visibility_threshold = visibility
            if (
                "exercise_sensitivity" in settings
                or "exercise" in settings
                or "exercise_arm" in settings
            ):
                exercise = settings.get("exercise", self.exercise.exercise)
                sensitivity = settings.get("exercise_sensitivity", self.exercise.sensitivity)
                arm = settings.get("exercise_arm", self.exercise.arm)
                if (
                    exercise != self.exercise.exercise
                    or sensitivity != self.exercise.sensitivity
                    or arm != self.exercise.arm
                ):
                    self.exercise.select(exercise, sensitivity, arm)

    def toggle_skeleton(self) -> bool:
        with self._lock:
            self.style.visible = not self.style.visible
            self.settings["skeleton_visible"] = self.style.visible
            return self.style.visible

    # -------------------------------------------------------------- controls
    def select_exercise(self, exercise: str) -> None:
        with self._lock:
            self.exercise.select(exercise, self.exercise.sensitivity, self.exercise.arm)

    def start_exercise(self, timestamp: float | None = None) -> None:
        with self._lock:
            self.exercise.start(timestamp if timestamp is not None else time.monotonic())

    def pause_exercise(self, timestamp: float | None = None) -> None:
        with self._lock:
            self.exercise.pause(timestamp if timestamp is not None else time.monotonic())

    def reset_exercise(self) -> None:
        with self._lock:
            self.exercise.reset()

    def exercise_snapshot(self, timestamp: float | None = None) -> ExerciseState:
        with self._lock:
            return self.exercise.snapshot(timestamp if timestamp is not None else time.monotonic())

    def calibrate_posture(self) -> dict[str, float]:
        with self._lock:
            calibration = self.posture.calibrate(self._last_landmarks)
            self.settings["posture_calibration"] = calibration
            return calibration

    def reset_posture_calibration(self) -> None:
        with self._lock:
            self.posture.reset_calibration()
            self.settings["posture_calibration"] = None

    def dismiss_fall(self, timestamp: float | None = None) -> None:
        with self._lock:
            self.fall.dismiss(timestamp if timestamp is not None else time.monotonic())

    def close(self) -> None:
        with self._lock:
            if self.detector is not None:
                self.detector.close()
                self.detector = None

    # --------------------------------------------------------------- process
    def process(
        self,
        frame_bgr: np.ndarray,
        timestamp: float | None = None,
        timestamp_ms: int | None = None,
    ) -> FrameResult:
        started = time.perf_counter()
        now = time.monotonic() if timestamp is None else float(timestamp)
        if timestamp_ms is None:
            timestamp_ms = int(now * 1000)

        with self._lock:
            self._frame_id += 1
            detected = False
            landmarks: Optional[list[Any]] = None
            pose_error: str | None = None

            if self.detector is not None:
                try:
                    detection = self.detector.detect(frame_bgr, timestamp_ms)
                    landmarks = detection.landmarks
                    detected = bool(landmarks) and landmarks_are_usable(
                        landmarks, max(0.2, self.style.visibility_threshold - 0.2)
                    )
                    if landmarks is not None and not detected:
                        # Keep partial landmarks for drawing but do not claim a
                        # reliable body detection in the status panel.
                        detected = len(landmarks) >= 29
                except Exception as exc:
                    pose_error = str(exc)
                    if pose_error != self._last_pose_error:
                        log.error("Pose detection error: %s", exc)
                        self._last_pose_error = pose_error
            else:
                pose_error = "Pose model is not loaded."

            if landmarks is not None:
                self._last_landmarks = landmarks
            visible_count = _visible_landmark_count(
                landmarks, self.style.visibility_threshold
            )

            motion = self.motion.update(landmarks if detected else None, now)
            activity = self.activity.update(landmarks if detected else None, motion, now)
            posture = self.posture.analyze(landmarks if detected else None)
            exercise_state = self.exercise.update(landmarks if detected else None, now)
            fall_state = self.fall.update(
                landmarks if detected else None, now, enabled=self.fall_enabled
            )

            if exercise_state.completed_rep:
                self._rep_seq += 1
            if fall_state.new_alert:
                self._fall_seq += 1

            # FPS measured from consecutive processed frames.
            if self._last_process_time is not None:
                delta = now - self._last_process_time
                if delta > 1e-4:
                    instant = 1.0 / delta
                    self._fps = instant if self._fps <= 0 else self._fps * 0.85 + instant * 0.15
            self._last_process_time = now

            display = cv2.flip(frame_bgr, 1) if self.mirror else frame_bgr.copy()

            active_joints = set(activity.active_joints)
            if exercise_state.running:
                active_joints.update(exercise_state.active_joints)
            warning_joints = set(posture.warning_joints)
            if fall_state.alert_active:
                warning_joints.update((11, 12, 23, 24))

            draw_skeleton(
                display,
                landmarks,
                style=self.style,
                mirror=self.mirror,
                active_joints=active_joints,
                warning_joints=warning_joints,
            )

            secondary = None
            if exercise_state.running:
                secondary = f"{exercise_state.exercise}: {exercise_state.reps} reps | {exercise_state.phase}"
            draw_hud(
                display,
                activity=activity.label if detected else "No body detected",
                fps=self._fps,
                detected=detected,
                status="Possible fall detected" if fall_state.alert_active else None,
                secondary=secondary,
                warning="Possible fall detected" if fall_state.alert_active else None,
            )

            elapsed_ms = (time.perf_counter() - started) * 1000.0
            height, width = display.shape[:2]
            return FrameResult(
                frame=display,
                frame_id=self._frame_id,
                timestamp=now,
                fps=self._fps,
                detected=detected,
                landmarks=landmarks,
                landmark_count=visible_count,
                landmark_total=len(landmarks) if landmarks else 0,
                activity=activity,
                posture=posture,
                exercise=exercise_state,
                fall=fall_state,
                motion=motion,
                processing_ms=elapsed_ms,
                rep_event_seq=self._rep_seq,
                fall_event_seq=self._fall_seq,
                pose_error=pose_error,
                frame_width=width,
                frame_height=height,
            )


def _visible_landmark_count(landmarks: Optional[Sequence[Any]], threshold: float) -> int:
    if not landmarks:
        return 0
    return sum(1 for point in landmarks if geo.visibility(point) >= threshold)
