"""Filesystem helpers used by humanbodyVision.

The application keeps all of its mutable data outside the installation folder
so it works when installed under Program Files, and so that user settings,
logs and calibration never end up in source control.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "humanbodyVision"


def is_frozen() -> bool:
    """Return True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Directory that contains bundled resources (works frozen and from source)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # paths.py lives in <package>/utils, so the package root is two levels up.
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Resolve a path inside the packaged resources folder."""
    return bundle_root().joinpath("resources", *parts)


def app_data_dir() -> Path:
    """Per-user configuration directory (%APPDATA%/humanbodyVision on Windows)."""
    base = os.environ.get("HUMANBODYVISION_DATA_DIR")
    if base:
        path = Path(base)
    elif os.name == "nt":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = Path(root) / APP_DIR_NAME
    else:
        path = Path(os.path.expanduser("~")) / ".config" / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def models_dir() -> Path:
    """Preferred writable model location, falling back to the bundled folder."""
    bundled = resource_path("models")
    if bundled.exists():
        return bundled
    local = app_data_dir() / "models"
    local.mkdir(parents=True, exist_ok=True)
    return local


MODEL_FILES = {
    "lite": "pose_landmarker_lite.task",
    "full": "pose_landmarker_full.task",
    "heavy": "pose_landmarker_heavy.task",
}


def model_path(variant: str = "full") -> Path:
    """Return the path for a pose model variant, checking bundled and user dirs."""
    filename = MODEL_FILES.get(variant, MODEL_FILES["full"])
    for directory in (resource_path("models"), app_data_dir() / "models"):
        candidate = directory / filename
        if candidate.exists():
            return candidate
    return resource_path("models") / filename


def available_model_variants() -> list[str]:
    return [name for name, filename in MODEL_FILES.items()
            if resource_path("models", filename).exists()
            or (app_data_dir() / "models" / filename).exists()]


def asset_path(*parts: str) -> Path:
    return resource_path(*parts)
