"""Dashboard page: live preview plus all key status cards."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..camera.frame_processor import (
    CONNECTED,
    CONNECTING,
    DISCONNECTED,
    ERROR,
    PAUSED,
    STOPPED,
)
from ..core.pipeline import FrameResult
from .base_page import BasePage
from .camera_view import CameraView
from .components.metric_card import MetricCard
from .components.status_card import StatusCard


class DashboardPage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._build()

    def _build(self) -> None:
        palette = self.palette
        self.grid_columnconfigure(0, weight=1, minsize=460)
        self.grid_columnconfigure(1, weight=0, minsize=390)
        self.grid_rowconfigure(0, weight=1)

        # ------------------------------------------------------------ preview
        preview_card = self.card()
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=(14, 8))
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(preview_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            header,
            text="LIVE BODY TRACKING",
            font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"],
        ).pack(side="left")
        self._live_hint = ctk.CTkLabel(
            header,
            text="Green skeleton = detected pose",
            font=("Segoe UI", 10),
            text_color=palette["text_muted"],
        )
        self._live_hint.pack(side="right")

        self.camera_view = CameraView(preview_card, palette)
        self.camera_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        # -------------------------------------------------------------- cards
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=(14, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)

        self._notice = ctk.CTkLabel(
            right,
            text="",
            font=("Segoe UI", 11),
            text_color=palette["orange"],
            wraplength=360,
            justify="left",
            anchor="w",
        )
        self._notice.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self._notice.grid_remove()

        self.camera_card = StatusCard(
            right, "Camera", "Stopped", "Not started", palette, palette["text_muted"]
        )
        self.body_card = StatusCard(
            right, "Body Detection", "No body", "Waiting for camera", palette, palette["text_muted"]
        )
        self.landmark_card = StatusCard(
            right, "Landmarks", "0 / 33", "Visible joints", palette, palette["cyan"]
        )
        self.activity_card = StatusCard(
            right, "Activity", "--", "Insufficient evidence", palette, palette["accent"]
        )
        self.fps_card = StatusCard(
            right, "Performance", "-- FPS", "Waiting for frames", palette, palette["accent"]
        )
        self.exercise_card = StatusCard(
            right, "Exercise", "Squats", "Session not started", palette, palette["yellow"]
        )
        self.reps_card = StatusCard(
            right, "Repetitions", "0", "Phase: Ready", palette, palette["accent"]
        )
        self.posture_card = StatusCard(
            right, "Posture", "--", "Insufficient visibility", palette, palette["cyan"]
        )

        cards = [
            self.camera_card, self.body_card, self.landmark_card, self.activity_card,
            self.fps_card, self.exercise_card, self.reps_card, self.posture_card,
        ]
        for index, card in enumerate(cards):
            row = 1 + index // 2
            col = index % 2
            card.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)

        tips = ctk.CTkFrame(right, fg_color=palette["card_alt"], corner_radius=10,
                            border_width=1, border_color=palette["border"])
        tips.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=4, pady=(10, 0))
        ctk.CTkLabel(
            tips,
            text="POSITIONING TIP",
            font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"],
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            tips,
            text=(
                "Stand 2-3 metres from the camera with your head, hands and feet "
                "visible. Good front lighting gives the most reliable green skeleton."
            ),
            font=("Segoe UI", 11),
            text_color=palette["text_muted"],
            wraplength=340,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        # ----------------------------------------------------------- controls
        controls = ctk.CTkFrame(self, fg_color=palette["card"], corner_radius=12,
                                border_width=1, border_color=palette["border"])
        controls.grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))

        button_row = ctk.CTkFrame(controls, fg_color="transparent")
        button_row.pack(fill="x", padx=12, pady=10)

        self.start_button = self.action_button(
            button_row, "Start Camera", self.app.start_camera, "primary", width=150
        )
        self.start_button.pack(side="left", padx=(0, 8))
        self.pause_button = self.action_button(
            button_row, "Pause", self.app.toggle_pause, width=110
        )
        self.pause_button.pack(side="left", padx=4)
        self.stop_button = self.action_button(
            button_row, "Stop", self.app.stop_camera, "danger", width=100
        )
        self.stop_button.pack(side="left", padx=4)
        self.skeleton_button = self.action_button(
            button_row, "Hide Skeleton", self.app.toggle_skeleton, width=150
        )
        self.skeleton_button.pack(side="left", padx=4)

        self._control_hint = ctk.CTkLabel(
            button_row,
            text="Ready",
            font=("Segoe UI", 10),
            text_color=palette["text_dim"],
        )
        self._control_hint.pack(side="left", padx=14)

        self.action_button(
            button_row, "Settings", lambda: self.app.show_page("settings"), width=110
        ).pack(side="right")

    # ------------------------------------------------------------------ update
    def on_show(self) -> None:
        self._sync_skeleton_button()
        if self.app.controller.model_error:
            self._notice.configure(
                text=f"Pose engine unavailable: {self.app.controller.model_error}"
            )
            self._notice.grid()
        else:
            self._notice.grid_remove()

    def update_view(
        self, result: Optional[FrameResult], status: str, status_message: str
    ) -> None:
        self._sync_controls(status)
        self._update_preview(result, status, status_message)

        if result is None:
            self.camera_card.set(status, status_message, _status_color(self.palette, status))
            self.body_card.set("No body", "Waiting for camera", self.palette["text_muted"])
            self.landmark_card.set("0 / 33", "Visible joints")
            self.activity_card.set("--", "Insufficient evidence")
            self.fps_card.set("-- FPS", status_message)
            exercise = self.app.controller.exercise_snapshot()
            self.exercise_card.set(exercise.exercise, "Session not started")
            self.reps_card.set(str(exercise.reps), "Press Start in Exercise Monitor")
            self.posture_card.set("--", "Insufficient visibility")
            return

        self.camera_card.set(status, status_message, _status_color(self.palette, status))

        activity = result.activity
        if result.detected:
            self.body_card.set(
                "Body detected",
                f"{result.landmark_count} visible landmarks",
                self.palette["accent"],
            )
        else:
            self.body_card.set("No body", "Step into the camera view", self.palette["orange"])

        self.landmark_card.set(
            f"{result.landmark_count} / {result.landmark_total or 33}",
            f"{result.processing_ms:.1f} ms inference",
        )
        self.activity_card.set(
            activity.label,
            f"{activity.evidence} evidence" if activity.is_known else activity.detail,
            self.palette["accent"] if activity.is_known else self.palette["text_muted"],
        )
        fps_color = (
            self.palette["accent"] if result.fps >= 20
            else self.palette["orange"] if result.fps > 0
            else self.palette["text_muted"]
        )
        self.fps_card.set(f"{result.fps:.1f} FPS", f"{result.processing_ms:.1f} ms per frame", fps_color)

        exercise = result.exercise
        self.exercise_card.set(
            exercise.exercise,
            "Session active" if exercise.running else "Session paused",
            self.palette["yellow"] if exercise.running else self.palette["text_muted"],
        )
        self.reps_card.set(
            str(exercise.reps),
            f"Phase: {exercise.phase}",
            self.palette["accent"] if exercise.reps else self.palette["text_muted"],
        )
        posture = result.posture
        self.posture_card.set(
            _short_posture(posture.status),
            posture.suggestion if posture.status else "Insufficient visibility",
            self.palette["accent"] if posture.is_ok else self.palette["orange"],
        )

        if result.pose_error and self.app.controller.model_error is None:
            self._notice.configure(text=f"Pose engine: {result.pose_error}")
            self._notice.grid()

    # --------------------------------------------------------------- internals
    def _update_preview(
        self, result: Optional[FrameResult], status: str, status_message: str
    ) -> None:
        if status == STOPPED:
            self.camera_view.show_message("Camera stopped", "Press Start Camera to begin")
            return
        if status == PAUSED:
            if result is not None:
                self.camera_view.update_frame(result.frame, result.frame_id)
            self.camera_view.show_overlay("Camera paused", "Press Resume to continue")
            return
        if status in (ERROR, DISCONNECTED):
            title = "Camera disconnected" if status == DISCONNECTED else "Camera error"
            self.camera_view.show_message(title, status_message)
            return
        if result is not None:
            self.camera_view.update_frame(result.frame, result.frame_id)
        else:
            self.camera_view.show_overlay("Connecting to camera", status_message or "Please wait")

    def _sync_controls(self, status: str) -> None:
        running = status not in (STOPPED,)
        paused = status == PAUSED
        try:
            self.start_button.configure(state="disabled" if running else "normal")
            self.pause_button.configure(
                state="normal" if running else "disabled",
                text="Resume" if paused else "Pause",
            )
            self.stop_button.configure(state="normal" if running else "disabled")
        except Exception:
            pass
        self._sync_skeleton_button()
        self._control_hint.configure(
            text={"Connected": "Streaming", "Paused": "Preview frozen"}.get(status, status)
        )

    def _sync_skeleton_button(self) -> None:
        visible = self.app.controller.skeleton_visible
        self.skeleton_button.configure(text="Hide Skeleton" if visible else "Show Skeleton")


def _status_color(palette: dict[str, str], status: str) -> str:
    if status == CONNECTED:
        return palette["accent"]
    if status == PAUSED:
        return palette["yellow"]
    if status in (ERROR, DISCONNECTED):
        return palette["red"]
    if status == CONNECTING:
        return palette["cyan"]
    return palette["text_muted"]


def _short_posture(status: str) -> str:
    mapping = {
        "Aligned": "Aligned",
        "Forward lean detected": "Forward lean",
        "Shoulder asymmetry observed": "Shoulder asymmetry",
        "Head position offset observed": "Head offset",
        "Insufficient visibility": "Insufficient",
    }
    return mapping.get(status, status)
