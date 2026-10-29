"""GUI metadata and import smoke tests.

No window is created here, so the tests run on headless CI machines. They still
verify that every page module imports and that navigation metadata stays in
sync with the registered page classes.
"""

from __future__ import annotations

import re

import pytest

import humanbodyvision.gui.activity_view  # noqa: F401
import humanbodyvision.gui.dashboard  # noqa: F401
import humanbodyvision.gui.exercise_view  # noqa: F401
import humanbodyvision.gui.fall_view  # noqa: F401
import humanbodyvision.gui.instructions_view  # noqa: F401
import humanbodyvision.gui.posture_view  # noqa: F401
import humanbodyvision.gui.settings_view  # noqa: F401
import humanbodyvision.gui.tracking_view  # noqa: F401
from humanbodyvision.gui import theme
from humanbodyvision.gui.main_window import NAV_ITEMS, PAGE_META


def test_navigation_keys_are_unique_and_covered_by_metadata():
    keys = [key for key, _, _ in NAV_ITEMS]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(PAGE_META)
    for key, label, icon in NAV_ITEMS:
        assert key and label and icon
        assert PAGE_META[key][0] == label


def test_dark_and_light_palettes_share_the_same_colour_slots():
    dark = theme.PALETTES["Dark"]
    light = theme.PALETTES["Light"]
    assert set(dark) == set(light)
    for name, value in dark.items():
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), name
    for name, value in light.items():
        assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), name


def test_palette_lookup_and_default():
    assert theme.palette("Light") is theme.PALETTES["Light"]
    assert theme.palette("Dark") is theme.PALETTES["Dark"]
    assert theme.palette("System") is theme.PALETTES["Dark"]
    assert theme.palette() is theme.PALETTES["Dark"]


def test_palette_has_required_semantic_colours():
    for mode in ("Dark", "Light"):
        palette = theme.palette(mode)
        for slot in (
            "root", "sidebar", "card", "text", "text_muted", "accent",
            "accent_hover", "cyan", "yellow", "red", "input", "preview_bg",
        ):
            assert slot in palette
        assert palette["accent"] != palette["red"]


def test_theme_font_helpers_return_fonts():
    # CTkFont requires a Tk root in some CustomTkinter builds; skip cleanly if
    # the headless environment cannot construct one.
    try:
        regular = theme.font(12)
        mono = theme.mono_font(12, "bold")
    except Exception as exc:  # pragma: no cover - depends on Tk availability
        pytest.skip(f"Tk font creation unavailable: {exc}")
    assert regular is not None
    assert mono is not None


def test_every_page_has_expected_hooks():
    from humanbodyvision.gui.activity_view import ActivityPage
    from humanbodyvision.gui.dashboard import DashboardPage
    from humanbodyvision.gui.exercise_view import ExercisePage
    from humanbodyvision.gui.fall_view import FallPage
    from humanbodyvision.gui.instructions_view import InstructionsPage
    from humanbodyvision.gui.posture_view import PosturePage
    from humanbodyvision.gui.settings_view import SettingsPage
    from humanbodyvision.gui.tracking_view import TrackingPage

    classes = {
        "dashboard": DashboardPage,
        "tracking": TrackingPage,
        "activity": ActivityPage,
        "exercise": ExercisePage,
        "posture": PosturePage,
        "fall": FallPage,
        "settings": SettingsPage,
        "instructions": InstructionsPage,
    }
    assert set(classes) == set(PAGE_META)
    for page_class in classes.values():
        assert callable(getattr(page_class, "update_view", None))
