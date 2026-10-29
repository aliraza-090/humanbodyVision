"""Local-only audio and visual feedback helpers.

Audio uses winsound on Windows. It is played on a short-lived daemon thread so
the GUI or processing thread is never blocked.
"""

from __future__ import annotations

import threading

from .logger import get_logger

log = get_logger("feedback")


def _beep(frequency: int, duration_ms: int, repeats: int = 1) -> None:
    try:
        import winsound  # Windows only
    except ImportError:  # pragma: no cover - non-Windows development
        return

    def play() -> None:
        try:
            for index in range(max(1, repeats)):
                winsound.Beep(frequency, duration_ms)
                if index < repeats - 1:
                    winsound.Beep(1, 80)
        except Exception:  # winsound can fail when audio is unavailable
            log.debug("Audio feedback unavailable", exc_info=True)

    threading.Thread(target=play, name="audio-feedback", daemon=True).start()


def play_fall_alert() -> None:
    _beep(880, 300, repeats=3)


def play_rep_chime() -> None:
    _beep(1200, 90)


def play_error_tone() -> None:
    _beep(320, 250)
