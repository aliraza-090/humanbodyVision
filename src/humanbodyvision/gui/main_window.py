"""Main application window: sidebar navigation, header and page polling."""

from __future__ import annotations

import time
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
from ..utils.feedback import play_fall_alert, play_rep_chime
from ..utils.logger import get_logger
from ..utils.paths import asset_path
from . import theme
from .activity_view import ActivityPage
from .dashboard import DashboardPage
from .exercise_view import ExercisePage
from .fall_view import FallPage
from .instructions_view import InstructionsPage
from .posture_view import PosturePage
from .settings_view import SettingsPage
from .tracking_view import TrackingPage

log = get_logger("gui")

NAV_ITEMS = [
    ("dashboard", "Dashboard", "⌂"),
    ("tracking", "Live Body Tracking", "◉"),
    ("activity", "Activity Recognition", "≈"),
    ("exercise", "Exercise Monitor", "▲"),
    ("posture", "Posture Analysis", "◆"),
    ("fall", "Fall Detection", "⚠"),
    ("settings", "Settings", "⚙"),
    ("instructions", "Instructions / About", "ⓘ"),
]

PAGE_META = {
    "dashboard": ("Dashboard", "Real-time body tracking at a glance"),
    "tracking": ("Live Body Tracking", "Full-body pose and landmark visibility"),
    "activity": ("Activity Recognition", "Interpretable labels from pose and motion"),
    "exercise": ("Exercise Monitor", "Repetition counting and movement phases"),
    "posture": ("Posture Analysis", "Neutral geometric posture feedback"),
    "fall": ("Fall Detection", "Experimental multi-signal monitoring"),
    "settings": ("Settings", "Camera, model and interface configuration"),
    "instructions": ("Instructions / About", "Usage, privacy and limitations"),
}


class MainWindow(ctk.CTk):
    def __init__(self, controller) -> None:
        self.controller = controller
        self.palette = theme.palette(controller.settings.get("theme", "Dark"))
        ctk.set_appearance_mode(
            "light" if controller.settings.get("theme") == "Light" else "dark"
        )
        ctk.set_default_color_theme("green")
        super().__init__(fg_color=self.palette["root"])

        self.title("humanbodyVision - AI-Powered Human Body Tracking")
        self.minsize(1100, 680)
        self.geometry(_centered_geometry(self, 1400, 900))
        self._set_icon()

        self.pages: dict[str, object] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.current_page = "dashboard"
        self._last_result: Optional[FrameResult] = None
        self._last_status: tuple[str, str] | None = None
        self._last_rep_seq: int | None = None
        self._last_fall_seq: int | None = None
        self._poll_after_id = None
        self._closing = False

        self._build_layout()
        self.show_page("dashboard")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll()

    # ----------------------------------------------------------------- layout
    def _set_icon(self) -> None:
        icon = asset_path("icons", "icon.ico")
        if icon.exists():
            try:
                self.iconbitmap(str(icon))
            except Exception:
                log.debug("Could not set window icon", exc_info=True)

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()

        main = ctk.CTkFrame(self, fg_color=self.palette["root"], corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(1, weight=1)
        main.grid_columnconfigure(0, weight=1)

        self._build_header(main)

        self.page_container = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
        self.page_container.grid(row=1, column=0, sticky="nsew")
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

        page_classes = {
            "dashboard": DashboardPage,
            "tracking": TrackingPage,
            "activity": ActivityPage,
            "exercise": ExercisePage,
            "posture": PosturePage,
            "fall": FallPage,
            "settings": SettingsPage,
            "instructions": InstructionsPage,
        }
        for key, page_class in page_classes.items():
            page = page_class(self.page_container, self)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page

    def _build_sidebar(self) -> None:
        palette = self.palette
        sidebar = ctk.CTkFrame(
            self, width=232, corner_radius=0, fg_color=palette["sidebar"],
            border_width=0,
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(2, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(22, 8))
        ctk.CTkLabel(
            brand, text="humanbodyVision", font=("Segoe UI", 19, "bold"),
            text_color=palette["text"], anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            brand, text="AI-Powered Human Body Tracking", font=("Segoe UI", 9),
            text_color=palette["text_dim"], anchor="w",
        ).pack(fill="x", pady=(1, 0))

        nav = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="new", padx=12, pady=(14, 0))
        nav.grid_columnconfigure(0, weight=1)
        for index, (key, label, icon) in enumerate(NAV_ITEMS):
            button = ctk.CTkButton(
                nav,
                text=f"  {icon}   {label}",
                anchor="w",
                height=40,
                corner_radius=9,
                fg_color="transparent",
                hover_color=palette["nav_hover"],
                text_color=palette["text_muted"],
                font=("Segoe UI", 12),
                command=lambda page_key=key: self.show_page(page_key),
            )
            button.grid(row=index, column=0, sticky="ew", pady=2)
            self.nav_buttons[key] = button

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="sew", padx=18, pady=(10, 18))
        footer.grid_columnconfigure(1, weight=1)

        self._offline_dot = ctk.CTkLabel(
            footer, text="●", font=("Segoe UI", 10), text_color=palette["accent"],
        )
        self._offline_dot.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            footer, text="Offline / on-device", font=("Segoe UI", 9, "bold"),
            text_color=palette["text_muted"], anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(4, 0))

        self._model_status = ctk.CTkLabel(
            footer,
            text="Pose model loaded" if not self.controller.model_error else "Pose model unavailable",
            font=("Segoe UI", 9),
            text_color=palette["accent"] if not self.controller.model_error else palette["orange"],
            anchor="w",
            wraplength=190,
            justify="left",
        )
        self._model_status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 0))

        ctk.CTkFrame(footer, height=1, fg_color=palette["border"]).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=10
        )
        ctk.CTkLabel(
            footer, text="Developed by", font=("Segoe UI", 9),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=3, column=0, columnspan=2, sticky="w")
        ctk.CTkLabel(
            footer, text="Ali Raza Chakrani", font=("Segoe UI", 11, "bold"),
            text_color=palette["text"], anchor="w",
        ).grid(row=4, column=0, columnspan=2, sticky="w")
        ctk.CTkLabel(
            footer, text="v1.0.0", font=("Segoe UI", 9),
            text_color=palette["text_dim"], anchor="w",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 0))

    def _build_header(self, main) -> None:
        palette = self.palette
        header = ctk.CTkFrame(main, fg_color="transparent", corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(15, 2))
        header.grid_columnconfigure(0, weight=1)

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.grid(row=0, column=0, sticky="w")
        self.page_title = ctk.CTkLabel(
            titles, text="Dashboard", font=("Segoe UI", 22, "bold"),
            text_color=palette["text"], anchor="w",
        )
        self.page_title.pack(anchor="w")
        self.page_subtitle = ctk.CTkLabel(
            titles, text="Real-time body tracking at a glance", font=("Segoe UI", 11),
            text_color=palette["text_muted"], anchor="w",
        )
        self.page_subtitle.pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")
        self.status_dot = ctk.CTkLabel(
            right, text="●", font=("Segoe UI", 14), text_color=palette["text_dim"],
        )
        self.status_dot.pack(side="left", padx=(0, 4))
        self.status_text = ctk.CTkLabel(
            right, text="Stopped", font=("Segoe UI", 11, "bold"),
            text_color=palette["text_muted"],
        )
        self.status_text.pack(side="left")

        ctk.CTkLabel(
            right, text="   Developed by Ali Raza Chakrani", font=("Segoe UI", 10),
            text_color=palette["text_dim"],
        ).pack(side="left", padx=(10, 0))

    # -------------------------------------------------------------- navigation
    def show_page(self, key: str) -> None:
        if key not in self.pages:
            return
        if self.current_page in self.pages and self.current_page != key:
            try:
                self.pages[self.current_page].on_hide()
            except Exception:
                log.debug("on_hide failed", exc_info=True)
        self.current_page = key
        page = self.pages[key]
        page.tkraise()
        try:
            page.on_show()
        except Exception:
            log.debug("on_show failed", exc_info=True)

        title, subtitle = PAGE_META.get(key, (key, ""))
        self.page_title.configure(text=title)
        self.page_subtitle.configure(text=subtitle)

        for nav_key, button in self.nav_buttons.items():
            active = nav_key == key
            button.configure(
                fg_color=self.palette["nav_active"] if active else "transparent",
                text_color=self.palette["accent"] if active else self.palette["text_muted"],
                font=("Segoe UI", 12, "bold") if active else ("Segoe UI", 12),
            )

    # ----------------------------------------------------------------- actions
    def start_camera(self) -> None:
        self.controller.start_camera()
        self._last_status = None

    def stop_camera(self) -> None:
        self.controller.stop_camera()
        self._last_result = None
        self._last_status = None

    def toggle_pause(self) -> None:
        self.controller.toggle_pause()
        self._last_status = None

    def toggle_skeleton(self) -> None:
        visible = self.controller.toggle_skeleton()
        log.info("Skeleton visibility: %s", visible)
        self._last_status = None

    def select_exercise(self, name: str) -> None:
        self.controller.select_exercise(name)

    def select_exercise_arm(self, arm: str) -> None:
        self.controller.select_exercise_arm(arm)

    def start_exercise(self) -> None:
        self.controller.start_exercise()

    def pause_exercise(self) -> None:
        self.controller.pause_exercise()

    def reset_exercise(self) -> None:
        self.controller.reset_exercise()

    def calibrate_posture(self) -> tuple[bool, str]:
        return self.controller.calibrate_posture()

    def reset_posture_calibration(self) -> None:
        self.controller.reset_posture_calibration()

    def dismiss_fall(self) -> None:
        self.controller.dismiss_fall()

    def set_fall_enabled(self, enabled: bool) -> None:
        self.controller.set_fall_enabled(enabled)

    def set_fall_sensitivity(self, sensitivity: str) -> None:
        self.controller.set_fall_sensitivity(sensitivity)

    def apply_settings(self, values: dict) -> tuple[bool, str]:
        previous_theme = self.controller.settings.get("theme", "Dark")
        ok, message = self.controller.apply_settings(values)
        if ok and values.get("theme") != previous_theme:
            message += " Theme will be fully applied after restarting the application."
        self._last_status = None
        return ok, message

    def restore_defaults(self) -> tuple[bool, str]:
        return self.controller.restore_defaults()

    # -------------------------------------------------------------------- poll
    def _poll(self) -> None:
        if self._closing:
            return
        try:
            processor = self.controller.processor
            status, message = processor.status()
            result = processor.drain_result()

            if result is not None:
                self._last_result = result
                self._handle_audio(result)
            if status == STOPPED:
                self._last_result = None

            self._update_status(status, message)

            page = self.pages.get(self.current_page)
            if page is not None:
                display = result if result is not None else self._last_result
                page.update_view(display, status, message)
        except Exception:
            log.exception("GUI poll failed")
        finally:
            if not self._closing:
                self._poll_after_id = self.after(33, self._poll)

    def _handle_audio(self, result: FrameResult) -> None:
        if self._last_rep_seq is None:
            self._last_rep_seq = result.rep_event_seq
            self._last_fall_seq = result.fall_event_seq
            return
        audio = bool(self.controller.settings.get("audio_feedback", True))
        if result.rep_event_seq > self._last_rep_seq:
            if audio:
                play_rep_chime()
            self._last_rep_seq = result.rep_event_seq
        if result.fall_event_seq > (self._last_fall_seq or 0):
            if audio:
                play_fall_alert()
            self._last_fall_seq = result.fall_event_seq

    def _update_status(self, status: str, message: str) -> None:
        if self._last_status == (status, message):
            return
        self._last_status = (status, message)
        color = {
            CONNECTED: self.palette["accent"],
            CONNECTING: self.palette["cyan"],
            PAUSED: self.palette["yellow"],
            DISCONNECTED: self.palette["red"],
            ERROR: self.palette["red"],
            STOPPED: self.palette["text_dim"],
        }.get(status, self.palette["text_dim"])
        self.status_dot.configure(text_color=color)
        self.status_text.configure(text=status, text_color=color)

        if self.controller.model_error:
            self._model_status.configure(
                text=f"Pose model unavailable: {self.controller.model_error}",
                text_color=self.palette["orange"],
            )
        elif status == CONNECTED:
            self._model_status.configure(
                text="Pose model loaded", text_color=self.palette["accent"]
            )

    # ------------------------------------------------------------------- close
    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:
                pass
        try:
            self.controller.shutdown()
        except Exception:
            log.exception("Error during shutdown")
        try:
            self.destroy()
        except Exception:
            pass


def _centered_geometry(window: ctk.CTk, width: int, height: int) -> str:
    try:
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        # High-DPI displays often report a smaller logical screen than the
        # requested 1400x900 window. Keep the whole window on screen.
        width = max(1100, min(width, int(screen_w * 0.94)))
        height = max(680, min(height, int(screen_h * 0.90)))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        return f"{width}x{height}+{x}+{y}"
    except Exception:
        return f"{width}x{height}"
