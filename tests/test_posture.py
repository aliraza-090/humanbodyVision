import pytest

from humanbodyvision.core.posture_analyzer import (
    ALIGNED,
    FORWARD_LEAN,
    HEAD_OFFSET,
    INSUFFICIENT,
    SHOULDER_ASYMMETRY,
    PostureAnalyzer,
)
from synthetic import make_pose


def test_aligned_default_pose():
    analyzer = PostureAnalyzer()
    result = analyzer.analyze(make_pose())
    assert result.status == ALIGNED
    assert result.shoulder_tilt == pytest.approx(0, abs=2)
    assert result.torso_inclination == pytest.approx(0, abs=2)


def test_forward_lean_detected():
    analyzer = PostureAnalyzer()
    result = analyzer.analyze(make_pose(lean=30))
    assert result.status == FORWARD_LEAN
    assert result.warning_joints


def test_shoulder_asymmetry_detected():
    analyzer = PostureAnalyzer()
    pose = make_pose()
    pose[11].y += 0.05
    result = analyzer.analyze(pose)
    assert result.status == SHOULDER_ASYMMETRY


def test_head_offset_detected():
    analyzer = PostureAnalyzer()
    result = analyzer.analyze(make_pose(head_offset=0.2))
    assert result.status == HEAD_OFFSET


def test_insufficient_visibility():
    analyzer = PostureAnalyzer()
    assert analyzer.analyze(None).status == INSUFFICIENT
    assert analyzer.analyze(make_pose(hidden=(0, 11, 12, 23, 24))).status == INSUFFICIENT


def test_calibration_and_reset():
    analyzer = PostureAnalyzer()
    pose = make_pose(lean=30)
    calibration = analyzer.calibrate(pose)
    assert set(calibration) == {"shoulder_tilt", "torso_inclination", "head_offset"}
    result = analyzer.analyze(pose)
    assert result.calibrated
    assert result.status == ALIGNED
    analyzer.reset_calibration()
    assert analyzer.analyze(pose).status == FORWARD_LEAN


def test_calibration_requires_visible_upper_body():
    analyzer = PostureAnalyzer()
    with pytest.raises(ValueError):
        analyzer.calibrate(None)
    with pytest.raises(ValueError):
        analyzer.calibrate(make_pose(hidden=(0, 11, 12, 23, 24)))
