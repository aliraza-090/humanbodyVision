"""Animated loading indicator used while the camera connects."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..theme import font


class LoadingIndicator(ctk.CTkFrame):
    def __init__(
        self,
        master,
        text: str = "Working",
        palette: Optional[dict[str, str]] = None,
    ) -> None:
        self.palette = palette or {}
        super().__init__(master, fg_color="transparent")
        self._base_text = text
        self._dots = 0
        self._running = False
        self._after_id = None

        self._label = ctk.CTkLabel(
            self,
            text=f"{text}...",
            font=font(12),
            text_color=self.palette.get("text_muted", "#93a4b5"),
        )
        self._label.pack(side="left")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self) -> None:
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def set_text(self, text: str) -> None:
        self._base_text = text
        self._label.configure(text=text)

    def _tick(self) -> None:
        if not self._running or not self.winfo_exists():
            return
        self._dots = (self._dots + 1) % 4
        self._label.configure(text=f"{self._base_text}{'.' * self._dots}")
        self._after_id = self.after(400, self._tick)

    def destroy(self) -> None:
        self.stop()
        super().destroy()
