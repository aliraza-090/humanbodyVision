"""Application controller lifecycle tests with a stubbed pose detector."""

from __future__ import annotations

import json

import numpy as np
import pytest

import humanbodyvision.app as app_module
from humanbodyvision.app import ApplicationController
from humanbodyvision.core.pose_detector import PoseDetection
from synthetic import STANDING, make_pose


class StubPoseDetector:
    instances: list["StubPoseDetector"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.closed = 0
        self.detect_calls = 0
        StubPoseDetector.instances.append(self)

    def detect(self, frame, timestamp_ms: int) -> PoseDetection:
        self.detect_calls += 1
        return PoseDetection(make_pose(**STANDING), timestamp_ms=timestamp_ms)

    def close(self) -> None:
        self.closed += 1


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMANBODYVISION_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(app_module, "PoseDetector", StubPoseDetector)
    StubPoseDetector.instances.clear()
    ctrl = ApplicationController()
    yield ctrl
    ctrl.shutdown()


def test_controller_starts_with_stubbed_detector(controller, tmp_path):
    assert controller.model_error is None
    assert controller.pipeline.detector is not None
    assert controller.processor is not None
    assert controller.settings["camera_index"] == 0
    assert len(StubPoseDetector.instances) == 1


def test_controller_toggles_and_settings_persist(controller, tmp_path):
    assert controller.skeleton_visible is True
    assert controller.toggle_skeleton() is False
    assert controller.skeleton_visible is False

    controller.select_exercise("Bicep Curls")
    controller.select_exercise_arm("Left arm")
    controller.set_fall_enabled(False)
    controller.set_fall_sensitivity("Strict")

    saved = json.loads((tmp_path / "data" / "settings.json").read_text(encoding="utf-8"))
    assert saved["skeleton_visible"] is False
    assert saved["exercise"] == "Bicep Curls"
    assert saved["exercise_arm"] == "Left arm"
    assert saved["fall_detection_enabled"] is False
    assert saved["fall_sensitivity"] == "Strict"


def test_controller_applies_restart_setting_and_replaces_pipeline(controller):
    first_pipeline = controller.pipeline
    first_detector = controller.pipeline.detector

    ok, message = controller.apply_settings({"camera_index": 1, "max_fps": 24})

    assert ok is True
    assert "restarted" in message.lower()
    assert controller.pipeline is not first_pipeline
    assert first_detector.closed == 1
    assert controller.settings["camera_index"] == 1
    assert controller.settings["max_fps"] == 24
    assert len(StubPoseDetector.instances) == 2


def test_controller_restores_defaults(controller):
    controller.apply_settings({"max_fps": 50, "mirror": False})
    assert controller.settings["max_fps"] == 50

    ok, message = controller.restore_defaults()

    assert ok is True
    assert "restored" in message.lower()
    assert controller.settings["max_fps"] == 30
    assert controller.settings["mirror"] is True


def test_controller_posture_calibration_requires_landmarks(controller):
    ok, message = controller.calibrate_posture()
    assert ok is False
    assert "upper body" in message.lower()

    frame = np.full((240, 320, 3), 30, dtype=np.uint8)
    controller.pipeline.process(frame, timestamp=1.0)

    ok, message = controller.calibrate_posture()
    assert ok is True
    assert "neutral posture" in message.lower()
    assert controller.settings["posture_calibration"] is not None

    controller.reset_posture_calibration()
    assert controller.settings["posture_calibration"] is None


def test_controller_survives_model_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMANBODYVISION_DATA_DIR", str(tmp_path / "data"))

    class FailingDetector:
        def __init__(self, **kwargs) -> None:
            raise app_module.ModelInitError("simulated model failure")

    monkeypatch.setattr(app_module, "PoseDetector", FailingDetector)
    controller = ApplicationController()
    try:
        assert controller.model_error
        assert "simulated model failure" in controller.model_error
        assert controller.pipeline.detector is None
        result = controller.pipeline.process(
            np.full((120, 160, 3), 20, dtype=np.uint8), timestamp=1.0
        )
        assert result.detected is False
        assert result.pose_error == "Pose model is not loaded."
    finally:
        controller.shutdown()


class _FakeProcessor:
    def __init__(self, results) -> None:
        self._results = list(results)
        self.capture_fps = 12.5
        self.shutdown_calls = 0

    def drain_result(self):
        return self._results.pop(0) if self._results else None

    def status(self):
        return ("Connected", "Camera connected and streaming.")

    def shutdown(self):
        self.shutdown_calls += 1


class _FakeController:
    model_error = None

    def __init__(self, results) -> None:
        self.processor = _FakeProcessor(results)
        self.started = False
        self.shutdown_calls = 0

    def start_camera(self):
        self.started = True

    def shutdown(self):
        self.shutdown_calls += 1
        self.processor.shutdown()


def test_self_test_passes_when_frames_are_processed(monkeypatch, capsys):
    from humanbodyvision.core.pipeline import FrameResult

    results = [
        FrameResult(frame=np.zeros((48, 64, 3), dtype=np.uint8), detected=True),
        FrameResult(frame=np.zeros((48, 64, 3), dtype=np.uint8), detected=False),
    ]
    fake = _FakeController(results)
    monkeypatch.setattr(app_module, "ApplicationController", lambda: fake)

    code = app_module.run_self_test(seconds=1.0)

    assert code == 0
    assert fake.started is True
    assert fake.shutdown_calls == 1
    assert fake.processor.shutdown_calls == 1
    out = capsys.readouterr().out
    assert "SELF-TEST PASS" in out
    assert "processed=2" in out
    assert "detected=1" in out


def test_self_test_fails_without_frames(monkeypatch, capsys):
    fake = _FakeController([])
    monkeypatch.setattr(app_module, "ApplicationController", lambda: fake)

    code = app_module.run_self_test(seconds=1.0)

    assert code == 3
    assert fake.shutdown_calls == 1
    assert "SELF-TEST FAIL" in capsys.readouterr().err


def test_self_test_fails_when_model_missing(monkeypatch, capsys):
    fake = _FakeController([])
    fake.model_error = "simulated model failure"
    monkeypatch.setattr(app_module, "ApplicationController", lambda: fake)

    code = app_module.run_self_test(seconds=1.0)

    assert code == 2
    assert fake.started is False
    assert "simulated model failure" in capsys.readouterr().err
