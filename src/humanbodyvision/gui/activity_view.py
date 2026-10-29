"""Activity recognition page with temporal evidence and activity log."""

from __future__ import annotations

import time
from typing import Optional

import customtkinter as ctk

from ..camera.frame_processor import CONNECTED, DISCONNECTED, ERROR, PAUSED, STOPPED
from ..core.pipeline import FrameResult
from .base_page import BasePage
from .camera_view import CameraView
from .components.metric_card import MetricCard


class ActivityPage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._last_logged: str | None = None
        self._build()

    def _build(self) -> None:
        palette = self.palette
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=380)
        self.grid_rowconfigure(0, weight=1)

        preview_card = self.card()
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=(14, 8))
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            preview_card, text="ACTIVITY RECOGNITION", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        self.camera_view = CameraView(preview_card, palette)
        self.camera_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=(14, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(4, weight=1)

        hero = self.card(right)
        hero.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            hero, text="CURRENT ACTIVITY", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 0))
        self.activity_value = ctk.CTkLabel(
            hero, text="Unknown", font=("Segoe UI", 30, "bold"),
            text_color=palette["text_muted"], anchor="w",
        )
        self.activity_value.pack(fill="x", padx=16)
        self.activity_detail = ctk.CTkLabel(
            hero, text="Step into view to begin", font=("Segoe UI", 12),
            text_color=palette["text_muted"], anchor="w", wraplength=330, justify="left",
        )
        self.activity_detail.pack(fill="x", padx=16, pady=(0, 4))
        self.evidence = ctk.CTkLabel(
            hero, text="Evidence: none", font=("Segoe UI", 11, "bold"),
            text_color=palette["text_dim"], anchor="w",
        )
        self.evidence.pack(fill="x", padx=16, pady=(0, 14))

        metrics = ctk.CTkFrame(right, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        metrics.grid_columnconfigure(0, weight=1)
        metrics.grid_columnconfigure(1, weight=1)
        self.motion_card = MetricCard(
            metrics, "Motion Energy", "--", "body units/s",
            "Movement across tracked joints", palette, color=palette["cyan"],
        )
        self.motion_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.leg_card = MetricCard(
            metrics, "Leg Alternation", "--", "/s",
            "Left/right ankle swings", palette, color=palette["yellow"],
        )
        self.leg_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        history_card = self.card(right)
        history_card.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        ctk.CTkLabel(
            history_card, text="ACTIVITY HISTORY", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=14, pady=(11, 4))
        self.log = ctk.CTkTextbox(
            history_card, height=150, corner_radius=8,
            fg_color=palette["input"], border_width=1, border_color=palette["border"],
            text_color=palette["text_muted"], font=("Consolas", 11), activate_scrollbars=True,
        )
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.log.insert("1.0", "Activity changes will appear here.\n")
        self.log.configure(state="disabled")

        info = ctk.CTkFrame(right, fg_color=palette["card_alt"], corner_radius=10,
                            border_width=1, border_color=palette["border"])
        info.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(
            info,
            text="RULE-BASED, NOT A TRAINED CLASSIFIER",
            font=("Segoe UI", 10, "bold"),
            text_color=palette["orange"],
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            info,
            text=(
                "Labels come from joint angles and short-term motion, smoothed over about "
                "one second. Evidence describes rule agreement, not a statistical "
                "probability. Occlusion, loose clothing, floor-level cameras and unusual "
                "poses can produce wrong labels."
            ),
            font=("Segoe UI", 10),
            text_color=palette["text_muted"],
            wraplength=330,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))
        self.action_button(controls, "Start Camera", self.app.start_camera, "primary", 140).pack(side="left")
        self._pause = self.action_button(controls, "Pause", self.app.toggle_pause, width=105)
        self._pause.pack(side="left", padx=8)
        self.action_button(controls, "Stop", self.app.stop_camera, "danger", 95).pack(side="left")
        self._status = ctk.CTkLabel(
            controls, text="", font=("Segoe UI", 10), text_color=palette["text_dim"]
        )
        self._status.pack(side="left", padx=14)

    def on_show(self) -> None:
        self._last_logged = None

    def update_view(self, result: Optional[FrameResult], status: str, status_message: str) -> None:
        self._pause.configure(text="Resume" if status == PAUSED else "Pause")
        self._status.configure(text=status_message)

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
            self.activity_value.configure(text="Unknown", text_color=self.palette["text_muted"])
            self.activity_detail.configure(text="No frames received yet.")
            self.evidence.configure(text="Evidence: none", text_color=self.palette["text_dim"])
            self.motion_card.set("--", "Waiting for frames")
            self.leg_card.set("--", "Waiting for frames")
            return

        activity = result.activity
        color = self.palette["accent"] if activity.is_known else self.palette["text_muted"]
        self.activity_value.configure(text=activity.label, text_color=color)
        self.activity_detail.configure(text=activity.detail)
        self.evidence.configure(
            text=f"Evidence: {activity.evidence.lower() if activity.evidence else 'none'}",
            text_color={
                "Strong": self.palette["accent"],
                "Moderate": self.palette["yellow"],
                "Weak": self.palette["orange"],
            }.get(activity.evidence, self.palette["text_dim"]),
        )

        motion = result.motion
        self.motion_card.set(
            f"{motion.motion_energy:.2f}" if motion.valid else "--",
            "Short-window motion across core joints",
        )
        self.leg_card.set(
            f"{motion.ankle_alternation_hz:.1f}" if motion.valid else "--",
            "Alternating ankle rhythm (walking cue)",
        )

        if activity.is_known and activity.label != self._last_logged:
            self._append_log(activity.label, activity.evidence)
            self._last_logged = activity.label

    def _append_log(self, label: str, evidence: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"{timestamp}  {label}  [{evidence}]\n")
        self.log.see("end")
        self.log.configure(state="disabled")
