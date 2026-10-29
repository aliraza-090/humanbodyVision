"""Default configuration values for humanbodyVision."""

from __future__ import annotations

APP_NAME = "humanbodyVision"
APP_TAGLINE = "AI-Powered Human Body Tracking & Activity Recognition"
DEVELOPER = "Ali Raza Chakrani"

# Resolution presets: label -> (width, height)
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "640x480": (640, 480),
    "1280x720": (1280, 720),
    "1920x1080": (1920, 1080),
}

EXERCISES = ["Squats", "Bicep Curls", "Jumping Jacks"]
EXERCISE_ARMS = ["Right arm", "Left arm"]
SENSITIVITIES = ["Relaxed", "Balanced", "Strict"]
THEMES = ["Dark", "Light", "System"]

DEFAULT_SETTINGS: dict = {
    "camera_index": 0,
    "resolution": "1280x720",
    "max_fps": 30,
    "mirror": True,
    "model_variant": "full",
    "min_detection_confidence": 0.5,
    "min_tracking_confidence": 0.5,
    "min_presence_confidence": 0.5,
    "skeleton_visible": True,
    "skeleton_line_thickness": 3,
    "landmark_dot_size": 4,
    "landmark_visibility_threshold": 0.5,
    "exercise": "Squats",
    "exercise_arm": "Right arm",
    "exercise_sensitivity": "Balanced",
    "fall_detection_enabled": True,
    "fall_sensitivity": "Balanced",
    "audio_feedback": True,
    "theme": "Dark",
    "posture_calibration": None,
}

# Valid ranges used by the settings validator.
NUMERIC_BOUNDS = {
    "camera_index": (0, 9),
    "max_fps": (10, 60),
    "min_detection_confidence": (0.1, 0.95),
    "min_tracking_confidence": (0.1, 0.95),
    "min_presence_confidence": (0.1, 0.95),
    "skeleton_line_thickness": (1, 8),
    "landmark_dot_size": (1, 10),
    "landmark_visibility_threshold": (0.2, 0.9),
}
