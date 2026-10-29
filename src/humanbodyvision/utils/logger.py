"""Application logging configuration."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .paths import log_dir

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure console + rotating file logging once, return the app logger."""
    global _configured
    root = logging.getLogger()
    if not _configured:
        root.setLevel(level)
        formatter = logging.Formatter(_LOG_FORMAT)

        console = logging.StreamHandler(stream=sys.stdout)
        console.setFormatter(formatter)
        root.addHandler(console)

        try:
            file_handler = RotatingFileHandler(
                log_dir() / "humanbodyvision.log",
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError:
            # Logging must never prevent the application from starting.
            root.warning("Could not create log file handler", exc_info=True)

        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        _configured = True

    return logging.getLogger("humanbodyvision")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"humanbodyvision.{name}")
