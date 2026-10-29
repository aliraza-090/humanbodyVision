# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for humanbodyVision.

Build with:
    .venv\\Scripts\\python.exe -m PyInstaller --noconfirm --clean packaging\\humanbodyVision.spec

The output is a self-contained onedir application at
``dist\\humanbodyVision\\humanbodyVision.exe``. Bundled resources (pose models
and icon) are placed under ``resources`` so ``utils.paths.resource_path`` works
both from source and from the frozen bundle.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
RESOURCES = SRC / "humanbodyvision" / "resources"

datas = [
    (str(RESOURCES), "resources"),
]
binaries = []
hiddenimports = []

for package in ("mediapipe", "customtkinter"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

hiddenimports += collect_submodules("mediapipe.tasks.python")
hiddenimports += [
    "PIL._tkinter_finder",
    "mediapipe.tasks.python.vision.pose_landmarker",
]

block_cipher = None

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Do not exclude stdlib modules: MediaPipe's task API imports ``unittest``
    # and ``pydoc`` at import time, so stripping them breaks the frozen app.
    excludes=["pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="humanbodyVision",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RESOURCES / "icons" / "icon.ico"),
    version=str(ROOT / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="humanbodyVision",
)
