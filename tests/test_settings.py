import json

import pytest

from humanbodyvision.config.defaults import DEFAULT_SETTINGS
from humanbodyvision.config.settings_manager import SettingsManager


def test_defaults_and_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(path)
    assert manager.get("camera_index") == DEFAULT_SETTINGS["camera_index"]
    manager.update({"max_fps": 45, "mirror": False, "exercise": "Bicep Curls"})
    assert path.exists()

    reloaded = SettingsManager(path)
    assert reloaded.get("max_fps") == 45
    assert reloaded.get("mirror") is False
    assert reloaded.get("exercise") == "Bicep Curls"


def test_invalid_values_are_clamped_or_defaulted(tmp_path):
    manager = SettingsManager(tmp_path / "settings.json")
    manager.update(
        {
            "max_fps": 999,
            "camera_index": -5,
            "resolution": "not-a-resolution",
            "skeleton_line_thickness": 50,
            "min_detection_confidence": 5,
            "exercise": "Push-ups",
            "theme": "Neon",
        }
    )
    assert manager.get("max_fps") == 60
    assert manager.get("camera_index") == 0
    assert manager.get("resolution") == "1280x720"
    assert manager.get("skeleton_line_thickness") == 8
    assert manager.get("min_detection_confidence") == 0.95
    assert manager.get("exercise") == "Squats"
    assert manager.get("theme") == "Dark"


def test_corrupted_settings_recover(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")
    manager = SettingsManager(path)
    assert manager.last_error
    assert manager.get("max_fps") == DEFAULT_SETTINGS["max_fps"]
    assert manager.get("mirror") is True


def test_non_object_settings_recover(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    manager = SettingsManager(path)
    assert manager.last_error
    assert manager.get("camera_index") == 0


def test_unknown_keys_and_bad_types_are_ignored(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"totally_unknown": 1, "max_fps": "fast", "mirror": "yes"}),
        encoding="utf-8",
    )
    manager = SettingsManager(path)
    assert "totally_unknown" not in manager.snapshot()
    assert manager.get("max_fps") == 30
    assert manager.get("mirror") is True


def test_posture_calibration_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    manager = SettingsManager(path)
    calibration = {"shoulder_tilt": 1.5, "torso_inclination": 2.0, "head_offset": 0.1}
    manager.set_posture_calibration(calibration)
    assert SettingsManager(path).get("posture_calibration") == calibration
    manager.set_posture_calibration(None)
    assert SettingsManager(path).get("posture_calibration") is None


def test_restore_defaults(tmp_path):
    manager = SettingsManager(tmp_path / "settings.json")
    manager.update({"max_fps": 55, "audio_feedback": False})
    manager.reset()
    assert manager.get("max_fps") == 30
    assert manager.get("audio_feedback") is True
