import pytest

from humanbodyvision.core.activity_recognizer import (
    BENDING,
    RAISING_ARM,
    SITTING,
    SQUATTING,
    STANDING,
    UNKNOWN,
    WALKING,
    ActivityRecognizer,
)
from humanbodyvision.core.motion_tracker import MotionTracker
from synthetic import make_pose


def run_sequence(recognizer, tracker, poses, interval=0.1, start=0.0):
    result = None
    for index, pose in enumerate(poses):
        timestamp = start + index * interval
        motion = tracker.update(pose, timestamp)
        result = recognizer.update(pose, motion, timestamp)
    return result


def test_unknown_without_body():
    recognizer = ActivityRecognizer()
    tracker = MotionTracker()
    result = recognizer.update(None, tracker.features(), 1.0)
    assert result.label == UNKNOWN
    assert result.evidence == "None"


def test_standing_classification_and_smoothing():
    recognizer = ActivityRecognizer()
    tracker = MotionTracker()
    result = run_sequence(recognizer, tracker, [make_pose()] * 12)
    assert result is not None
    assert result.label == STANDING
    assert result.evidence in {"Moderate", "Strong"}


def test_single_frame_does_not_switch_label():
    recognizer = ActivityRecognizer()
    tracker = MotionTracker()
    run_sequence(recognizer, tracker, [make_pose()] * 12)
    result = run_sequence(
        recognizer, tracker, [make_pose(knee_angle=85)], start=1.3
    )
    assert result.label == STANDING  # hysteresis rejects a one-frame flicker


def test_sustained_squat_switches_after_hold():
    recognizer = ActivityRecognizer()
    tracker = MotionTracker()
    run_sequence(recognizer, tracker, [make_pose()] * 12)
    result = run_sequence(
        recognizer, tracker, [make_pose(knee_angle=85)] * 12, start=1.3
    )
    assert result.label == SQUATTING


def test_raising_arm_and_bending_and_sitting():
    for pose, expected in (
        (make_pose(wrists_up=True), RAISING_ARM),
        (make_pose(lean=55), BENDING),
        (make_pose(ankle_y=0.63, knee_angle=110), SITTING),
    ):
        recognizer = ActivityRecognizer()
        tracker = MotionTracker()
        result = run_sequence(recognizer, tracker, [pose] * 12)
        assert result.label == expected, expected


def test_walking_in_place_uses_temporal_motion():
    recognizer = ActivityRecognizer()
    tracker = MotionTracker()
    poses = []
    for index in range(24):
        phase = (index // 2) % 2
        poses.append(
            make_pose(
                left_ankle_lift=0.06 if phase == 0 else 0.0,
                right_ankle_lift=0.0 if phase == 0 else 0.06,
            )
        )
    result = run_sequence(recognizer, tracker, poses, interval=0.1)
    assert result.label == WALKING


def test_motion_tracker_features_are_bounded():
    tracker = MotionTracker()
    for index in range(12):
        tracker.update(make_pose(), index * 0.1)
    features = tracker.features()
    assert features.valid
    assert features.duration >= 0.9
    assert features.motion_energy >= 0
    assert features.ankle_lift_range == pytest.approx(0.0, abs=0.01)
