"""Base class for GUI pages."""

from __future__ import annotations

from typing import Any, Optional

import customtkinter as ctk

from ..core.pipeline import FrameResult
from . import theme


class BasePage(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        self.app = app
        self.palette = app.palette
        super().__init__(master, fg_color=self.palette.get("root", "#0b0f14"), corner_radius=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

    def on_show(self) -> None:
        """Called when the page becomes visible."""

    def on_hide(self) -> None:
        """Called when the page is hidden."""

    def update_view(
        self, result: Optional[FrameResult], status: str, status_message: str
    ) -> None:
        """Called by the main window poll loop while this page is visible."""

    # ---------------------------------------------------------------- helpers
    def card(self, master=None, **kwargs) -> ctk.CTkFrame:
        options = {
            "corner_radius": 12,
            "fg_color": self.palette.get("card", "#141c24"),
            "border_width": 1,
            "border_color": self.palette.get("border", "#23303d"),
        }
        options.update(kwargs)
        return ctk.CTkFrame(master or self, **options)

    def title_label(self, master, text: str, size: int = 14) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            master,
            text=text,
            font=theme.font(size, "bold"),
            text_color=self.palette.get("text", "#eef4f8"),
            anchor="w",
        )

    def muted_label(self, master, text: str, size: int = 11, wrap: int = 360) -> ctk.CTkLabel:
        return ctk.CTkLabel(
            master,
            text=text,
            font=theme.font(size),
            text_color=self.palette.get("text_muted", "#93a4b5"),
            anchor="w",
            justify="left",
            wraplength=wrap,
        )

    def action_button(
        self,
        master,
        text: str,
        command,
        kind: str = "secondary",
        width: int = 130,
        height: int = 36,
    ) -> ctk.CTkButton:
        colors = self.palette
        if kind == "primary":
            fg, hover, text_color = colors["accent"], colors["accent_hover"], "#04140a"
        elif kind == "danger":
            fg, hover, text_color = colors["red_soft"], "#5c1f22", colors["red"]
        else:
            fg, hover, text_color = colors["card_alt"], colors["nav_hover"], colors["text"]
        return ctk.CTkButton(
            master,
            text=text,
            command=command,
            width=width,
            height=height,
            corner_radius=9,
            fg_color=fg,
            hover_color=hover,
            text_color=text_color,
            border_width=1 if kind == "secondary" else 0,
            border_color=colors.get("border", "#23303d"),
            font=theme.font(12, "bold"),
        )
