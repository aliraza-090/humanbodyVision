"""Experimental fall detection page."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..camera.frame_processor import DISCONNECTED, ERROR, PAUSED, STOPPED
from ..config.defaults import SENSITIVITIES
from ..core.pipeline import FrameResult
from .base_page import BasePage
from .camera_view import CameraView
from .components.metric_card import MetricCard


class FallPage(BasePage):
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
            preview_card, text="FALL DETECTION (EXPERIMENTAL)", font=("Segoe UI", 10, "bold"),
            text_color=palette["orange"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        self.camera_view = CameraView(preview_card, palette)
        self.camera_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=(14, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)

        warning = ctk.CTkFrame(right, fg_color=palette["red_soft"], corner_radius=10,
                               border_width=1, border_color=palette["red"])
        warning.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(
            warning, text="EXPERIMENTAL - NOT A SAFETY DEVICE",
            font=("Segoe UI", 10, "bold"), text_color=palette["red"], anchor="w",
        ).pack(fill="x", padx=12, pady=(9, 2))
        ctk.CTkLabel(
            warning,
            text=(
                "This heuristic can miss real falls and raise false alarms. It does not "
                "contact emergency services. Never rely on it for someone at risk."
            ),
            font=("Segoe UI", 10), text_color=palette["text_muted"], wraplength=330,
            justify="left", anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 9))

        self.alert_banner = ctk.CTkFrame(right, fg_color=palette["red_soft"], corner_radius=10,
                                         border_width=1, border_color=palette["red"])
        self.alert_banner.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.alert_title = ctk.CTkLabel(
            self.alert_banner, text="Monitoring for falls", font=("Segoe UI", 16, "bold"),
            text_color=palette["text_muted"], anchor="w",
        )
        self.alert_title.pack(fill="x", padx=14, pady=(10, 0))
        self.alert_detail = ctk.CTkLabel(
            self.alert_banner, text="No alert active", font=("Segoe UI", 10),
            text_color=palette["text_muted"], anchor="w",
        )
        self.alert_detail.pack(fill="x", padx=14, pady=(0, 3))
        self.dismiss_button = self.action_button(
            self.alert_banner, "Dismiss Alert", self.app.dismiss_fall, width=130, height=32
        )
        self.dismiss_button.pack(anchor="w", padx=14, pady=(0, 10))
        self.dismiss_button.configure(state="disabled")

        config = self.card(right)
        config.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        config.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            config, text="Detection enabled", font=("Segoe UI", 11, "bold"),
            text_color=palette["text_muted"], anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(10, 4))
        self.enabled_switch = ctk.CTkSwitch(
            config, text="", command=self._on_toggle, progress_color=palette["accent"],
        )
        self.enabled_switch.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            config, text="Sensitivity", font=("Segoe UI", 11, "bold"),
            text_color=palette["text_muted"], anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 10))
        self.sensitivity_menu = ctk.CTkOptionMenu(
            config, values=SENSITIVITIES, command=self._on_sensitivity, width=150,
            fg_color=palette["input"], button_color=palette["accent"],
            button_hover_color=palette["accent_hover"], text_color=palette["text"],
            dropdown_fg_color=palette["card"], dropdown_hover_color=palette["nav_hover"],
            dropdown_text_color=palette["text"], font=("Segoe UI", 11),
        )
        self.sensitivity_menu.grid(row=1, column=1, sticky="e", padx=12, pady=(0, 8))

        metrics = ctk.CTkFrame(right, fg_color="transparent")
        metrics.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        metrics.grid_columnconfigure(0, weight=1)
        metrics.grid_columnconfigure(1, weight=1)
        self.torso_card = MetricCard(
            metrics, "Torso Angle", "--", "deg", "Horizontal suggests lying down",
            palette, color=palette["cyan"],
        )
        self.torso_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.drop_card = MetricCard(
            metrics, "Hip Speed", "--", "fr/s", "Rapid downward motion signal",
            palette, color=palette["orange"],
        )
        self.drop_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        signals_card = self.card(right)
        signals_card.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(
            signals_card, text="ACTIVE SIGNALS", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 2))
        self.signals_label = ctk.CTkLabel(
            signals_card, text="No fall signals detected.",
            font=("Segoe UI", 10), text_color=palette["text_muted"], anchor="w",
            wraplength=330, justify="left",
        )
        self.signals_label.pack(fill="x", padx=14, pady=(0, 10))

        note = ctk.CTkFrame(right, fg_color=palette["card_alt"], corner_radius=10,
                            border_width=1, border_color=palette["border"])
        note.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(
            note, text="HOW IT WORKS", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=12, pady=(9, 2))
        ctk.CTkLabel(
            note,
            text=(
                "The detector looks for a rapid hip drop, an upright-to-horizontal torso "
                "change and sustained low posture. Two concurrent signals are required, "
                "followed by a cooldown. Sensitivity changes the thresholds and cooldown. "
                "Normal sitting and bending are rejected where possible, but this is not "
                "validated against real fall data."
            ),
            font=("Segoe UI", 9), text_color=palette["text_muted"], wraplength=330,
            justify="left", anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 9))

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
        settings = self.app.controller.settings
        if settings.get("fall_detection_enabled", True):
            self.enabled_switch.select()
        else:
            self.enabled_switch.deselect()
        self.sensitivity_menu.set(settings.get("fall_sensitivity", "Balanced"))

    def _on_toggle(self) -> None:
        self.app.set_fall_enabled(bool(self.enabled_switch.get()))

    def _on_sensitivity(self, value: str) -> None:
        self.app.set_fall_sensitivity(value)

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
            self.alert_title.configure(text="Monitoring inactive", text_color=self.palette["text_muted"])
            self.alert_detail.configure(text="Start the camera to monitor.")
            self.dismiss_button.configure(state="disabled")
            self.torso_card.set("--")
            self.drop_card.set("--")
            self.signals_label.configure(text="No fall signals detected.")
            return

        fall = result.fall
        if fall.alert_active:
            self.alert_banner.configure(
                fg_color=self.palette["red_soft"], border_color=self.palette["red"]
            )
            self.alert_title.configure(
                text="Possible Fall Detected", text_color=self.palette["red"]
            )
            self.alert_detail.configure(
                text=fall.message, text_color=self.palette["text"]
            )
            self.dismiss_button.configure(state="normal")
        elif not fall.enabled:
            self.alert_title.configure(text="Fall detection disabled",
                                       text_color=self.palette["text_muted"])
            self.alert_detail.configure(text="Enable it to start monitoring.")
            self.dismiss_button.configure(state="disabled")
        else:
            self.alert_title.configure(text="Monitoring for falls",
                                       text_color=self.palette["accent"])
            self.alert_detail.configure(text=fall.message, text_color=self.palette["text_muted"])
            self.dismiss_button.configure(state="disabled")

        self.torso_card.set(
            f"{fall.torso_inclination:.1f}" if fall.torso_inclination is not None else "--",
            "Torso angle from vertical",
        )
        self.drop_card.set(
            f"{fall.rapid_drop:.2f}" if fall.monitored else "--",
            "Largest recent hip drop speed",
        )
        if fall.signals:
            self.signals_label.configure(
                text="\n".join(f"- {signal}" for signal in fall.signals),
                text_color=self.palette["orange"],
            )
        else:
            self.signals_label.configure(
                text="No fall signals detected." if fall.enabled else "Monitoring disabled.",
                text_color=self.palette["text_muted"],
            )
