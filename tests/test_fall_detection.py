import pytest

from humanbodyvision.core.fall_detector import FallDetector
from synthetic import make_pose


def feed(detector, poses, start=0.0, interval=0.1):
    results = []
    for index, pose in enumerate(poses):
        results.append(detector.update(pose, start + index * interval, enabled=True))
    return results


def test_no_alert_for_standing_sitting_or_bending():
    for pose in (
        make_pose(),
        make_pose(ankle_y=0.63, knee_angle=110),
        make_pose(lean=50),
    ):
        detector = FallDetector("Balanced")
        results = feed(detector, [pose] * 15)
        assert not any(result.alert_active for result in results)
        assert not any(result.new_alert for result in results)


def test_fall_sequence_triggers_alert():
    detector = FallDetector("Balanced")
    poses = [make_pose()] * 9
    poses.append(make_pose(hip_y=0.70, lean=35))
    poses.append(make_pose(hip_y=0.88, lean=70))
    results = feed(detector, poses)
    assert any(result.new_alert for result in results)
    assert results[-1].alert_active
    assert "Possible fall" in results[-1].message


def test_alert_requires_multiple_signals():
    detector = FallDetector("Balanced")
    # Horizontal torso alone, without a rapid drop or sustained low posture.
    results = feed(detector, [make_pose(lean=70)] * 12)
    assert not any(result.alert_active for result in results)


def test_dismiss_and_cooldown():
    detector = FallDetector("Balanced", cooldown_seconds=10.0)
    poses = [make_pose()] * 9
    poses += [make_pose(hip_y=0.70, lean=35), make_pose(hip_y=0.88, lean=70)]
    feed(detector, poses)
    assert detector.active
    detector.dismiss(1.0)
    result = detector.update(make_pose(hip_y=0.9, lean=75), 1.2, enabled=True)
    assert not result.alert_active


def test_strict_sensitivity_rejects_marginal_drop():
    detector = FallDetector("Strict")
    poses = [make_pose()] * 9
    poses += [make_pose(hip_y=0.68, lean=35), make_pose(hip_y=0.80, lean=70)]
    results = feed(detector, poses)
    assert not any(result.alert_active for result in results)


def test_disabled_detector_does_not_alert():
    detector = FallDetector("Balanced")
    result = detector.update(make_pose(hip_y=0.9, lean=80), 1.0, enabled=False)
    assert not result.enabled
    assert not result.alert_active
    assert not result.monitored
