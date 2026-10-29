import math

import pytest

from humanbodyvision.core.exercise_counter import (
    BICEP_CURLS,
    JUMPING_JACKS,
    SQUATS,
    BicepCurlCounter,
    ExerciseSession,
    JumpingJackCounter,
    SquatCounter,
)
from synthetic import make_pose


def feed(counter, poses, interval=0.1):
    states = []
    for index, (kind, value) in enumerate(poses):
        if kind == "knee":
            pose = make_pose(knee_angle=value)
        else:
            pose = make_pose(elbow_angle=value)
        state = counter.update(pose, index * interval)
        states.append(state)
    return states


def test_squat_counts_full_reps_only():
    counter = SquatCounter("Balanced")
    sequence = [
        175, 150, 120, 100, 80, 120, 150, 170,
        120, 100, 80, 120, 170,
    ]
    states = feed(counter, [("knee", angle) for angle in sequence])
    assert counter.reps == 2
    assert any(state.completed_rep for state in states)
    assert counter.phase == "Ready"


def test_partial_squat_not_counted():
    counter = SquatCounter("Balanced")
    feed(counter, [("knee", angle) for angle in [175, 150, 125, 120, 150, 170]])
    assert counter.reps == 0


def test_deep_squat_requires_return_to_standing():
    counter = SquatCounter("Balanced")
    feed(counter, [("knee", angle) for angle in [175, 120, 100, 80, 80, 90, 105]])
    assert counter.reps == 0
    counter.update(make_pose(knee_angle=175), 2.0)
    assert counter.reps == 1


def test_squat_sensitivity_changes_depth_threshold():
    relaxed = SquatCounter("Relaxed")
    strict = SquatCounter("Strict")
    angles = [175, 150, 115, 110, 150, 170]
    feed(relaxed, [("knee", angle) for angle in angles])
    feed(strict, [("knee", angle) for angle in angles])
    assert relaxed.reps == 1
    assert strict.reps == 0


def test_bicep_curl_counts_and_tracks_arm():
    counter = BicepCurlCounter("Balanced", "Right arm")
    angles = [175, 150, 120, 90, 60, 45, 60, 100, 140, 160]
    feed(counter, [("elbow", angle) for angle in angles])
    assert counter.reps == 1
    assert 16 in counter.active_joints
    assert 15 not in counter.active_joints


def test_bicep_curl_without_extension_not_counted():
    counter = BicepCurlCounter("Balanced", "Right arm")
    feed(counter, [("elbow", angle) for angle in [175, 120, 60, 45, 60, 120, 145]])
    assert counter.reps == 0


def test_jumping_jack_counts_open_close_cycle():
    counter = JumpingJackCounter("Balanced")
    closed = make_pose(ankle_spread=0.08)
    opened = make_pose(ankle_spread=0.32, wrists_up=True)
    timestamps = 0.0
    states = []
    for pose in [closed, closed, opened, opened, closed, closed]:
        states.append(counter.update(pose, timestamps))
        timestamps += 0.15
    assert counter.reps == 1
    assert any(state.completed_rep for state in states)


def test_jumping_jack_missing_feet_reports_warning():
    counter = JumpingJackCounter("Balanced")
    pose = make_pose(hidden=(27, 28))
    state = counter.update(pose, 0.0)
    assert state.visibility_warning is not None
    assert counter.reps == 0


def test_session_timing_pause_resume_reset():
    session = ExerciseSession("Squats", "Balanced")
    session.start(10.0)
    session.update(make_pose(), 11.0)
    session.pause(12.0)
    snapshot = session.snapshot(20.0)
    assert not snapshot.running
    assert snapshot.elapsed == pytest.approx(2.0)
    session.resume(30.0)
    session.update(make_pose(), 33.0)
    assert session.snapshot(33.0).elapsed == pytest.approx(5.0)
    session.reset()
    assert session.snapshot(40.0).reps == 0
    assert session.snapshot(40.0).elapsed == 0


def test_session_select_resets_counter():
    session = ExerciseSession("Squats", "Balanced")
    session.start(0)
    session.update(make_pose(knee_angle=80), 1.0)
    session.select("Bicep Curls", arm="Left arm")
    assert session.exercise == BICEP_CURLS
    assert session.snapshot(2.0).reps == 0
    assert not session.snapshot(2.0).running
