"""Background webcam capture and pose-processing workers.

Two daemon threads keep the GUI responsive:
  * capture thread reads frames and stores only the newest one (no backlog),
  * processing thread runs pose inference on the newest frame and publishes the
    newest annotated result to a single-slot mailbox for the GUI.

Frames are never queued without bound, so a slow analysis step cannot build a
delay between what the camera sees and what the user sees.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from ..config.defaults import RESOLUTIONS
from ..core.pipeline import FrameResult, Pipeline
from ..utils.logger import get_logger
from .camera_manager import CameraDevice, CameraError

log = get_logger("frame_processor")

STOPPED = "Stopped"
CONNECTING = "Connecting"
CONNECTED = "Connected"
PAUSED = "Paused"
DISCONNECTED = "Disconnected"
ERROR = "Error"


@dataclass
class _FramePacket:
    frame: np.ndarray
    timestamp: float
    sequence: int


class FrameProcessor:
    def __init__(
        self,
        pipeline: Pipeline,
        settings: dict[str, Any],
        camera_factory=None,
    ) -> None:
        self.pipeline = pipeline
        self.settings = dict(settings)
        self._camera_factory = camera_factory
        self._camera: Optional[CameraDevice] = None
        self._camera_lock = threading.Lock()

        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._frame_condition = threading.Condition()
        self._latest_frame: Optional[_FramePacket] = None
        self._frame_sequence = 0

        self._result_lock = threading.Lock()
        self._latest_result: Optional[FrameResult] = None
        self._result_sequence = 0

        self._status_lock = threading.Lock()
        self._status = STOPPED
        self._status_message = "Camera is stopped."
        self._running = False
        self._paused = False
        self._threads: list[threading.Thread] = []
        self._target_fps = int(settings.get("max_fps", 30))
        self._last_capture = 0.0
        self._capture_fps = 0.0

    # --------------------------------------------------------------- lifecycle
    @property
    def running(self) -> bool:
        return self._running

    @property
    def paused(self) -> bool:
        return self._paused

    def start(self) -> None:
        with self._status_lock:
            if self._running:
                already_running = True
                was_paused = self._paused
            else:
                already_running = False
                was_paused = False
                self._running = True
                self._paused = False
                self._stop_event.clear()
                self._pause_event.clear()
                self._status = CONNECTING
                self._status_message = "Opening camera..."

        if already_running:
            if was_paused:
                self.resume()
            return

        with self._frame_condition:
            self._latest_frame = None

        self._camera = self._build_camera()
        self._threads = [
            threading.Thread(target=self._capture_loop, name="camera-capture", daemon=True),
            threading.Thread(target=self._process_loop, name="pose-processing", daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        log.info("Frame processor started (camera %s)", self.settings.get("camera_index", 0))

    def pause(self) -> None:
        with self._status_lock:
            if not self._running or self._paused:
                return
            self._paused = True
            self._pause_event.set()
            self._status = PAUSED
            self._status_message = "Camera paused. Preview is frozen."
        with self._frame_condition:
            self._latest_frame = None
            self._frame_condition.notify_all()

    def resume(self) -> None:
        with self._status_lock:
            if not self._running:
                self.start()
                return
            if not self._paused:
                return
            self._paused = False
            self._pause_event.clear()
            self._status = CONNECTING
            self._status_message = "Resuming camera..."
        with self._frame_condition:
            self._latest_frame = None
            self._frame_condition.notify_all()
        if self._camera is not None:
            self._camera.flush()

    def toggle_pause(self) -> None:
        if self._paused:
            self.resume()
        elif self._running:
            self.pause()

    def stop(self) -> None:
        with self._status_lock:
            was_running = self._running
            self._running = False
            self._paused = False
            self._status = STOPPED
            self._status_message = "Camera is stopped."
        self._stop_event.set()
        self._pause_event.clear()
        with self._frame_condition:
            self._latest_frame = None
            self._frame_condition.notify_all()

        current = threading.current_thread()
        for thread in self._threads:
            if thread is not current and thread.is_alive():
                thread.join(timeout=0.8)
        self._threads = []
        self._release_camera()
        if was_running:
            log.info("Frame processor stopped")

    def shutdown(self) -> None:
        self.stop()
        try:
            self.pipeline.close()
        except Exception:
            log.debug("Error closing pipeline", exc_info=True)

    # ------------------------------------------------------------------- state
    def status(self) -> tuple[str, str]:
        with self._status_lock:
            return self._status, self._status_message

    def drain_result(self) -> Optional[FrameResult]:
        """Return the newest annotated frame result and clear the slot."""
        with self._result_lock:
            result = self._latest_result
            self._latest_result = None
            return result

    def peek_result(self) -> Optional[FrameResult]:
        with self._result_lock:
            return self._latest_result

    @property
    def capture_fps(self) -> float:
        return self._capture_fps

    # --------------------------------------------------------------- internals
    def _build_camera(self) -> CameraDevice:
        resolution = self.settings.get("resolution", "1280x720")
        width, height = RESOLUTIONS.get(resolution, (1280, 720))
        return CameraDevice(
            index=int(self.settings.get("camera_index", 0)),
            width=width,
            height=height,
            fps=int(self.settings.get("max_fps", 30)),
            capture_factory=self._camera_factory,
        )

    def _set_status(self, status: str, message: str) -> None:
        with self._status_lock:
            self._status = status
            self._status_message = message

    def _release_camera(self) -> None:
        with self._camera_lock:
            if self._camera is not None:
                self._camera.release()

    def _publish_result(self, result: FrameResult) -> None:
        with self._result_lock:
            self._latest_result = result
            self._result_sequence += 1

    def _capture_loop(self) -> None:
        retry_delay = 1.5
        while not self._stop_event.is_set():
            if self._paused:
                self._release_camera()
                time.sleep(0.05)
                continue

            camera = self._camera
            if camera is None:
                self._camera = self._build_camera()
                camera = self._camera

            if not camera.is_open:
                try:
                    camera.open()
                    self._set_status(CONNECTING, "Camera opened. Waiting for first frame...")
                except CameraError as exc:
                    self._set_status(ERROR, str(exc))
                    log.warning("Camera open failed: %s", exc)
                    self._release_camera()
                    self._stop_event.wait(retry_delay)
                    continue
                except Exception as exc:  # defensive: unexpected driver error
                    self._set_status(ERROR, f"Unexpected camera error: {exc}")
                    log.exception("Unexpected camera error")
                    self._release_camera()
                    self._stop_event.wait(retry_delay)
                    continue

            try:
                frame = camera.read()
            except CameraError as exc:
                self._set_status(DISCONNECTED, str(exc))
                self._release_camera()
                self._stop_event.wait(1.0)
                continue
            except Exception as exc:
                self._set_status(DISCONNECTED, f"Camera read failed: {exc}")
                self._release_camera()
                self._stop_event.wait(1.0)
                continue

            now = time.monotonic()
            if self._status != CONNECTED:
                self._set_status(CONNECTED, "Camera connected and streaming.")
            with self._frame_condition:
                self._frame_sequence += 1
                self._latest_frame = _FramePacket(frame, now, self._frame_sequence)
                self._frame_condition.notify_all()

            if self._last_capture > 0:
                delta = now - self._last_capture
                if delta > 1e-4:
                    instant = 1.0 / delta
                    self._capture_fps = instant if self._capture_fps <= 0 else self._capture_fps * 0.9 + instant * 0.1
            self._last_capture = now

            target = max(5, self._target_fps)
            elapsed = time.monotonic() - now
            remaining = (1.0 / target) - elapsed
            if remaining > 0:
                self._stop_event.wait(remaining)

        self._release_camera()

    def _process_loop(self) -> None:
        while not self._stop_event.is_set():
            packet: Optional[_FramePacket] = None
            with self._frame_condition:
                if self._latest_frame is None and not self._stop_event.is_set():
                    self._frame_condition.wait(timeout=0.1)
                packet = self._latest_frame
                self._latest_frame = None
            if packet is None:
                continue
            if self._paused:
                continue
            try:
                result = self.pipeline.process(packet.frame, packet.timestamp)
                self._publish_result(result)
            except Exception as exc:
                log.exception("Processing pipeline failed")
                self._set_status(ERROR, f"Processing error: {exc}")
                time.sleep(0.2)
