"""Persistent JSON settings with validation and corruption recovery."""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path
from typing import Any

from ..utils.logger import get_logger
from ..utils.paths import settings_path
from .defaults import (
    DEFAULT_SETTINGS,
    EXERCISE_ARMS,
    EXERCISES,
    NUMERIC_BOUNDS,
    RESOLUTIONS,
    SENSITIVITIES,
    THEMES,
)

log = get_logger("settings")


class SettingsManager:
    """Loads, validates and stores settings in a per-user JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else settings_path()
        self._lock = threading.RLock()
        self._settings: dict[str, Any] = copy.deepcopy(DEFAULT_SETTINGS)
        self.last_error: str | None = None
        self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> dict[str, Any]:
        with self._lock:
            self._settings = copy.deepcopy(DEFAULT_SETTINGS)
            self.last_error = None
            if not self.path.exists():
                return self.snapshot()

            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("settings root must be a JSON object")
                self._settings.update(self._sanitise(raw))
            except (OSError, ValueError, TypeError) as exc:
                self.last_error = f"Settings could not be read ({exc}). Defaults restored."
                log.warning("Invalid settings file %s: %s", self.path, exc)
                self._settings = copy.deepcopy(DEFAULT_SETTINGS)
            return self.snapshot()

    # ------------------------------------------------------------------ save
    def save(self) -> bool:
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".json.tmp")
                tmp.write_text(
                    json.dumps(self._settings, indent=2, sort_keys=True),
                    encoding="utf-8",
                )
                os.replace(tmp, self.path)
                self.last_error = None
                return True
            except OSError as exc:
                self.last_error = f"Settings could not be saved: {exc}"
                log.error("Could not save settings to %s: %s", self.path, exc)
                return False

    # ----------------------------------------------------------------- access
    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._settings)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return copy.deepcopy(self._settings.get(key, default))

    def update(self, values: dict[str, Any], save: bool = True) -> dict[str, Any]:
        with self._lock:
            self._settings.update(self._sanitise(values))
            if save:
                self.save()
            return self.snapshot()

    def reset(self, save: bool = True) -> dict[str, Any]:
        with self._lock:
            self._settings = copy.deepcopy(DEFAULT_SETTINGS)
            if save:
                self.save()
            return self.snapshot()

    def set_posture_calibration(self, calibration: dict[str, float] | None) -> None:
        with self._lock:
            self._settings["posture_calibration"] = calibration
            self.save()

    # -------------------------------------------------------------- validation
    def _sanitise(self, values: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        defaults = DEFAULT_SETTINGS

        for key, value in values.items():
            if key not in defaults:
                continue  # ignore unknown keys rather than persisting junk

            default = defaults[key]
            try:
                if key in NUMERIC_BOUNDS:
                    low, high = NUMERIC_BOUNDS[key]
                    number = float(value)
                    if key in {"camera_index", "max_fps", "skeleton_line_thickness",
                               "landmark_dot_size"}:
                        number = int(round(number))
                    clean[key] = max(low, min(high, number))
                elif key == "resolution":
                    clean[key] = value if value in RESOLUTIONS else default
                elif key == "model_variant":
                    clean[key] = value if value in {"lite", "full", "heavy"} else default
                elif key == "exercise":
                    clean[key] = value if value in EXERCISES else default
                elif key == "exercise_arm":
                    clean[key] = value if value in EXERCISE_ARMS else default
                elif key == "exercise_sensitivity":
                    clean[key] = value if value in SENSITIVITIES else default
                elif key == "fall_sensitivity":
                    clean[key] = value if value in SENSITIVITIES else default
                elif key == "theme":
                    clean[key] = value if value in THEMES else default
                elif key == "posture_calibration":
                    clean[key] = self._clean_calibration(value)
                elif isinstance(default, bool):
                    if isinstance(value, bool):
                        clean[key] = value
                    elif isinstance(value, (int, float)):
                        clean[key] = bool(value)
                    elif isinstance(value, str):
                        clean[key] = value.strip().lower() in {"1", "true", "yes", "on"}
                elif isinstance(default, (int, float)):
                    clean[key] = type(default)(value)
                elif isinstance(default, str):
                    clean[key] = str(value)
            except (TypeError, ValueError):
                # Keep the default for this bad field and continue.
                continue

        return clean

    @staticmethod
    def _clean_calibration(value: Any) -> dict[str, float] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            return None
        wanted = {"shoulder_tilt", "torso_inclination", "head_offset"}
        clean: dict[str, float] = {}
        for key in wanted:
            try:
                clean[key] = float(value[key])
            except (KeyError, TypeError, ValueError):
                return None
        return clean
