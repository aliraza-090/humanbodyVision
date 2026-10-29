"""Pipeline integration tests with a fake pose detector.

Synthetic landmarks are used only to exercise geometry, rendering and state
machines. They are not evidence of real-world webcam accuracy.
"""

from __future__ import annotations

import numpy as np

from humanbodyvision.core.pipeline import Pipeline
from humanbodyvision.core.pose_detector import PoseDetection
from humanbodyvision.core.skeleton_renderer import SkeletonStyle, draw_skeleton
from synthetic import STANDING, make_pose


class FakeDetector:
    def __init__(self, landmarks=None) -> None:
        self.landmarks = landmarks
        self.calls = 0
        self.closed = 0
        self.last_timestamp: int | None = None

    def detect(self, frame, timestamp_ms: int) -> PoseDetection:
        self.calls += 1
        self.last_timestamp = timestamp_ms
        return PoseDetection(self.landmarks, timestamp_ms=timestamp_ms)

    def close(self) -> None:
        self.closed += 1


class BrokenDetector:
    def detect(self, frame, timestamp_ms: int):
        raise RuntimeError("simulated inference failure")

    def close(self) -> None:
        pass


def _frame(width: int = 640, height: int = 480) -> np.ndarray:
    return np.full((height, width, 3), 35, dtype=np.uint8)


def test_pipeline_detects_body_and_draws_green_skeleton():
    landmarks = make_pose(**STANDING)
    detector = FakeDetector(landmarks)
    pipeline = Pipeline(detector=detector, settings={"mirror": False})

    result = pipeline.process(_frame(), timestamp=10.0)

    assert result.detected is True
    assert result.pose_error is None
    assert result.landmark_total == 33
    assert result.landmark_count >= 25
    assert result.frame is not None
    assert result.frame.shape == (480, 640, 3)
    # The skeleton lines are pure green; anti-aliased edges blend toward the
    # dark background, so look for strongly green pixels rather than an exact
    # single colour count.
    blue, green, red = result.frame[:, :, 0], result.frame[:, :, 1], result.frame[:, :, 2]
    green_pixels = int(np.count_nonzero((green > 180) & (red < 120) & (blue < 120)))
    assert green_pixels > 100
    assert detector.calls == 1


def test_pipeline_without_detector_reports_model_error():
    pipeline = Pipeline(detector=None)
    result = pipeline.process(_frame(), timestamp=1.0)
    assert result.detected is False
    assert result.pose_error == "Pose model is not loaded."
    assert result.frame is not None


def test_pipeline_survives_detector_exception():
    pipeline = Pipeline(detector=BrokenDetector())
    result = pipeline.process(_frame(), timestamp=1.0)
    assert result.detected is False
    assert "simulated inference failure" in (result.pose_error or "")
    assert result.frame is not None


def test_pipeline_toggle_skeleton_hides_overlay():
    landmarks = make_pose(**STANDING)
    pipeline = Pipeline(detector=FakeDetector(landmarks), settings={"mirror": False})
    assert pipeline.toggle_skeleton() is False
    result = pipeline.process(_frame(), timestamp=1.0)
    # With the overlay hidden only the HUD remains; no skeleton joint circles.
    assert result.frame is not None
    style = SkeletonStyle(visibility_threshold=0.5, visible=False)
    canvas = _frame()
    draw_skeleton(canvas, landmarks, style=style)
    assert np.array_equal(canvas, _frame())


def test_pipeline_posture_calibration_roundtrip():
    landmarks = make_pose(**STANDING)
    pipeline = Pipeline(detector=FakeDetector(landmarks), settings={"mirror": False})
    pipeline.process(_frame(), timestamp=1.0)

    calibration = pipeline.calibrate_posture()
    assert set(calibration) == {"shoulder_tilt", "torso_inclination", "head_offset"}
    assert pipeline.settings["posture_calibration"] == calibration

    result = pipeline.process(_frame(), timestamp=1.1)
    assert result.posture.calibrated is True
    assert result.posture.status != "Insufficient visibility"

    pipeline.reset_posture_calibration()
    assert pipeline.settings["posture_calibration"] is None
    assert pipeline.process(_frame(), timestamp=1.2).posture.calibrated is False


def test_pipeline_mirrors_display_without_mutating_input():
    landmarks = make_pose(**STANDING)
    pipeline = Pipeline(detector=FakeDetector(landmarks), settings={"mirror": True})
    source = _frame()
    original = source.copy()
    result = pipeline.process(source, timestamp=1.0)
    assert np.array_equal(source, original)
    assert result.frame is not None and result.frame is not source


def test_pipeline_exercise_controls_and_rep_event_sequence():
    landmarks = make_pose(**STANDING)
    pipeline = Pipeline(detector=FakeDetector(landmarks), settings={"mirror": False})

    idle = pipeline.exercise_snapshot(timestamp=0.0)
    assert idle.running is False and idle.reps == 0

    pipeline.start_exercise(timestamp=5.0)
    running = pipeline.process(_frame(), timestamp=5.1).exercise
    assert running.running is True
    assert running.elapsed >= 0.0

    pipeline.pause_exercise(timestamp=6.0)
    paused = pipeline.process(_frame(), timestamp=6.1).exercise
    assert paused.running is False

    pipeline.reset_exercise()
    reset = pipeline.exercise_snapshot(timestamp=7.0)
    assert reset.reps == 0 and reset.running is False


def test_pipeline_apply_settings_updates_style_and_closes_detector():
    detector = FakeDetector(make_pose(**STANDING))
    pipeline = Pipeline(detector=detector, settings={"mirror": False})
    pipeline.apply_settings(
        {
            "skeleton_visible": False,
            "skeleton_line_thickness": 5,
            "landmark_dot_size": 7,
            "landmark_visibility_threshold": 0.7,
            "fall_detection_enabled": False,
        }
    )
    assert pipeline.style.visible is False
    assert pipeline.style.line_thickness == 5
    assert pipeline.style.dot_size == 7
    assert pipeline.style.visibility_threshold == 0.7
    assert pipeline.fall_enabled is False

    pipeline.close()
    assert detector.closed == 1
    assert pipeline.detector is None
