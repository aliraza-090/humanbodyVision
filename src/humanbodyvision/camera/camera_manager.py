"""Webcam discovery and capture device management."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import cv2

from ..utils.logger import get_logger

log = get_logger("camera")


class CameraError(RuntimeError):
    """Raised for camera open/read failures with a user-facing message."""


@dataclass
class CameraInfo:
    index: int
    width: int = 0
    height: int = 0
    label: str = ""

    def display_name(self) -> str:
        if self.width and self.height:
            return f"Camera {self.index} ({self.width}x{self.height})"
        return f"Camera {self.index}"


CaptureFactory = Callable[[int, int], Any]


def _default_factory(index: int, backend: int) -> Any:
    return cv2.VideoCapture(index, backend)


def _dshow() -> int:
    return int(getattr(cv2, "CAP_DSHOW", getattr(cv2, "CAP_ANY", 0)))


def _any_backend() -> int:
    return int(getattr(cv2, "CAP_ANY", 0))


class CameraDevice:
    """Small wrapper around cv2.VideoCapture with backend fallback."""

    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        capture_factory: Optional[CaptureFactory] = None,
    ) -> None:
        self.index = int(index)
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self._factory = capture_factory or _default_factory
        self._capture: Any = None

    @property
    def is_open(self) -> bool:
        return bool(self._capture is not None and self._capture.isOpened())

    def open(self) -> None:
        self.release()
        backends = [_dshow(), _any_backend()]
        seen: set[int] = set()
        for backend in backends:
            if backend in seen:
                continue
            seen.add(backend)
            capture = self._factory(self.index, backend)
            if capture is not None and capture.isOpened():
                self._capture = capture
                self._configure(capture)
                log.info(
                    "Camera %s opened with backend %s (%sx%s @ %s fps requested)",
                    self.index, backend, self.width, self.height, self.fps,
                )
                return
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
        raise CameraError(
            f"Camera {self.index} could not be opened. Check that it is connected, "
            "not in use by another application, and that camera permission is enabled "
            "in Windows Settings > Privacy & security > Camera."
        )

    def _configure(self, capture: Any) -> None:
        try:
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            capture.set(cv2.CAP_PROP_FPS, self.fps)
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            log.debug("Could not apply all camera properties", exc_info=True)

    def read(self) -> Any:
        if not self.is_open:
            raise CameraError("Camera is not open.")
        ok, frame = self._capture.read()
        if not ok or frame is None:
            raise CameraError("Camera stopped delivering frames. Reconnecting...")
        return frame

    def flush(self, grabs: int = 3) -> None:
        """Discard stale buffered frames after a pause."""
        if not self.is_open:
            return
        for _ in range(max(0, grabs)):
            try:
                self._capture.grab()
            except Exception:
                break

    def resolution(self) -> tuple[int, int]:
        if not self.is_open:
            return 0, 0
        try:
            width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            return width, height
        except Exception:
            return 0, 0

    def release(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None


def enumerate_cameras(max_index: int = 5) -> list[CameraInfo]:
    """Probe camera indices. This is slow and should run off the GUI thread."""
    found: list[CameraInfo] = []
    for index in range(max_index + 1):
        capture = None
        try:
            capture = cv2.VideoCapture(index, _dshow())
            if capture is not None and capture.isOpened():
                width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
                height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                found.append(CameraInfo(index=index, width=width, height=height))
        except Exception:
            log.debug("Camera probe failed for index %s", index, exc_info=True)
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
        time.sleep(0.02)
    return found
