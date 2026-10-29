"""Settings page with persistent configuration controls."""

from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ..config.defaults import (
    EXERCISE_ARMS,
    RESOLUTIONS,
    SENSITIVITIES,
    THEMES,
)
from ..utils.paths import available_model_variants
from .base_page import BasePage


class SettingsPage(BasePage):
    def __init__(self, master, app) -> None:
        super().__init__(master, app)
        self._widgets: dict[str, object] = {}
        self._build()
        self._load_values()

    # ------------------------------------------------------------------- build
    def _build(self) -> None:
        palette = self.palette
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=palette["border"],
            scrollbar_button_hover_color=palette["text_dim"],
        )
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=(18, 8), pady=(14, 8))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._camera_section()
        self._model_section()
        self._display_section()
        self._exercise_section()
        self._audio_theme_section()

        footer = ctk.CTkFrame(self, fg_color=palette["card"], corner_radius=12,
                              border_width=1, border_color=palette["border"])
        footer.grid(row=1, column=0, sticky="ew", padx=18, pady=(4, 16))
        self.action_button(footer, "Save & Apply", self._save, "primary", 150, 38).pack(
            side="left", padx=12, pady=10
        )
        self.action_button(footer, "Restore Defaults", self._restore, width=150, height=38).pack(
            side="left", padx=4, pady=10
        )
        self._message = ctk.CTkLabel(
            footer, text="Settings are stored locally in your Windows user profile.",
            font=("Segoe UI", 10), text_color=palette["text_dim"],
            anchor="w", wraplength=560, justify="left",
        )
        self._message.pack(side="left", padx=14, pady=10)

    def _section(self, title: str, subtitle: str = "") -> ctk.CTkFrame:
        palette = self.palette
        card = self.card(self.scroll)
        card.grid(
            row=len(self.scroll.grid_slaves()), column=0, sticky="ew",
            padx=4, pady=(0, 10),
        )
        card.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(13, 2))
        ctk.CTkLabel(
            header, text=title.upper(), font=("Segoe UI", 10, "bold"),
            text_color=palette["accent"], anchor="w",
        ).pack(side="left")
        if subtitle:
            ctk.CTkLabel(
                header, text=subtitle, font=("Segoe UI", 10),
                text_color=palette["text_dim"], anchor="w",
            ).pack(side="left", padx=10)
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 12))
        body.grid_columnconfigure(1, weight=1)
        return body

    def _row_label(self, body, row: int, text: str) -> None:
        ctk.CTkLabel(
            body, text=text, font=("Segoe UI", 11, "bold"),
            text_color=self.palette["text_muted"], anchor="w",
        ).grid(row=row, column=0, sticky="w", padx=(4, 20), pady=5)

    def _add_option(self, body, row: int, key: str, label: str, values: list[str], width: int = 190) -> None:
        self._row_label(body, row, label)
        menu = ctk.CTkOptionMenu(
            body, values=values, width=width,
            fg_color=self.palette["input"], button_color=self.palette["accent"],
            button_hover_color=self.palette["accent_hover"], text_color=self.palette["text"],
            dropdown_fg_color=self.palette["card"], dropdown_hover_color=self.palette["nav_hover"],
            dropdown_text_color=self.palette["text"], font=("Segoe UI", 11),
            anchor="w",
        )
        menu.grid(row=row, column=1, sticky="e", padx=4, pady=4)
        self._widgets[key] = menu

    def _add_switch(self, body, row: int, key: str, label: str, hint: str = "") -> None:
        self._row_label(body, row, label)
        holder = ctk.CTkFrame(body, fg_color="transparent")
        holder.grid(row=row, column=1, sticky="e", padx=4, pady=4)
        if hint:
            ctk.CTkLabel(
                holder, text=hint, font=("Segoe UI", 9),
                text_color=self.palette["text_dim"],
            ).pack(side="left", padx=(0, 8))
        switch = ctk.CTkSwitch(
            holder, text="", width=44, progress_color=self.palette["accent"],
        )
        switch.pack(side="right")
        self._widgets[key] = switch

    def _add_slider(
        self, body, row: int, key: str, label: str, low: float, high: float,
        steps: int | None, fmt: str, unit: str = "",
    ) -> None:
        self._row_label(body, row, label)
        holder = ctk.CTkFrame(body, fg_color="transparent")
        holder.grid(row=row, column=1, sticky="ew", padx=4, pady=4)
        holder.grid_columnconfigure(0, weight=1)
        value_label = ctk.CTkLabel(
            holder, text=fmt.format(low), font=("Consolas", 11),
            text_color=self.palette["cyan"], width=70, anchor="e",
        )
        value_label.grid(row=0, column=1, sticky="e", padx=(8, 2))

        def update(value, label=value_label):
            label.configure(text=f"{fmt.format(value)}{unit}")

        slider = ctk.CTkSlider(
            holder, from_=low, to=high, number_of_steps=steps,
            command=update, progress_color=self.palette["accent"],
            button_color=self.palette["accent"], button_hover_color=self.palette["accent_hover"],
            fg_color=self.palette["border"],
        )
        slider.grid(row=0, column=0, sticky="ew")
        self._widgets[key] = (slider, value_label, fmt, unit)

    # ----------------------------------------------------------------- sections
    def _camera_section(self) -> None:
        body = self._section("Camera", "Capture device and stream")
        self._add_option(
            body, 0, "camera_index", "Camera",
            [f"Camera {i}" for i in range(5)],
        )
        self._add_option(
            body, 1, "resolution", "Resolution",
            list(RESOLUTIONS.keys()),
        )
        self._add_slider(body, 2, "max_fps", "Maximum FPS", 10, 60, 50, "{:.0f}", " fps")
        self._add_switch(body, 3, "mirror", "Mirror preview", "Natural selfie view")
        ctk.CTkLabel(
            body,
            text=(
                "Camera 0 is normally the built-in/default webcam. If another application "
                "is using the camera, close it before saving. Changes restart the stream."
            ),
            font=("Segoe UI", 9), text_color=self.palette["text_dim"],
            wraplength=620, justify="left", anchor="w",
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))

    def _model_section(self) -> None:
        body = self._section("Pose engine", "MediaPipe Pose Landmarker")
        variants = available_model_variants() or ["full"]
        labels = {"lite": "Lite - fastest", "full": "Full - recommended", "heavy": "Heavy - most accurate"}
        values = [labels.get(name, name.title()) for name in variants]
        self._add_option(body, 0, "model_variant", "Model", values)
        self._widgets["_model_variants"] = variants
        self._add_slider(
            body, 1, "min_detection_confidence", "Detection confidence", 0.1, 0.95, 17, "{:.2f}"
        )
        self._add_slider(
            body, 2, "min_tracking_confidence", "Tracking confidence", 0.1, 0.95, 17, "{:.2f}"
        )
        self._add_slider(
            body, 3, "min_presence_confidence", "Presence confidence", 0.1, 0.95, 17, "{:.2f}"
        )
        ctk.CTkLabel(
            body,
            text=(
                "Higher confidence filters uncertain landmarks but can drop the body in poor "
                "lighting. Changing the model or confidence restarts pose inference."
            ),
            font=("Segoe UI", 9), text_color=self.palette["text_dim"],
            wraplength=620, justify="left", anchor="w",
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=(4, 0))

    def _display_section(self) -> None:
        body = self._section("Skeleton overlay", "Green body visualization")
        self._add_switch(body, 0, "skeleton_visible", "Show skeleton", "Green lines and joints")
        self._add_slider(body, 1, "skeleton_line_thickness", "Line thickness", 1, 8, 7, "{:.0f}", " px")
        self._add_slider(body, 2, "landmark_dot_size", "Joint dot size", 1, 10, 9, "{:.0f}", " px")
        self._add_slider(
            body, 3, "landmark_visibility_threshold", "Visibility threshold", 0.2, 0.9, 14, "{:.2f}"
        )

    def _exercise_section(self) -> None:
        body = self._section("Exercise & fall detection", "Heuristic thresholds")
        self._add_option(body, 0, "exercise_sensitivity", "Exercise sensitivity", SENSITIVITIES)
        self._add_option(body, 1, "exercise_arm", "Curl arm", EXERCISE_ARMS)
        self._add_option(body, 2, "fall_sensitivity", "Fall sensitivity", SENSITIVITIES)
        self._add_switch(body, 3, "fall_detection_enabled", "Fall detection", "Experimental")
        self._add_switch(body, 4, "audio_feedback", "Audio feedback", "Rep and fall sounds")

    def _audio_theme_section(self) -> None:
        body = self._section("Appearance & privacy", "Local configuration only")
        self._add_option(body, 0, "theme", "Theme (applies on restart)", THEMES)
        ctk.CTkLabel(
            body,
            text=(
                "No camera images are uploaded or recorded. Settings are saved to "
                "%APPDATA%\\humanbodyVision\\settings.json. Restart the application after "
                "changing the theme to rebuild the palette."
            ),
            font=("Segoe UI", 9), text_color=self.palette["text_dim"],
            wraplength=620, justify="left", anchor="w",
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=(6, 0))

    # ------------------------------------------------------------------- values
    def _load_values(self) -> None:
        settings = self.app.controller.settings
        index = int(settings.get("camera_index", 0))
        widget = self._widgets["camera_index"]
        widget.set(f"Camera {index}")

        widget = self._widgets["resolution"]
        widget.set(settings.get("resolution", "1280x720"))

        self._set_slider("max_fps", float(settings.get("max_fps", 30)))

        self._set_switch("mirror", bool(settings.get("mirror", True)))

        variants = self._widgets.get("_model_variants", ["full"])
        labels = {"lite": "Lite - fastest", "full": "Full - recommended", "heavy": "Heavy - most accurate"}
        variant = settings.get("model_variant", "full")
        if variant not in variants:
            variant = variants[0]
        self._widgets["model_variant"].set(labels.get(variant, variant.title()))

        self._set_slider("min_detection_confidence", settings.get("min_detection_confidence", 0.5))
        self._set_slider("min_tracking_confidence", settings.get("min_tracking_confidence", 0.5))
        self._set_slider("min_presence_confidence", settings.get("min_presence_confidence", 0.5))

        self._set_switch("skeleton_visible", bool(settings.get("skeleton_visible", True)))
        self._set_slider("skeleton_line_thickness", settings.get("skeleton_line_thickness", 3))
        self._set_slider("landmark_dot_size", settings.get("landmark_dot_size", 4))
        self._set_slider(
            "landmark_visibility_threshold", settings.get("landmark_visibility_threshold", 0.5)
        )

        self._widgets["exercise_sensitivity"].set(settings.get("exercise_sensitivity", "Balanced"))
        self._widgets["exercise_arm"].set(settings.get("exercise_arm", "Right arm"))
        self._widgets["fall_sensitivity"].set(settings.get("fall_sensitivity", "Balanced"))
        self._set_switch("fall_detection_enabled", bool(settings.get("fall_detection_enabled", True)))
        self._set_switch("audio_feedback", bool(settings.get("audio_feedback", True)))
        self._widgets["theme"].set(settings.get("theme", "Dark"))

    def _set_slider(self, key: str, value: float) -> None:
        slider, label, fmt, unit = self._widgets[key]
        slider.set(float(value))
        label.configure(text=f"{fmt.format(float(value))}{unit}")

    def _set_switch(self, key: str, value: bool) -> None:
        switch = self._widgets[key]
        if value:
            switch.select()
        else:
            switch.deselect()

    def _collect(self) -> dict:
        variants = self._widgets.get("_model_variants", ["full"])
        labels = {"Lite - fastest": "lite", "Full - recommended": "full", "Heavy - most accurate": "heavy"}
        model_label = self._widgets["model_variant"].get()
        variant = labels.get(model_label, variants[0] if variants else "full")

        camera_label = self._widgets["camera_index"].get()
        try:
            camera_index = int(camera_label.replace("Camera", "").strip())
        except ValueError:
            camera_index = 0

        def slider_value(key: str) -> float:
            return float(self._widgets[key][0].get())

        return {
            "camera_index": camera_index,
            "resolution": self._widgets["resolution"].get(),
            "max_fps": int(round(slider_value("max_fps"))),
            "mirror": bool(self._widgets["mirror"].get()),
            "model_variant": variant,
            "min_detection_confidence": round(slider_value("min_detection_confidence"), 2),
            "min_tracking_confidence": round(slider_value("min_tracking_confidence"), 2),
            "min_presence_confidence": round(slider_value("min_presence_confidence"), 2),
            "skeleton_visible": bool(self._widgets["skeleton_visible"].get()),
            "skeleton_line_thickness": int(round(slider_value("skeleton_line_thickness"))),
            "landmark_dot_size": int(round(slider_value("landmark_dot_size"))),
            "landmark_visibility_threshold": round(slider_value("landmark_visibility_threshold"), 2),
            "exercise_sensitivity": self._widgets["exercise_sensitivity"].get(),
            "exercise_arm": self._widgets["exercise_arm"].get(),
            "fall_sensitivity": self._widgets["fall_sensitivity"].get(),
            "fall_detection_enabled": bool(self._widgets["fall_detection_enabled"].get()),
            "audio_feedback": bool(self._widgets["audio_feedback"].get()),
            "theme": self._widgets["theme"].get(),
        }

    # ------------------------------------------------------------------ actions
    def _save(self) -> None:
        settings = self._collect()
        ok, message = self.app.apply_settings(settings)
        self._message.configure(
            text=message, text_color=self.palette["accent"] if ok else self.palette["orange"]
        )

    def _restore(self) -> None:
        ok, message = self.app.restore_defaults()
        self._load_values()
        self._message.configure(
            text=message, text_color=self.palette["accent"] if ok else self.palette["orange"]
        )

    def on_show(self) -> None:
        self._load_values()
