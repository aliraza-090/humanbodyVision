"""Filesystem path resolution tests (bundled resources and user data)."""

from __future__ import annotations

from pathlib import Path

from humanbodyvision.utils import paths


def test_resource_root_is_the_package_directory():
    root = paths.bundle_root()
    assert root.name == "humanbodyvision"
    assert (root / "resources").is_dir()


def test_bundled_models_are_discoverable():
    variants = paths.available_model_variants()
    assert "full" in variants
    assert "lite" in variants
    model = paths.model_path("full")
    assert model.exists()
    assert model.suffix == ".task"
    assert model.stat().st_size > 1_000_000


def test_icon_resource_exists():
    icon = paths.asset_path("icons", "icon.ico")
    assert icon.exists()
    assert icon.stat().st_size > 0


def test_app_data_dir_honours_environment_override(tmp_path, monkeypatch):
    monkeypatch.setenv("HUMANBODYVISION_DATA_DIR", str(tmp_path / "custom"))
    data = paths.app_data_dir()
    assert data == tmp_path / "custom"
    assert data.is_dir()
    assert paths.settings_path() == data / "settings.json"
    assert paths.log_dir() == data / "logs"
