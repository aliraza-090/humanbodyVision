"""Reusable large metric card."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..theme import font


class MetricCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        label: str,
        value: str = "--",
        unit: str = "",
        hint: str = "",
        palette: Optional[dict[str, str]] = None,
        color: Optional[str] = None,
    ) -> None:
        self.palette = palette or {}
        self._color = color or self.palette.get("text", "#eef4f8")
        super().__init__(
            master,
            corner_radius=12,
            fg_color=self.palette.get("card", "#141c24"),
            border_width=1,
            border_color=self.palette.get("border", "#23303d"),
        )
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=label.upper(),
            font=font(10, "bold"),
            text_color=self.palette.get("text_dim", "#66788c"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(11, 0))

        value_row = ctk.CTkFrame(self, fg_color="transparent")
        value_row.grid(row=1, column=0, sticky="ew", padx=14)

        self._value = ctk.CTkLabel(
            value_row,
            text=value,
            font=font(28, "bold"),
            text_color=self._color,
            anchor="w",
        )
        self._value.pack(side="left")

        self._unit = ctk.CTkLabel(
            value_row,
            text=unit,
            font=font(12),
            text_color=self.palette.get("text_muted", "#93a4b5"),
            anchor="sw",
        )
        self._unit.pack(side="left", padx=(5, 0), pady=(0, 5))

        self._hint = ctk.CTkLabel(
            self,
            text=hint,
            font=font(10),
            text_color=self.palette.get("text_muted", "#93a4b5"),
            anchor="w",
            wraplength=300,
            justify="left",
        )
        self._hint.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 11))

    def set(self, value: str, hint: str | None = None, color: str | None = None) -> None:
        self._value.configure(text=value, text_color=color or self._color)
        if hint is not None:
            self._hint.configure(text=hint)

    def set_unit(self, unit: str) -> None:
        self._unit.configure(text=unit)
