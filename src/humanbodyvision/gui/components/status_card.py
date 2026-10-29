"""Reusable status card widget."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..theme import font


class StatusCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        title: str,
        value: str = "--",
        detail: str = "",
        palette: Optional[dict[str, str]] = None,
        accent: Optional[str] = None,
        width: int = 170,
        height: int = 82,
    ) -> None:
        self.palette = palette or {}
        self._accent = accent or self.palette.get("accent", "#22c55e")
        super().__init__(
            master,
            width=width,
            height=height,
            corner_radius=10,
            fg_color=self.palette.get("card", "#141c24"),
            border_width=1,
            border_color=self.palette.get("border", "#23303d"),
        )
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)

        self._title = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=font(10, "bold"),
            text_color=self.palette.get("text_dim", "#66788c"),
            anchor="w",
        )
        self._title.grid(row=0, column=0, sticky="ew", padx=12, pady=(9, 0))

        self._value = ctk.CTkLabel(
            self,
            text=value,
            font=font(19, "bold"),
            text_color=self._accent,
            anchor="w",
        )
        self._value.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 0))

        self._detail = ctk.CTkLabel(
            self,
            text=detail,
            font=font(10),
            text_color=self.palette.get("text_muted", "#93a4b5"),
            anchor="w",
        )
        self._detail.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

    def set(self, value: str, detail: str = "", color: str | None = None) -> None:
        self._value.configure(text=value, text_color=color or self._accent)
        self._detail.configure(text=detail)

    def set_color(self, color: str) -> None:
        self._accent = color
        self._value.configure(text_color=color)

    def set_title(self, title: str) -> None:
        self._title.configure(text=title.upper())
