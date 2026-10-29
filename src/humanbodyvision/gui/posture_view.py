"""Posture analysis page."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..camera.frame_processor import DISCONNECTED, ERROR, PAUSED, STOPPED
from ..core.pipeline import FrameResult
from .base_page import BasePage
from .camera_view import CameraView
from .components.metric_card import MetricCard


class PosturePage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
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
            preview_card, text="POSTURE ANALYSIS", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        self.camera_view = CameraView(preview_card, palette)
        self.camera_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=(14, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)
        right.grid_rowconfigure(5, weight=1)

        hero = self.card(right)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(
            hero, text="POSTURE STATUS", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=16, pady=(14, 0))
        self.status_value = ctk.CTkLabel(
            hero, text="Insufficient visibility", font=("Segoe UI", 22, "bold"),
            text_color=palette["text_muted"], anchor="w",
        )
        self.status_value.pack(fill="x", padx=16)
        self.status_detail = ctk.CTkLabel(
            hero, text="Position your upper body in view", font=("Segoe UI", 11),
            text_color=palette["text_muted"], anchor="w", wraplength=330, justify="left",
        )
        self.status_detail.pack(fill="x", padx=16, pady=(2, 14))

        self.shoulder_card = MetricCard(
            right, "Shoulder Tilt", "--", "deg", "Relative to horizontal",
            palette, color=palette["cyan"],
        )
        self.shoulder_card.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(10, 0))
        self.torso_card = MetricCard(
            right, "Torso Lean", "--", "deg", "From vertical",
            palette, color=palette["cyan"],
        )
        self.torso_card.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(10, 0))
        self.head_card = MetricCard(
            right, "Head Offset", "--", "ratio", "Nose vs shoulder centre",
            palette, color=palette["cyan"],
        )
        self.head_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        calibration = self.card(right)
        calibration.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        calibration.grid_columnconfigure(0, weight=1)
        self.calibration_state = ctk.CTkLabel(
            calibration, text="No neutral calibration saved", font=("Segoe UI", 11),
            text_color=palette["text_muted"], anchor="w",
        )
        self.calibration_state.grid(row=0, column=0, columnspan=2, sticky="ew",
                                    padx=14, pady=(10, 4))
        self.action_button(
            calibration, "Calibrate Neutral Posture", self._calibrate, "primary", 200, 34
        ).grid(row=1, column=0, sticky="w", padx=10, pady=(2, 10))
        self.action_button(
            calibration, "Clear", self._reset_calibration, width=80, height=34
        ).grid(row=1, column=1, sticky="e", padx=10, pady=(2, 10))

        suggestion = ctk.CTkFrame(right, fg_color=palette["card_alt"], corner_radius=10,
                                  border_width=1, border_color=palette["border"])
        suggestion.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(
            suggestion, text="GENERAL GUIDANCE", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=12, pady=(9, 2))
        self.suggestion = ctk.CTkLabel(
            suggestion, text="Analysis will appear once your shoulders and hips are visible.",
            font=("Segoe UI", 10), text_color=palette["text_muted"], wraplength=330,
            justify="left", anchor="w",
        )
        self.suggestion.pack(fill="x", padx=12, pady=(0, 5))
        ctk.CTkLabel(
            suggestion,
            text=(
                "This is not a medical assessment. Camera angle, clothing and perspective "
                "distort posture measurements. It cannot diagnose spinal or health conditions."
            ),
            font=("Segoe UI", 9), text_color=palette["text_dim"], wraplength=330,
            justify="left", anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 9))

        self.calibration_message = ctk.CTkLabel(
            right, text="", font=("Segoe UI", 10), text_color=palette["text_dim"],
            anchor="w", wraplength=340, justify="left",
        )
        self.calibration_message.grid(row=5, column=0, columnspan=2, sticky="new", pady=(6, 0))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))
        self.action_button(footer, "Start Camera", self.app.start_camera, "primary", 140).pack(side="left")
        self._pause_camera = self.action_button(footer, "Pause Camera", self.app.toggle_pause, width=130)
        self._pause_camera.pack(side="left", padx=8)
        self.action_button(footer, "Stop", self.app.stop_camera, "danger", 95).pack(side="left")
        self._status = ctk.CTkLabel(
            footer, text="", font=("Segoe UI", 10), text_color=palette["text_dim"]
        )
        self._status.pack(side="left", padx=14)

    def on_show(self) -> None:
        self._refresh_calibration_state()

    def _refresh_calibration_state(self) -> None:
        calibration = self.app.controller.settings.get("posture_calibration")
        if calibration:
            self.calibration_state.configure(
                text=(
                    "Neutral calibration active  |  shoulder "
                    f"{calibration.get('shoulder_tilt', 0):.1f} deg, torso "
                    f"{calibration.get('torso_inclination', 0):.1f} deg"
                ),
                text_color=self.palette["accent"],
            )
        else:
            self.calibration_state.configure(
                text="No neutral calibration saved", text_color=self.palette["text_muted"]
            )

    def _calibrate(self) -> None:
        success, message = self.app.calibrate_posture()
        self.calibration_message.configure(
            text=message,
            text_color=self.palette["accent"] if success else self.palette["orange"],
        )
        self._refresh_calibration_state()

    def _reset_calibration(self) -> None:
        self.app.reset_posture_calibration()
        self.calibration_message.configure(
            text="Neutral calibration cleared.", text_color=self.palette["text_muted"]
        )
        self._refresh_calibration_state()

    def update_view(self, result: Optional[FrameResult], status: str, status_message: str) -> None:
        self._pause_camera.configure(text="Resume Camera" if status == PAUSED else "Pause Camera")
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
            self.status_value.configure(text="Insufficient visibility",
                                        text_color=self.palette["text_muted"])
            self.status_detail.configure(text="No frames received yet.")
            self.shoulder_card.set("--")
            self.torso_card.set("--")
            self.head_card.set("--")
            return

        posture = result.posture
        color = self.palette["accent"] if posture.is_ok else self.palette["orange"]
        if posture.status == "Insufficient visibility":
            color = self.palette["text_muted"]
        self.status_value.configure(text=posture.status, text_color=color)
        calibration_note = "Calibrated baseline active" if posture.calibrated else "Uncalibrated baseline"
        self.status_detail.configure(
            text=f"Visibility: {posture.visibility}  |  {calibration_note}"
        )
        self.shoulder_card.set(
            f"{posture.shoulder_tilt:.1f}" if posture.shoulder_tilt is not None else "--",
            "Absolute tilt of the shoulder line",
        )
        self.torso_card.set(
            f"{posture.torso_inclination:.1f}" if posture.torso_inclination is not None else "--",
            "Shoulder-to-hip axis from vertical",
        )
        self.head_card.set(
            f"{posture.head_offset:.2f}" if posture.head_offset is not None else "--",
            "Horizontal nose offset in torso units",
        )
        self.suggestion.configure(text=posture.suggestion)
