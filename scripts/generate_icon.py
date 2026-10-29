"""Generate the multi-resolution Windows application icon.

Run from the project root:

    .venv\\Scripts\\python.exe scripts\\generate_icon.py

The icon is drawn at 4x resolution and downsampled for clean anti-aliased
edges, then saved as a multi-size .ico file used by the GUI and installer.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "src" / "humanbodyvision" / "resources" / "icons" / "icon.ico"

SCALE = 4
SIZE = 256 * SCALE

BACKGROUND = "#0b0f14"
PANEL = "#101820"
GREEN = "#22c55e"
GREEN_DARK = "#0f3d25"
CYAN = "#22d3ee"
WHITE = "#eef4f8"


def s(value: int) -> int:
    return value * SCALE


def main() -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle(
        (s(8), s(8), SIZE - s(8), SIZE - s(8)),
        radius=s(52),
        fill=BACKGROUND,
        outline=GREEN_DARK,
        width=s(5),
    )
    draw.rounded_rectangle(
        (s(24), s(24), SIZE - s(24), SIZE - s(24)),
        radius=s(40),
        fill=PANEL,
    )
    draw.ellipse(
        (s(54), s(30), SIZE - s(54), SIZE - s(30)),
        outline=GREEN_DARK,
        width=s(2),
    )

    joints = {
        "head": (128, 58),
        "neck": (128, 92),
        "left_shoulder": (94, 98),
        "right_shoulder": (162, 98),
        "left_elbow": (78, 126),
        "right_elbow": (178, 126),
        "left_wrist": (68, 154),
        "right_wrist": (188, 154),
        "left_hip": (106, 160),
        "right_hip": (150, 160),
        "left_knee": (98, 192),
        "right_knee": (158, 192),
        "left_ankle": (86, 220),
        "right_ankle": (170, 220),
    }
    bones = [
        ("neck", "left_shoulder"),
        ("neck", "right_shoulder"),
        ("left_shoulder", "left_elbow"),
        ("left_elbow", "left_wrist"),
        ("right_shoulder", "right_elbow"),
        ("right_elbow", "right_wrist"),
        ("neck", "left_hip"),
        ("neck", "right_hip"),
        ("left_hip", "right_hip"),
        ("left_hip", "left_knee"),
        ("left_knee", "left_ankle"),
        ("right_hip", "right_knee"),
        ("right_knee", "right_ankle"),
    ]

    for start, end in bones:
        ax, ay = joints[start]
        bx, by = joints[end]
        draw.line(
            (s(ax), s(ay), s(bx), s(by)),
            fill=GREEN_DARK,
            width=s(14),
        )
        draw.line(
            (s(ax), s(ay), s(bx), s(by)),
            fill=GREEN,
            width=s(8),
        )

    hx, hy = joints["head"]
    draw.ellipse(
        (s(hx - 19), s(hy - 19), s(hx + 19), s(hy + 19)),
        outline=GREEN_DARK,
        width=s(12),
    )
    draw.ellipse(
        (s(hx - 19), s(hy - 19), s(hx + 19), s(hy + 19)),
        outline=GREEN,
        width=s(7),
        fill=PANEL,
    )

    for name, (x, y) in joints.items():
        if name == "head":
            continue
        radius = 8 if name in {"neck", "left_hip", "right_hip"} else 6
        draw.ellipse(
            (s(x - radius - 2), s(y - radius - 2), s(x + radius + 2), s(y + radius + 2)),
            fill=BACKGROUND,
        )
        draw.ellipse(
            (s(x - radius), s(y - radius), s(x + radius), s(y + radius)),
            fill=CYAN if name.endswith("shoulder") else WHITE,
        )

    # Small motion accent in the corner.
    draw.arc(
        (s(176), s(176), s(232), s(232)),
        start=300,
        end=80,
        fill=GREEN,
        width=s(5),
    )

    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(
        OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
