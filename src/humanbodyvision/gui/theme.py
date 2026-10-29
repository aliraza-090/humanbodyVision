"""GUI palette and typography for humanbodyVision."""

from __future__ import annotations

import customtkinter as ctk

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Consolas"

PALETTES: dict[str, dict[str, str]] = {
    "Dark": {
        "root": "#0b0f14",
        "sidebar": "#0e141b",
        "card": "#141c24",
        "card_alt": "#101820",
        "border": "#23303d",
        "text": "#eef4f8",
        "text_muted": "#93a4b5",
        "text_dim": "#66788c",
        "accent": "#22c55e",
        "accent_hover": "#16a34a",
        "accent_soft": "#123524",
        "cyan": "#22d3ee",
        "yellow": "#facc15",
        "orange": "#fb923c",
        "red": "#f87171",
        "red_soft": "#3a1618",
        "input": "#0f1720",
        "nav_hover": "#17222d",
        "nav_active": "#123322",
        "preview_bg": "#05080c",
    },
    "Light": {
        "root": "#eef3f7",
        "sidebar": "#ffffff",
        "card": "#ffffff",
        "card_alt": "#f5f8fb",
        "border": "#d5e0ea",
        "text": "#12212e",
        "text_muted": "#526579",
        "text_dim": "#7c8fa3",
        "accent": "#15803d",
        "accent_hover": "#166534",
        "accent_soft": "#dcfce7",
        "cyan": "#0e7490",
        "yellow": "#a16207",
        "orange": "#c2410c",
        "red": "#b91c1c",
        "red_soft": "#fee2e2",
        "input": "#f8fafc",
        "nav_hover": "#edf3f8",
        "nav_active": "#dcfce7",
        "preview_bg": "#0b1015",
    },
}


def palette(theme: str = "Dark") -> dict[str, str]:
    if theme == "Light":
        return PALETTES["Light"]
    return PALETTES["Dark"]


def font(size: int = 13, weight: str = "normal", family: str = FONT_FAMILY) -> ctk.CTkFont:
    return ctk.CTkFont(family=family, size=size, weight=weight)


def mono_font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FAMILY, size=size, weight=weight)
