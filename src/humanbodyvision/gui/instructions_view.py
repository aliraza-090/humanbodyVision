"""Instructions and About page."""

from __future__ import annotations

import customtkinter as ctk

from .. import __version__
from .base_page import BasePage


class InstructionsPage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._build()

    def _build(self) -> None:
        palette = self.palette
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=palette["border"],
            scrollbar_button_hover_color=palette["text_dim"],
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=(14, 16))
        scroll.grid_columnconfigure(0, weight=1)

        hero = self.card(scroll)
        hero.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 10))
        ctk.CTkLabel(
            hero,
            text="humanbodyVision",
            font=("Segoe UI", 28, "bold"),
            text_color=palette["text"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=(18, 0))
        ctk.CTkLabel(
            hero,
            text="AI-Powered Human Body Tracking & Activity Recognition",
            font=("Segoe UI", 13),
            text_color=palette["accent"],
            anchor="w",
        ).pack(fill="x", padx=20)
        ctk.CTkLabel(
            hero,
            text=f"Developed by Ali Raza Chakrani  |  Version {__version__}  |  Fully offline",
            font=("Segoe UI", 11),
            text_color=palette["text_muted"],
            anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 18))

        self._section(
            scroll, "Quick start",
            "1. Open Settings and choose the camera, resolution and mirror preference.\n"
            "2. Return to the Dashboard and press Start Camera.\n"
            "3. Allow Windows camera access if prompted.\n"
            "4. Stand 2-3 metres away so your head, hands and feet are in frame.\n"
            "5. The bright green skeleton should follow your body in real time.\n"
            "6. Use Exercise Monitor to choose an exercise, then press Start and perform "
            "full-range repetitions.\n"
            "7. Use Posture Analysis to calibrate a neutral reference posture if desired.",
            index=1,
        )
        self._section(
            scroll, "Body tracking & skeleton",
            "humanbodyVision uses MediaPipe Pose Landmarker in video mode. Up to 33 body "
            "landmarks are tracked: face, shoulders, elbows, wrists, hips, knees, ankles, "
            "heels and feet. Lines are only drawn between joints with sufficient visibility, "
            "so a partially visible body does not produce misleading limbs. The preview is "
            "mirrored for natural interaction while the underlying inference still uses the "
            "camera frame.\n\n"
            "Bright green lines represent bones. Cyan dots are joints. Yellow joints are "
            "active in the current exercise or activity. Orange/red points indicate a posture "
            "warning or a possible fall. Skeleton thickness, dot size and visibility threshold "
            "are configurable in Settings.",
            index=2,
        )
        self._section(
            scroll, "Activity recognition",
            "Activities are inferred from joint angles and motion over roughly one second. "
            "Supported labels: Standing, Sitting, Walking in place, Raising arm, Squatting, "
            "Bending and Unknown. Evidence (Strong/Moderate/Weak) reflects rule agreement, "
            "not a statistical probability. Results are smoothed to avoid label flicker. "
            "This is a heuristic system: camera angle, occlusion, loose clothing and unusual "
            "poses can produce incorrect labels.",
            index=3,
        )
        self._section(
            scroll, "Exercise counting",
            "Squats use the average knee angle and require a deep bend followed by a return to "
            "standing. Bicep curls use the selected arm's elbow angle and require full flexion "
            "and extension. Jumping jacks require both wrists above the shoulders with feet "
            "apart, followed by arms down and feet together. Sensitivity presets adjust the "
            "angle thresholds. Partial reps and rapid jitter are rejected. These counters are "
            "fitness aids and are not clinically validated.",
            index=4,
        )
        self._section(
            scroll, "Posture and fall detection",
            "Posture analysis reports shoulder tilt, torso inclination and head offset relative "
            "to a neutral calibration. It uses neutral labels and does not diagnose medical "
            "conditions. Fall detection is experimental: it requires multiple temporal signals "
            "such as a rapid hip drop, a change to a horizontal torso and sustained low posture. "
            "It cannot replace supervision, medical devices or emergency services and does not "
            "automatically contact anyone.",
            index=5,
        )
        self._section(
            scroll, "Privacy",
            "All frame processing happens on this computer. Camera images are never uploaded, "
            "recorded or transmitted. There are no accounts, telemetry, cloud APIs or automatic "
            "screenshots. Settings and logs are stored under %APPDATA%\\humanbodyVision. "
            "The pose model files are bundled for offline use.",
            index=6,
        )
        self._section(
            scroll, "Troubleshooting",
            "Camera will not open: close other video apps, check Windows camera privacy "
            "permissions, then press Stop and Start again.\n\n"
            "No skeleton but video is visible: make sure you are in frame, improve lighting, "
            "and confirm the pose engine is loaded (the Dashboard shows a notice if the model "
            "is missing).\n\n"
            "Low frame rate: choose the Lite model, lower the resolution to 640x480, or lower "
            "the maximum FPS in Settings.\n\n"
            "Skeleton misaligned: toggle mirror in Settings to match your expectation. The "
            "overlay is intentionally mirrored to behave like a mirror.\n\n"
            "Model missing: run scripts/download_model.py or reinstall with the bundled model, "
            "then restart the application.",
            index=7,
        )
        self._section(
            scroll, "Known limitations",
            "Pose quality depends on lighting, camera placement and body visibility. Activity "
            "recognition is rule-based, not a trained classifier. Exercise counting supports "
            "squats, bicep curls and jumping jacks only; push-ups are not implemented. Fall "
            "detection is experimental and unvalidated. Posture analysis is geometric only and "
            "is not a medical assessment. The application has been tested with synthetic "
            "landmark sequences; real webcam validation depends on the user's hardware and "
            "environment.",
            index=8,
        )

        footer = ctk.CTkFrame(scroll, fg_color=palette["card"], corner_radius=12,
                              border_width=1, border_color=palette["border"])
        footer.grid(row=9, column=0, sticky="ew", padx=4, pady=(0, 10))
        ctk.CTkLabel(
            footer,
            text=(
                "humanbodyVision  |  MIT License  |  MediaPipe Pose Landmarker  |  "
                "OpenCV  |  CustomTkinter  |  Developed by Ali Raza Chakrani"
            ),
            font=("Segoe UI", 10),
            text_color=palette["text_dim"],
            wraplength=900,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=16, pady=14)

    def _section(self, master, title: str, body: str, index: int = 0) -> None:
        palette = self.palette
        card = self.card(master)
        card.grid(row=index, column=0, sticky="ew", padx=4, pady=(0, 10))
        ctk.CTkLabel(
            card, text=title.upper(), font=("Segoe UI", 10, "bold"),
            text_color=palette["accent"], anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            card, text=body, font=("Segoe UI", 11),
            text_color=palette["text_muted"], justify="left", anchor="w",
            wraplength=900,
        ).pack(fill="x", padx=16, pady=(0, 12))
