"""Camera device and background worker tests using fake captures.

These tests never touch real hardware. A fake ``cv2.VideoCapture``-compatible
object lets us verify open/read/flush behaviour and the two-thread
capture/processing lifecycle deterministically.
"""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from humanbodyvision.camera.camera_manager import CameraDevice, CameraError
from humanbodyvision.camera.frame_processor import (
    CONNECTED,
    ERROR,
    PAUSED,
    STOPPED,
    FrameProcessor,
)
from humanbodyvision.core.pipeline import FrameResult


class FakeCapture:
    """Minimal stand-in for cv2.VideoCapture."""

    def __init__(self, opened: bool = True, fail_read_after: int | None = None) -> None:
        self.opened = opened
        self.fail_read_after = fail_read_after
        self.reads = 0
        self.grabs = 0
        self.released = 0
        self.properties: dict[int, float] = {}
        self._frame = np.full((48, 64, 3), 40, dtype=np.uint8)

    def isOpened(self) -> bool:  # noqa: N802 - matching OpenCV API
        return self.opened

    def set(self, prop: int, value: float) -> bool:
        self.properties[prop] = value
        return True

    def get(self, prop: int) -> float:
        return self.properties.get(prop, 0.0)

    def read(self):
        if self.fail_read_after is not None and self.reads >= self.fail_read_after:
            return False, None
        self.reads += 1
        frame = self._frame.copy()
        frame[0, 0] = (self.reads % 255, 0, 0)
        return True, frame

    def grab(self) -> bool:
        self.grabs += 1
        return True

    def release(self) -> None:
        self.released += 1
        self.opened = False


class FakePipeline:
    """Pipeline double that returns a fixed annotated result."""

    def __init__(self) -> None:
        self.processed = 0
        self.closed = 0
        self.lock = threading.Lock()

    def process(self, frame, timestamp):
        with self.lock:
            self.processed += 1
            return FrameResult(
                frame=frame,
                frame_id=self.processed,
                timestamp=timestamp,
                detected=True,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
            )

    def close(self) -> None:
        self.closed += 1


def _wait_for(predicate, timeout: float = 4.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ------------------------------------------------------------------ CameraDevice
def test_camera_open_configures_and_reads():
    capture = FakeCapture()
    device = CameraDevice(
        index=2, width=640, height=480, fps=15, capture_factory=lambda i, b: capture
    )
    device.open()
    try:
        assert device.is_open
        assert capture.properties
        frame = device.read()
        assert frame.shape == (48, 64, 3)
        device.flush(grabs=3)
        assert capture.grabs == 3
        width, height = device.resolution()
        assert isinstance(width, int) and isinstance(height, int)
    finally:
        device.release()
    assert not device.is_open
    assert capture.released >= 1


def test_camera_open_failure_raises_friendly_error():
    device = CameraDevice(index=7, capture_factory=lambda i, b: FakeCapture(opened=False))
    with pytest.raises(CameraError, match="could not be opened"):
        device.open()
    assert not device.is_open
    with pytest.raises(CameraError, match="not open"):
        device.read()


def test_camera_read_failure_raises_camera_error():
    capture = FakeCapture(fail_read_after=0)
    device = CameraDevice(capture_factory=lambda i, b: capture)
    device.open()
    try:
        with pytest.raises(CameraError, match="stopped delivering frames"):
            device.read()
    finally:
        device.release()


def test_camera_falls_back_to_second_backend():
    attempts: list[int] = []

    def factory(index: int, backend: int):
        attempts.append(backend)
        return FakeCapture(opened=len(attempts) > 1)

    device = CameraDevice(capture_factory=factory)
    device.open()
    try:
        assert len(attempts) >= 2
        assert device.is_open
    finally:
        device.release()


# ---------------------------------------------------------------- FrameProcessor
def test_frame_processor_captures_and_publishes_result():
    pipeline = FakePipeline()
    processor = FrameProcessor(
        pipeline,
        {"camera_index": 0, "resolution": "640x480", "max_fps": 60},
        camera_factory=lambda i, b: FakeCapture(),
    )
    processor.start()
    try:
        assert _wait_for(lambda: processor.status()[0] == CONNECTED)
        assert _wait_for(lambda: processor.drain_result() is not None)
        assert pipeline.processed >= 1
        assert processor.running
    finally:
        processor.stop()

    status, _ = processor.status()
    assert status == STOPPED
    assert not processor.running
    assert _wait_for(lambda: len(processor._threads) == 0, timeout=1.0)


def test_frame_processor_pause_and_resume():
    pipeline = FakePipeline()
    processor = FrameProcessor(
        pipeline,
        {"camera_index": 0, "resolution": "640x480", "max_fps": 60},
        camera_factory=lambda i, b: FakeCapture(),
    )
    processor.start()
    try:
        assert _wait_for(lambda: pipeline.processed >= 1)
        processor.pause()
        assert processor.paused
        assert processor.status()[0] == PAUSED
        processed_at_pause = pipeline.processed
        # Give the worker a moment to prove it stops publishing new results.
        time.sleep(0.25)
        assert pipeline.processed <= processed_at_pause + 1

        processor.resume()
        assert not processor.paused
        assert _wait_for(lambda: pipeline.processed > processed_at_pause)
    finally:
        processor.stop()


def test_frame_processor_reports_open_failure_and_stops():
    pipeline = FakePipeline()
    processor = FrameProcessor(
        pipeline,
        {"camera_index": 3, "resolution": "640x480", "max_fps": 30},
        camera_factory=lambda i, b: FakeCapture(opened=False),
    )
    processor.start()
    try:
        assert _wait_for(lambda: processor.status()[0] == ERROR)
        assert processor.running
        assert processor.drain_result() is None
    finally:
        processor.stop()
    assert processor.status()[0] == STOPPED


def test_frame_processor_shutdown_closes_pipeline():
    pipeline = FakePipeline()
    processor = FrameProcessor(
        pipeline,
        {"camera_index": 0, "resolution": "640x480", "max_fps": 30},
        camera_factory=lambda i, b: FakeCapture(),
    )
    processor.shutdown()
    assert pipeline.closed == 1
    assert processor.status()[0] == STOPPED
