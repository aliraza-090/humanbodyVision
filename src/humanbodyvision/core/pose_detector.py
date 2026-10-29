"""MediaPipe Pose Landmarker wrapper.

The detector is intentionally thin: it converts BGR OpenCV frames to MediaPipe
images, enforces monotonically increasing timestamps in VIDEO mode, and returns
plain landmark objects. All interpretation lives in the analysis modules.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from ..utils.logger import get_logger
from ..utils.paths import available_model_variants, model_path

log = get_logger("pose")


class PoseDetectorError(RuntimeError):
    """Base class for pose detector failures."""


class ModelNotFoundError(PoseDetectorError):
    """Raised when no bundled pose model can be found."""


class ModelInitError(PoseDetectorError):
    """Raised when MediaPipe cannot initialise the pose model."""


@dataclass
class PoseDetection:
    landmarks: Optional[list[Any]]
    world_landmarks: Optional[list[Any]] = None
    timestamp_ms: int = 0

    @property
    def detected(self) -> bool:
        return bool(self.landmarks)


def resolve_model_path(variant: str = "full", explicit: str | Path | None = None) -> Path:
    if explicit:
        path = Path(explicit)
        if path.exists():
            return path
        raise ModelNotFoundError(f"Pose model not found: {path}")

    requested = model_path(variant)
    if requested.exists():
        return requested

    # Gracefully fall back to any bundled variant (e.g. only lite shipped).
    for name in available_model_variants():
        fallback = model_path(name)
        if fallback.exists():
            log.warning("Model '%s' missing; using '%s' instead", variant, name)
            return fallback

    raise ModelNotFoundError(
        "No pose landmarker model was found. Run scripts/download_model.py "
        "or reinstall the application with the bundled model."
    )


class PoseDetector:
    """Reusable MediaPipe Pose Landmarker (VIDEO running mode)."""

    def __init__(
        self,
        variant: str = "full",
        model_file: str | Path | None = None,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        num_poses: int = 1,
    ) -> None:
        self.variant = variant
        self.model_file = resolve_model_path(variant, model_file)
        self.min_detection_confidence = float(min_detection_confidence)
        self.min_tracking_confidence = float(min_tracking_confidence)
        self.min_presence_confidence = float(min_presence_confidence)
        self.num_poses = int(num_poses)
        self._lock = threading.Lock()
        self._last_timestamp_ms = 0
        self._landmarker = None
        self._init_backend()

    # ------------------------------------------------------------- lifecycle
    def _init_backend(self) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ModelInitError(
                f"MediaPipe is not installed correctly ({exc}). "
                "Install dependencies from requirements.txt or reinstall the application."
            ) from exc

        try:
            options = mp_vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(self.model_file)),
                running_mode=mp_vision.RunningMode.VIDEO,
                num_poses=self.num_poses,
                min_pose_detection_confidence=self.min_detection_confidence,
                min_pose_presence_confidence=self.min_presence_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                output_segmentation_masks=False,
            )
            self._landmarker = mp_vision.PoseLandmarker.create_from_options(options)
            self._mp = mp
            log.info("Pose model loaded: %s", self.model_file.name)
        except Exception as exc:  # MediaPipe raises varied exception types
            raise ModelInitError(f"Could not initialise MediaPipe Pose Landmarker: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self._landmarker is not None:
                try:
                    self._landmarker.close()
                except Exception:  # pragma: no cover - defensive
                    log.debug("Error closing pose landmarker", exc_info=True)
                finally:
                    self._landmarker = None

    def __enter__(self) -> "PoseDetector":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    # -------------------------------------------------------------- inference
    def _next_timestamp(self, timestamp_ms: int) -> int:
        # MediaPipe VIDEO mode requires strictly increasing timestamps.
        timestamp_ms = int(timestamp_ms)
        if timestamp_ms <= self._last_timestamp_ms:
            timestamp_ms = self._last_timestamp_ms + 1
        self._last_timestamp_ms = timestamp_ms
        return timestamp_ms

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int) -> PoseDetection:
        """Run pose landmark detection on one BGR frame."""
        if frame_bgr is None or frame_bgr.size == 0:
            return PoseDetection(None, timestamp_ms=int(timestamp_ms))

        with self._lock:
            if self._landmarker is None:
                raise ModelInitError("Pose detector is closed or not initialised.")

            rgb = np.ascontiguousarray(frame_bgr[:, :, ::-1])
            try:
                image = self._mp.Image(
                    image_format=self._mp.ImageFormat.SRGB, data=rgb
                )
                timestamp = self._next_timestamp(timestamp_ms)
                result = self._landmarker.detect_for_video(image, timestamp)
            except Exception as exc:
                log.warning("Pose inference failed: %s", exc)
                return PoseDetection(None, timestamp_ms=int(timestamp_ms))

            if not result.pose_landmarks:
                return PoseDetection(None, timestamp_ms=int(timestamp_ms))

            landmarks = list(result.pose_landmarks[0])
            world = list(result.pose_world_landmarks[0]) if result.pose_world_landmarks else None
            return PoseDetection(landmarks, world, timestamp_ms=int(timestamp_ms))


def landmarks_are_usable(points: Optional[Sequence[Any]], threshold: float = 0.5) -> bool:
    """True when enough core joints are visible to run the analysis pipeline."""
    if not points or len(points) < 29:
        return False
    core = (11, 12, 13, 14, 15, 16, 23, 24, 25, 26)
    visible = 0
    for index in core:
        try:
            score = getattr(points[index], "visibility", 0.0) or 0.0
        except (IndexError, TypeError):
            continue
        if float(score) >= threshold:
            visible += 1
    return visible >= 4
