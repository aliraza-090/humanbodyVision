import math

import pytest

from humanbodyvision.core import landmark_geometry as geo
from synthetic import make_pose, with_visibility


def test_angle_between_right_angle():
    class P:
        def __init__(self, x, y, visibility=0.99):
            self.x, self.y, self.visibility = x, y, visibility

    assert geo.angle_between(P(0, 1), P(0, 0), P(1, 0)) == pytest.approx(90.0)
    assert geo.angle_between(P(0, 1), P(0, 0), P(0, -1)) == pytest.approx(180.0)


def test_knee_and_elbow_angles_from_synthetic_pose():
    pose = make_pose(knee_angle=110, elbow_angle=60)
    assert geo.knee_angle(pose) == pytest.approx(110, abs=2.0)
    assert geo.elbow_angle(pose, "right") == pytest.approx(60, abs=2.0)
    assert geo.elbow_angle(pose, "left") == pytest.approx(60, abs=2.0)


def test_missing_and_low_visibility_landmarks():
    pose = make_pose(hidden=(25, 26))
    assert geo.knee_angle(pose) is None
    pose = with_visibility(make_pose(), (25, 26, 11, 12), 0.0)
    assert geo.visibility(pose[25]) == 0.0
    assert not geo.is_visible(pose[25], 0.5)
    assert geo.knee_angle(pose) is not None  # geometry exists even when hidden


def test_torso_inclination_and_shoulder_tilt():
    upright = make_pose()
    leaning = make_pose(lean=35)
    assert geo.torso_inclination(upright) == pytest.approx(0, abs=1)
    assert geo.torso_inclination(leaning) == pytest.approx(35, abs=2)
    assert geo.shoulder_tilt(upright) == pytest.approx(0, abs=1)
    assert geo.torso_length(upright) > 0.1
    assert geo.body_scale(upright) == pytest.approx(0.23, abs=0.02)


def test_head_offset_and_leg_ratio():
    pose = make_pose(head_offset=0.1)
    assert geo.head_offset(pose) > 0.3
    assert geo.leg_vertical_ratio(pose) > 1.0
    sitting = make_pose(ankle_y=0.63, knee_angle=110)
    assert geo.leg_vertical_ratio(sitting) < 0.6
    assert geo.ankle_spread(make_pose(ankle_spread=0.3)) > 1.0


def test_torso_vector_none_when_hips_hidden():
    assert geo.torso_vector(make_pose(hidden=(23, 24))) is None
    assert geo.shoulder_tilt(make_pose(hidden=(11,))) is None
    assert geo.torso_inclination(None) is None
    assert geo.angle_between(None, None, None) is None
