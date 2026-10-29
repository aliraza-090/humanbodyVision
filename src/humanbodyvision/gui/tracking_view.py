"""Live body tracking page with detailed landmark visibility."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..camera.frame_processor import CONNECTED, ERROR, DISCONNECTED, PAUSED, STOPPED
from ..core import landmark_geometry as geo
from ..core.pipeline import FrameResult
from .base_page import BasePage
from .camera_view import CameraView
from .components.status_card import StatusCard


KEY_LANDMARKS = [
    ("Nose", geo.NOSE),
    ("Left shoulder", geo.LEFT_SHOULDER),
    ("Right shoulder", geo.RIGHT_SHOULDER),
    ("Left elbow", geo.LEFT_ELBOW),
    ("Right elbow", geo.RIGHT_ELBOW),
    ("Left wrist", geo.LEFT_WRIST),
    ("Right wrist", geo.RIGHT_WRIST),
    ("Left hip", geo.LEFT_HIP),
    ("Right hip", geo.RIGHT_HIP),
    ("Left knee", geo.LEFT_KNEE),
    ("Right knee", geo.RIGHT_KNEE),
    ("Left ankle", geo.LEFT_ANKLE),
    ("Right ankle", geo.RIGHT_ANKLE),
]


class TrackingPage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._build()

    def _build(self) -> None:
        palette = self.palette
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=330)
        self.grid_rowconfigure(0, weight=1)

        preview_card = self.card()
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=(14, 8))
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(preview_card, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            head, text="LIVE BODY TRACKING", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"],
        ).pack(side="left")
        self._resolution_label = ctk.CTkLabel(
            head, text="", font=("Segoe UI", 10), text_color=palette["text_muted"]
        )
        self._resolution_label.pack(side="right")

        self.camera_view = CameraView(preview_card, palette)
        self.camera_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=(14, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)

        self.status_card = StatusCard(right, "Camera", "Stopped", "Not started", palette,
                                      palette["text_muted"], width=150, height=80)
        self.detect_card = StatusCard(right, "Detection", "No body", "0 visible", palette,
                                      palette["text_muted"], width=150, height=80)
        self.fps_card = StatusCard(right, "Frame Rate", "-- FPS", "0 ms", palette,
                                   palette["text_muted"], width=150, height=80)
        self.skeleton_card = StatusCard(right, "Skeleton", "On", "Green overlay", palette,
                                        palette["accent"], width=150, height=80)
        self.status_card.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self.detect_card.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)
        self.fps_card.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self.skeleton_card.grid(row=1, column=1, sticky="nsew", padx=4, pady=4)

        details = self.card(right)
        details.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=4, pady=(10, 0))
        details.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            details, text="LANDMARK VISIBILITY", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 6))

        self._landmark_labels: dict[int, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        for row, (name, index) in enumerate(KEY_LANDMARKS, start=1):
            ctk.CTkLabel(
                details, text=name, font=("Segoe UI", 11), text_color=palette["text_muted"],
                anchor="w",
            ).grid(row=row, column=0, sticky="w", padx=(12, 4), pady=1)
            value = ctk.CTkLabel(
                details, text="--", font=("Consolas", 11), text_color=palette["text_dim"],
                anchor="e",
            )
            value.grid(row=row, column=1, sticky="e", padx=(4, 12), pady=1)
            self._landmark_labels[index] = (value, value)

        note = ctk.CTkLabel(
            details,
            text=(
                "Landmarks are normalized image coordinates from MediaPipe. Low-visibility "
                "joints are hidden from the skeleton to avoid misleading lines."
            ),
            font=("Segoe UI", 10),
            text_color=palette["text_dim"],
            wraplength=300,
            justify="left",
            anchor="w",
        )
        note.grid(row=len(KEY_LANDMARKS) + 1, column=0, columnspan=2, sticky="ew",
                  padx=12, pady=(8, 10))

        controls = ctk.CTkFrame(self, fg_color=palette["card"], corner_radius=12,
                                border_width=1, border_color=palette["border"])
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))
        row = ctk.CTkFrame(controls, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)
        self.action_button(row, "Start Camera", self.app.start_camera, "primary", 140).pack(side="left", padx=(0, 8))
        self._pause = self.action_button(row, "Pause", self.app.toggle_pause, width=105)
        self._pause.pack(side="left", padx=4)
        self.action_button(row, "Stop", self.app.stop_camera, "danger", 95).pack(side="left", padx=4)
        self._skeleton_button = self.action_button(
            row, "Hide Skeleton", self.app.toggle_skeleton, width=145
        )
        self._skeleton_button.pack(side="left", padx=4)
        self._hint = ctk.CTkLabel(
            row, text="", font=("Segoe UI", 10), text_color=palette["text_dim"]
        )
        self._hint.pack(side="left", padx=12)

    def on_show(self) -> None:
        self._skeleton_button.configure(
            text="Hide Skeleton" if self.app.controller.skeleton_visible else "Show Skeleton"
        )

    def update_view(self, result: Optional[FrameResult], status: str, status_message: str) -> None:
        self._pause.configure(text="Resume" if status == PAUSED else "Pause")
        self._hint.configure(text=status_message)
        self._skeleton_button.configure(
            text="Hide Skeleton" if self.app.controller.skeleton_visible else "Show Skeleton"
        )
        self.status_card.set(status, status_message, _status_color(self.palette, status))
        self.skeleton_card.set(
            "On" if self.app.controller.skeleton_visible else "Hidden",
            "Green overlay" if self.app.controller.skeleton_visible else "Overlay disabled",
            self.palette["accent"] if self.app.controller.skeleton_visible else self.palette["text_muted"],
        )

        if status == STOPPED:
            self.camera_view.show_message("Camera stopped", "Press Start Camera to begin")
        elif status == PAUSED:
            if result is not None:
                self.camera_view.update_frame(result.frame, result.frame_id)
            self.camera_view.show_overlay("Camera paused", "Press Resume to continue")
        elif status in (ERROR, DISCONNECTED):
            self.camera_view.show_message("Camera unavailable", status_message)
        elif result is not None:
            self.camera_view.update_frame(result.frame, result.frame_id)

        if result is None:
            self.detect_card.set("No body", "Waiting for frames", self.palette["text_muted"])
            self.fps_card.set("-- FPS", "0 ms", self.palette["text_muted"])
            for label, _ in self._landmark_labels.values():
                label.configure(text="--", text_color=self.palette["text_dim"])
            self._resolution_label.configure(text="")
            return

        self.detect_card.set(
            "Body detected" if result.detected else "No body",
            f"{result.landmark_count} visible landmarks",
            self.palette["accent"] if result.detected else self.palette["orange"],
        )
        self.fps_card.set(f"{result.fps:.1f} FPS", f"{result.processing_ms:.1f} ms",
                          self.palette["accent"] if result.fps >= 20 else self.palette["orange"])
        self._resolution_label.configure(
            text=f"{result.frame_width}x{result.frame_height} | mirrored"
            if self.app.controller.settings.get("mirror", True)
            else f"{result.frame_width}x{result.frame_height}"
        )

        threshold = float(self.app.controller.settings.get("landmark_visibility_threshold", 0.5))
        for index, (label, _) in self._landmark_labels.items():
            point = geo.landmark(result.landmarks, index)
            score = geo.visibility(point) if point is not None else 0.0
            label.configure(
                text=f"{score * 100:3.0f}%",
                text_color=(
                    self.palette["accent"] if score >= threshold
                    else self.palette["orange"] if score > 0.1
                    else self.palette["text_dim"]
                ),
            )


def _status_color(palette: dict[str, str], status: str) -> str:
    if status == CONNECTED:
        return palette["accent"]
    if status == PAUSED:
        return palette["yellow"]
    if status in (ERROR, DISCONNECTED):
        return palette["red"]
    return palette["text_muted"]
