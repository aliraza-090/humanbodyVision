"""Application controller and entry point.

Owns the settings, pose pipeline and camera workers, and exposes a small API to
the GUI so widgets never touch worker threads directly.
"""

from __future__ import annotations

import sys
import threading
from typing import Optional

from .camera.frame_processor import FrameProcessor
from .config.defaults import DEFAULT_SETTINGS
from .config.settings_manager import SettingsManager
from .core.pipeline import Pipeline
from .core.pose_detector import ModelInitError, ModelNotFoundError, PoseDetector
from .core.exercise_counter import ExerciseState
from .utils.logger import get_logger, setup_logging
from .utils.paths import available_model_variants

log = get_logger("app")

_RESTART_KEYS = {
    "camera_index",
    "resolution",
    "max_fps",
    "model_variant",
    "min_detection_confidence",
    "min_tracking_confidence",
    "min_presence_confidence",
}


class ApplicationController:
    def __init__(self) -> None:
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.snapshot()
        self.model_error: Optional[str] = None
        self._lock = threading.RLock()

        self.pipeline, self.model_error = self._create_pipeline(self.settings)
        self.processor = FrameProcessor(self.pipeline, self.settings)
        log.info(
            "Application ready (camera=%s, model=%s, model_error=%s)",
            self.settings.get("camera_index"),
            self.settings.get("model_variant"),
            self.model_error,
        )

    # ------------------------------------------------------------------ setup
    def _create_pipeline(self, settings: dict) -> tuple[Pipeline, Optional[str]]:
        detector = None
        error = None
        try:
            detector = PoseDetector(
                variant=settings.get("model_variant", "full"),
                min_detection_confidence=float(
                    settings.get("min_detection_confidence", 0.5)
                ),
                min_tracking_confidence=float(
                    settings.get("min_tracking_confidence", 0.5)
                ),
                min_presence_confidence=float(
                    settings.get("min_presence_confidence", 0.5)
                ),
            )
        except ModelNotFoundError as exc:
            error = str(exc)
            log.error("Pose model not found: %s", exc)
        except ModelInitError as exc:
            error = str(exc)
            log.error("Pose model failed to initialise: %s", exc)
        except Exception as exc:
            error = f"Unexpected pose engine error: {exc}"
            log.exception("Unexpected pose engine error")

        pipeline = Pipeline(
            detector=detector,
            settings=settings,
            exercise=settings.get("exercise", "Squats"),
            exercise_arm=settings.get("exercise_arm", "Right arm"),
        )
        return pipeline, error

    @property
    def skeleton_visible(self) -> bool:
        return bool(self.pipeline.style.visible)

    def exercise_snapshot(self) -> ExerciseState:
        return self.pipeline.exercise_snapshot()

    # --------------------------------------------------------------- lifecycle
    def start_camera(self) -> None:
        try:
            self.processor.start()
        except Exception:
            log.exception("Could not start camera")

    def stop_camera(self) -> None:
        try:
            self.processor.stop()
        except Exception:
            log.exception("Could not stop camera")

    def toggle_pause(self) -> None:
        try:
            self.processor.toggle_pause()
        except Exception:
            log.exception("Could not toggle pause")

    def toggle_skeleton(self) -> bool:
        visible = self.pipeline.toggle_skeleton()
        self._update_setting({"skeleton_visible": visible})
        return visible

    # --------------------------------------------------------------- exercise
    def select_exercise(self, exercise: str) -> None:
        self.pipeline.select_exercise(exercise)
        self._update_setting({"exercise": exercise})

    def select_exercise_arm(self, arm: str) -> None:
        exercise = self.settings.get("exercise", "Squats")
        self.pipeline.exercise.select(exercise, self.settings.get("exercise_sensitivity", "Balanced"), arm)
        self._update_setting({"exercise_arm": arm})

    def start_exercise(self) -> None:
        self.pipeline.start_exercise()

    def pause_exercise(self) -> None:
        self.pipeline.pause_exercise()

    def reset_exercise(self) -> None:
        self.pipeline.reset_exercise()

    # ---------------------------------------------------------------- posture
    def calibrate_posture(self) -> tuple[bool, str]:
        try:
            calibration = self.pipeline.calibrate_posture()
        except ValueError as exc:
            return False, str(exc)
        except Exception as exc:
            log.exception("Posture calibration failed")
            return False, f"Posture calibration failed: {exc}"
        self.settings_manager.set_posture_calibration(calibration)
        self.settings["posture_calibration"] = calibration
        return True, "Neutral posture captured. Future readings are relative to this pose."

    def reset_posture_calibration(self) -> None:
        self.pipeline.reset_posture_calibration()
        self.settings_manager.set_posture_calibration(None)
        self.settings["posture_calibration"] = None

    # ------------------------------------------------------------------- fall
    def dismiss_fall(self) -> None:
        self.pipeline.dismiss_fall()

    def set_fall_enabled(self, enabled: bool) -> None:
        self.pipeline.apply_settings({"fall_detection_enabled": bool(enabled)})
        self._update_setting({"fall_detection_enabled": bool(enabled)})

    def set_fall_sensitivity(self, sensitivity: str) -> None:
        self.pipeline.apply_settings({"fall_sensitivity": sensitivity})
        self._update_setting({"fall_sensitivity": sensitivity})

    # --------------------------------------------------------------- settings
    def apply_settings(self, values: dict) -> tuple[bool, str]:
        with self._lock:
            current = self.settings_manager.snapshot()
            needs_restart = any(
                key in values and values.get(key) != current.get(key)
                for key in _RESTART_KEYS
            )
            theme_changed = values.get("theme") != current.get("theme")

            self.settings = self.settings_manager.update(values)
            self.pipeline.apply_settings(self.settings)
            self.processor.settings.update(self.settings)

            if theme_changed:
                try:
                    import customtkinter as ctk

                    ctk.set_appearance_mode(
                        "light" if self.settings.get("theme") == "Light" else "dark"
                    )
                except Exception:
                    log.debug("Could not apply appearance mode", exc_info=True)

            if needs_restart:
                self._restart_pipeline(restart=bool(self.processor.running))
                if self.model_error:
                    return True, (
                        "Settings saved, but the pose engine could not start: "
                        f"{self.model_error}"
                    )
                return True, "Settings saved. Camera and pose engine restarted."

            return True, "Settings saved and applied."

    def restore_defaults(self) -> tuple[bool, str]:
        with self._lock:
            defaults = dict(DEFAULT_SETTINGS)
            self.settings = self.settings_manager.update(defaults)
            self._restart_pipeline(restart=bool(self.processor.running))
            self.pipeline.apply_settings(self.settings)
            self.processor.settings.update(self.settings)
            if self.model_error:
                return True, f"Defaults restored, but the pose engine failed: {self.model_error}"
            return True, "Default settings restored and applied."

    def _restart_pipeline(self, restart: bool) -> None:
        was_paused = self.processor.paused
        try:
            self.processor.shutdown()
        except Exception:
            log.exception("Error stopping old pipeline")

        self.pipeline, self.model_error = self._create_pipeline(self.settings)
        self.processor = FrameProcessor(self.pipeline, self.settings)
        if restart:
            try:
                self.processor.start()
                if was_paused:
                    self.processor.pause()
            except Exception:
                log.exception("Could not restart camera")
        log.info("Pipeline restarted (camera running=%s)", restart)

    def _update_setting(self, values: dict) -> None:
        self.settings = self.settings_manager.update(values)

    # --------------------------------------------------------------- shutdown
    def shutdown(self) -> None:
        try:
            self.processor.shutdown()
        except Exception:
            log.exception("Error shutting down processor")
        finally:
            try:
                self.settings_manager.save()
            except Exception:
                log.debug("Could not save settings at shutdown", exc_info=True)


def run_self_test(seconds: float = 8.0) -> int:
    """Headless smoke test: model load, camera capture, pose pipeline.

    Used to verify a packaged build without driving the GUI. A body does not
    have to be visible: the check requires a working model, a live camera, and
    frames flowing through the analysis pipeline.
    """
    import time

    setup_logging()
    log.info("Starting self-test (%.1fs)", seconds)
    controller = ApplicationController()
    if controller.model_error:
        print(f"SELF-TEST FAIL: pose model: {controller.model_error}", file=sys.stderr)
        controller.shutdown()
        return 2

    controller.start_camera()
    processed = 0
    detected = 0
    last_frame_shape = None
    deadline = time.monotonic() + max(1.0, seconds)
    while time.monotonic() < deadline:
        result = controller.processor.drain_result()
        if result is not None:
            processed += 1
            if result.detected:
                detected += 1
            if result.frame is not None:
                last_frame_shape = result.frame.shape
        time.sleep(0.02)

    status, message = controller.processor.status()
    fps = controller.processor.capture_fps
    controller.shutdown()

    summary = (
        f"model=ok status={status} processed={processed} detected={detected} "
        f"capture_fps={fps:.1f} frame={last_frame_shape}"
    )
    if processed <= 0 or last_frame_shape is None:
        print(f"SELF-TEST FAIL: no annotated frames ({summary}); {message}", file=sys.stderr)
        log.error("Self-test failed: %s", summary)
        return 3
    print(f"SELF-TEST PASS: {summary}")
    log.info("Self-test passed: %s", summary)
    return 0


def main() -> int:
    setup_logging()
    log.info("Starting humanbodyVision")
    if "--self-test" in sys.argv[1:]:
        return run_self_test()
    try:
        from .gui.main_window import MainWindow
    except ImportError as exc:
        log.exception("GUI dependencies are missing")
        print(f"Could not start the GUI: {exc}", file=sys.stderr)
        return 1

    controller = ApplicationController()
    try:
        window = MainWindow(controller)
    except Exception:
        log.exception("Could not create the main window")
        controller.shutdown()
        return 1

    try:
        window.mainloop()
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    finally:
        try:
            controller.shutdown()
        except Exception:
            log.exception("Shutdown error")
    return 0
