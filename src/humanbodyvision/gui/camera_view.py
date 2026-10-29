"""Live camera preview widget with aspect-preserving letterboxing."""

from __future__ import annotations

from typing import Optional

import cv2
import customtkinter as ctk
import numpy as np
from PIL import Image

from .theme import font


class CameraView(ctk.CTkFrame):
    """Displays pipeline frames (BGR) at ~30 FPS without cropping."""

    def __init__(
        self,
        master,
        palette: dict[str, str],
        min_width: int = 320,
        min_height: int = 240,
    ) -> None:
        self.palette = palette
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._label = ctk.CTkLabel(
            self,
            text="",
            fg_color=palette.get("preview_bg", "#05080c"),
            corner_radius=12,
            width=min_width,
            height=min_height,
        )
        self._label.grid(row=0, column=0, sticky="nsew")

        self._overlay = ctk.CTkFrame(
            self,
            fg_color=palette.get("card", "#141c24"),
            corner_radius=12,
            border_width=1,
            border_color=palette.get("border", "#23303d"),
        )
        self._overlay_title = ctk.CTkLabel(
            self._overlay,
            text="Camera stopped",
            font=font(18, "bold"),
            text_color=palette.get("text", "#eef4f8"),
        )
        self._overlay_title.pack(padx=28, pady=(18, 2))
        self._overlay_detail = ctk.CTkLabel(
            self._overlay,
            text="Press Start Camera",
            font=font(11),
            text_color=palette.get("text_muted", "#93a4b5"),
            wraplength=420,
            justify="center",
        )
        self._overlay_detail.pack(padx=28, pady=(0, 18))

        self._image_ref = None
        self._frame: Optional[np.ndarray] = None
        self._last_frame_id: int = -1
        self._last_size: tuple[int, int] = (0, 0)
        self._show_overlay(True, "Camera stopped", "Press Start Camera")
        self._label.bind("<Configure>", self._on_resize)
        self._render_after_id = None

    # ------------------------------------------------------------------ public
    def update_frame(self, frame: Optional[np.ndarray], frame_id: int = -1) -> None:
        if frame is None:
            return
        size_changed = self._current_size() != self._last_size
        if frame_id == self._last_frame_id and not size_changed:
            return
        self._frame = frame
        self._last_frame_id = frame_id
        self._render()
        self._show_overlay(False)

    def show_message(self, title: str, detail: str = "") -> None:
        self._frame = None
        self._last_frame_id = -1
        self._show_overlay(True, title, detail)

    def show_overlay(self, title: str, detail: str = "") -> None:
        self._show_overlay(True, title, detail)

    def clear(self) -> None:
        self._label.configure(image=None, text="")
        self._image_ref = None
        self._show_overlay(True, "Camera stopped", "Press Start Camera")

    @property
    def has_frame(self) -> bool:
        return self._frame is not None

    # --------------------------------------------------------------- internals
    def _on_resize(self, _event=None) -> None:
        if self._frame is not None:
            self._render()

    def _current_size(self) -> tuple[int, int]:
        width = max(64, self._label.winfo_width())
        height = max(64, self._label.winfo_height())
        return width, height

    def _render(self) -> None:
        if self._frame is None:
            return
        target_w, target_h = self._current_size()
        if target_w < 40 or target_h < 40:
            return
        self._last_size = (target_w, target_h)
        try:
            rgb = cv2.cvtColor(self._frame, cv2.COLOR_BGR2RGB)
        except cv2.error:
            return
        image = Image.fromarray(rgb)

        # Fit inside the label, preserving the camera aspect ratio.
        scale = min(target_w / image.width, target_h / image.height)
        new_w = max(1, int(image.width * scale))
        new_h = max(1, int(image.height * scale))
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
        canvas = Image.new("RGB", (target_w, target_h), (5, 8, 12))
        canvas.paste(image, ((target_w - new_w) // 2, (target_h - new_h) // 2))

        ctk_image = ctk.CTkImage(
            light_image=canvas, dark_image=canvas, size=(target_w, target_h)
        )
        self._image_ref = ctk_image
        self._label.configure(image=ctk_image, text="")

    def _show_overlay(self, visible: bool, title: str = "", detail: str = "") -> None:
        if visible:
            self._overlay_title.configure(text=title)
            self._overlay_detail.configure(text=detail)
            self._overlay.place(relx=0.5, rely=0.5, anchor="center")
            self._overlay.lift()
        else:
            self._overlay.place_forget()
