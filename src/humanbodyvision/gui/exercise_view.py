"""Exercise monitoring page with rep counter and phase feedback."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..camera.frame_processor import DISCONNECTED, ERROR, PAUSED, STOPPED
from ..config.defaults import EXERCISES
from ..core.pipeline import FrameResult
from .base_page import BasePage
from .camera_view import CameraView
from .components.metric_card import MetricCard

GUIDANCE = {
    "Squats": (
        "Face the camera and keep your whole body in frame. Lower until the knees are "
        "clearly bent, then stand tall. The counter only counts a rep after you reach "
        "the bottom range and return to standing."
    ),
    "Bicep Curls": (
        "Choose one arm and keep that elbow visible. Start with the arm extended, curl "
        "your hand toward the shoulder, then lower fully. Keep your elbow close to your "
        "side so the camera sees a clean angle."
    ),
    "Jumping Jacks": (
        "Show your arms and feet for the whole set. Start with arms down and feet "
        "together, open both arms overhead with feet apart, then close again. Full "
        "open/close cycles are counted."
    ),
}


class ExercisePage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._build()

    def _build(self) -> None:
        palette = self.palette
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=370)
        self.grid_rowconfigure(0, weight=1)

        preview_card = self.card()
        preview_card.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=(14, 8))
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            preview_card, text="EXERCISE MONITOR", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        self.camera_view = CameraView(preview_card, palette)
        self.camera_view.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=(14, 8))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(4, weight=1)

        selector = self.card(right)
        selector.grid(row=0, column=0, sticky="ew")
        selector.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            selector, text="Exercise", font=("Segoe UI", 11, "bold"),
            text_color=palette["text_muted"], anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(14, 8), pady=(12, 4))
        self.exercise_menu = ctk.CTkOptionMenu(
            selector,
            values=EXERCISES,
            command=self._on_exercise_change,
            width=170,
            fg_color=palette["input"],
            button_color=palette["accent"],
            button_hover_color=palette["accent_hover"],
            text_color=palette["text"],
            dropdown_fg_color=palette["card"],
            dropdown_hover_color=palette["nav_hover"],
            dropdown_text_color=palette["text"],
            font=("Segoe UI", 11),
        )
        self.exercise_menu.grid(row=0, column=1, sticky="e", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            selector, text="Arm", font=("Segoe UI", 11, "bold"),
            text_color=palette["text_muted"], anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=(14, 8), pady=(0, 12))
        self.arm_menu = ctk.CTkOptionMenu(
            selector,
            values=["Right arm", "Left arm"],
            command=self._on_arm_change,
            width=170,
            fg_color=palette["input"],
            button_color=palette["accent"],
            button_hover_color=palette["accent_hover"],
            text_color=palette["text"],
            dropdown_fg_color=palette["card"],
            dropdown_hover_color=palette["nav_hover"],
            dropdown_text_color=palette["text"],
            font=("Segoe UI", 11),
        )
        self.arm_menu.grid(row=1, column=1, sticky="e", padx=12, pady=(0, 10))

        metrics = ctk.CTkFrame(right, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        metrics.grid_columnconfigure(0, weight=1)
        metrics.grid_columnconfigure(1, weight=1)
        self.reps_card = MetricCard(
            metrics, "Repetitions", "0", "reps", "Completed full-range reps",
            palette, color=palette["accent"],
        )
        self.reps_card.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.time_card = MetricCard(
            metrics, "Session Time", "00:00", "", "Paused time excluded",
            palette, color=palette["cyan"],
        )
        self.time_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        state_card = self.card(right)
        state_card.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        state_card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            state_card, text="MOVEMENT PHASE", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(11, 0))
        self.phase = ctk.CTkLabel(
            state_card, text="Ready", font=("Segoe UI", 18, "bold"),
            text_color=palette["yellow"], anchor="e",
        )
        self.phase.grid(row=0, column=1, sticky="e", padx=14, pady=(8, 0))
        self.angle = ctk.CTkLabel(
            state_card, text="Joint angle: --", font=("Consolas", 11),
            text_color=palette["text_muted"], anchor="w",
        )
        self.angle.grid(row=1, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 0))
        self.feedback = ctk.CTkLabel(
            state_card, text="Press Start to begin", font=("Segoe UI", 11),
            text_color=palette["text_muted"], anchor="w", wraplength=320, justify="left",
        )
        self.feedback.grid(row=2, column=0, columnspan=2, sticky="ew", padx=14, pady=(4, 12))

        controls = self.card(right)
        controls.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        button_row = ctk.CTkFrame(controls, fg_color="transparent")
        button_row.pack(fill="x", padx=10, pady=10)
        self.start_button = self.action_button(
            button_row, "Start", self.app.start_exercise, "primary", width=100
        )
        self.start_button.pack(side="left", padx=(0, 6))
        self.pause_button = self.action_button(
            button_row, "Pause", self.app.pause_exercise, width=100
        )
        self.pause_button.pack(side="left", padx=3)
        self.action_button(button_row, "Reset", self.app.reset_exercise, "danger", width=90).pack(
            side="left", padx=3
        )

        guidance = ctk.CTkFrame(right, fg_color=palette["card_alt"], corner_radius=10,
                                border_width=1, border_color=palette["border"])
        guidance.grid(row=4, column=0, sticky="new", pady=(10, 0))
        ctk.CTkLabel(
            guidance, text="HOW TO PERFORM", font=("Segoe UI", 10, "bold"),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        self.guidance = ctk.CTkLabel(
            guidance, text=GUIDANCE["Squats"], font=("Segoe UI", 10),
            text_color=palette["text_muted"], wraplength=320, justify="left", anchor="w",
        )
        self.guidance.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkLabel(
            guidance,
            text="Fitness aid only. Joint-angle thresholds are not a clinical assessment.",
            font=("Segoe UI", 9), text_color=palette["text_dim"],
            wraplength=320, justify="left", anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

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

    # ------------------------------------------------------------------ events
    def on_show(self) -> None:
        settings = self.app.controller.settings
        self.exercise_menu.set(settings.get("exercise", "Squats"))
        self.arm_menu.set(settings.get("exercise_arm", "Right arm"))
        self.guidance.configure(text=GUIDANCE.get(settings.get("exercise", "Squats"), ""))
        self._sync_exercise_buttons()

    def _on_exercise_change(self, value: str) -> None:
        self.app.select_exercise(value)
        self.guidance.configure(text=GUIDANCE.get(value, ""))

    def _on_arm_change(self, value: str) -> None:
        self.app.select_exercise_arm(value)

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

        exercise = result.exercise if result is not None else self.app.controller.exercise_snapshot()
        self.reps_card.set(str(exercise.reps), f"{exercise.reps} completed repetition(s)")
        minutes, seconds = divmod(int(exercise.elapsed), 60)
        self.time_card.set(f"{minutes:02d}:{seconds:02d}", "Session running" if exercise.running else "Session stopped")
        self.phase.configure(text=exercise.phase)
        self.angle.configure(
            text=(
                f"Primary joint angle: {exercise.angle:.1f} deg"
                if exercise.angle is not None else "Primary joint angle: --"
            )
        )
        self.feedback.configure(
            text=exercise.visibility_warning or exercise.feedback,
            text_color=(
                self.palette["orange"] if exercise.visibility_warning
                else self.palette["text_muted"]
            ),
        )
        self._sync_exercise_buttons(exercise.running)

    def _sync_exercise_buttons(self, running: bool | None = None) -> None:
        if running is None:
            running = self.app.controller.exercise_snapshot().running
        self.start_button.configure(text="Resume" if not running else "Start",
                                    state="disabled" if running else "normal")
        self.pause_button.configure(state="normal" if running else "disabled")
