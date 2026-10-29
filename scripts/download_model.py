"""Download official MediaPipe Pose Landmarker models for development.

The Windows build ships with models bundled. Run this script only if the model
files are missing (for example after cloning without Git LFS):

    .venv\\Scripts\\python.exe scripts\\download_model.py
    .venv\\Scripts\\python.exe scripts\\download_model.py --variant full --force

Models are downloaded from Google's public MediaPipe model storage. No account
or API key is required.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "src" / "humanbodyvision" / "resources" / "models"

BASE_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker"
VARIANTS = {
    "lite": "pose_landmarker_lite.task",
    "full": "pose_landmarker_full.task",
    "heavy": "pose_landmarker_heavy.task",
}
MIN_BYTES = 1_000_000


def url_for(variant: str) -> str:
    return f"{BASE_URL}/{VARIANTS[variant]}/float16/latest/{VARIANTS[variant]}"


def download(variant: str, force: bool = False) -> Path:
    target = MODELS_DIR / VARIANTS[variant]
    if target.exists() and target.stat().st_size >= MIN_BYTES and not force:
        print(f"[skip] {target.name} already exists ({target.stat().st_size:,} bytes)")
        return target

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    url = url_for(variant)
    temporary = target.with_suffix(".task.part")
    print(f"[get ] {url}")
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP {response.status}")
            expected = int(response.headers.get("Content-Length") or 0)
            received = 0
            with temporary.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    handle.write(chunk)
                    received += len(chunk)
                    if expected:
                        percent = received * 100 / expected
                        print(f"\r       {percent:5.1f}%  {received:,} bytes", end="")
            print()
    except (urllib.error.URLError, OSError, RuntimeError) as exc:
        temporary.unlink(missing_ok=True)
        raise SystemExit(f"Download failed: {exc}") from exc

    if temporary.stat().st_size < MIN_BYTES:
        temporary.unlink(missing_ok=True)
        raise SystemExit(
            f"Downloaded file is unexpectedly small: {temporary.name}. "
            "Check your internet connection and try again."
        )
    os.replace(temporary, target)
    print(f"[done] {target} ({target.stat().st_size:,} bytes)")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download MediaPipe pose models")
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANTS),
        default="all",
        help="Model variant to download (default: all)",
    )
    parser.add_argument("--force", action="store_true", help="Replace existing files")
    args = parser.parse_args(argv)

    variants = sorted(VARIANTS) if args.variant == "all" else [args.variant]
    for variant in variants:
        download(variant, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
