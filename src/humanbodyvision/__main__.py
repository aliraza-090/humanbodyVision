"""Allow running with ``python -m humanbodyvision``."""

from __future__ import annotations

from .app import main

if __name__ == "__main__":
    raise SystemExit(main())
