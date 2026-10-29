"""Basic upper-body posture analysis from visible pose landmarks.

The analysis is intentionally conservative and uses neutral language. A webcam
cannot diagnose spinal disorders; this module only reports observable geometry
relative to an optional neutral calibration pose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from . import landmark_geometry as geo

ALIGNED = "Aligned"
FORWARD_LEAN = "Forward lean detected"
SHOULDER_ASYMMETRY = "Shoulder asymmetry observed"
HEAD_OFFSET = "Head position offset observed"
INSUFFICIENT = "Insufficient visibility"


@dataclass
class PostureResult:
    status: str = INSUFFICIENT
    shoulder_tilt: Optional[float] = None
    torso_inclination: Optional[float] = None
    head_offset: Optional[float] = None
    shoulder_delta: Optional[float] = None
    torso_delta: Optional[float] = None
    head_delta: Optional[float] = None
    suggestion: str = "Position your upper body clearly in frame."
    calibrated: bool = False
    visibility: str = "Insufficient"
    warning_joints: tuple[int, ...] = ()
    active_joints: tuple[int, ...] = (11, 12, 23, 24)

    @property
    def is_ok(self) -> bool:
        return self.status == ALIGNED


class PostureAnalyzer:
    def __init__(
        self,
        calibration: Optional[dict[str, float]] = None,
        visibility_threshold: float = 0.5,
    ) -> None:
        self.visibility_threshold = float(visibility_threshold)
        self.calibration: Optional[dict[str, float]] = (
            dict(calibration) if calibration else None
        )

    def set_calibration(self, calibration: Optional[dict[str, float]]) -> None:
        self.calibration = dict(calibration) if calibration else None

    def calibrate(self, landmarks: Optional[Sequence[Any]]) -> dict[str, float]:
        """Capture a neutral reference posture; raises ValueError if invisible."""
        result = self._measure(landmarks)
        if result["usable"] < 3:
            raise ValueError(
                "Calibration needs your upper body in view (shoulders, hips and head)."
            )
        calibration = {
            "shoulder_tilt": result["shoulder_tilt"] or 0.0,
            "torso_inclination": result["torso_inclination"] or 0.0,
            "head_offset": result["head_offset"] or 0.0,
        }
        self.calibration = calibration
        return calibration

    def reset_calibration(self) -> None:
        self.calibration = None

    def analyze(self, landmarks: Optional[Sequence[Any]]) -> PostureResult:
        measurements = self._measure(landmarks)
        if measurements["usable"] < 2 or measurements["shoulder_tilt"] is None:
            return PostureResult(
                status=INSUFFICIENT,
                visibility="Insufficient",
                suggestion="Make sure your head, shoulders and hips are visible to the camera.",
        )

        shoulder = measurements["shoulder_tilt"]
        torso = measurements["torso_inclination"]
        head = measurements["head_offset"]
        calibrated = self.calibration is not None

        shoulder_delta = None
        torso_delta = None
        head_delta = None
        if self.calibration:
            shoulder_delta = shoulder - abs(self.calibration.get("shoulder_tilt", 0.0))
            if torso is not None:
                torso_delta = torso - abs(self.calibration.get("torso_inclination", 0.0))
            if head is not None:
                head_delta = head - self.calibration.get("head_offset", 0.0)

        warning: tuple[int, ...] = ()
        status = ALIGNED
        suggestion = "Posture looks balanced from this camera angle. Keep it up."

        # Shoulder asymmetry: absolute threshold plus deviation from calibration.
        if shoulder > 9 or (shoulder_delta is not None and shoulder_delta > 6):
            status = SHOULDER_ASYMMETRY
            warning = (11, 12)
            suggestion = (
                "Your shoulder line looks tilted. Relax your shoulders and check that "
                "you are sitting or standing evenly."
            )
        elif torso is not None and torso > 16 and (
            torso_delta is None or torso_delta > 6
        ):
            status = FORWARD_LEAN
            warning = (11, 12, 23, 24)
            suggestion = (
                "Your torso is leaning away from vertical. Try stacking your shoulders "
                "over your hips and adjusting your seat or stance."
            )
        elif head is not None and abs(head) > 0.45 and (
            head_delta is None or abs(head_delta) > 0.22
        ):
            status = HEAD_OFFSET
            warning = (0, 11, 12)
            suggestion = (
                "Your head appears shifted relative to your shoulders. Centre your head "
                "and take a short posture break."
            )

        visibility = "Good" if measurements["usable"] >= 4 else "Partial"
        return PostureResult(
            status=status,
            shoulder_tilt=round(shoulder, 1),
            torso_inclination=round(torso, 1) if torso is not None else None,
            head_offset=round(head, 2) if head is not None else None,
            shoulder_delta=round(shoulder_delta, 1) if shoulder_delta is not None else None,
            torso_delta=round(torso_delta, 1) if torso_delta is not None else None,
            head_delta=round(head_delta, 2) if head_delta is not None else None,
            suggestion=suggestion,
            calibrated=calibrated,
            visibility=visibility,
            warning_joints=warning,
        )

    # ------------------------------------------------------------- internals
    def _measure(self, landmarks: Optional[Sequence[Any]]) -> dict[str, Any]:
        if landmarks is None or len(landmarks) < 25:
            return {
                "usable": 0,
                "shoulder_tilt": None,
                "torso_inclination": None,
                "head_offset": None,
            }
        threshold = self.visibility_threshold
        required = [geo.LEFT_SHOULDER, geo.RIGHT_SHOULDER, geo.LEFT_HIP,
                    geo.RIGHT_HIP, geo.NOSE]
        usable = sum(
            1 for index in required if geo.is_visible(geo.landmark(landmarks, index), threshold)
        )
        return {
            "usable": usable,
            "shoulder_tilt": geo.shoulder_tilt(landmarks),
            "torso_inclination": geo.torso_inclination(landmarks),
            "head_offset": geo.head_offset(landmarks),
        }
