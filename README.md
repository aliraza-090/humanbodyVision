# humanbodyVision

**Offline, on-device human body tracking for Windows.** Point a webcam at yourself, press
Start, and see a bright green skeleton track your full body in real time, with rule-based
activity recognition, exercise repetition counting, neutral posture feedback and
experimental fall detection.

Developed by **Ali Raza Chakrani** · Version **1.0.0** · MIT License

> **Privacy:** every frame is processed on this computer. There are no accounts, cloud
> APIs, telemetry, uploads or automatic recordings. Nothing is sent over the network at
> runtime.

---

## Contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Install from source](#install-from-source)
- [Run the app](#run-the-app)
- [Using the app](#using-the-app)
- [How each feature works](#how-each-feature-works)
- [Settings and data locations](#settings-and-data-locations)
- [Automated tests](#automated-tests)
- [Package a Windows build](#package-a-windows-build)
- [Project structure](#project-structure)
- [Versions](#versions)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Manual webcam verification checklist](#manual-webcam-verification-checklist)
- [License](#license)

---

## What it does

| Feature | Summary |
| --- | --- |
| Live body tracking | MediaPipe Pose Landmarker tracks up to 33 body landmarks in video mode. A bright green skeleton is drawn on the original camera image. |
| Skeleton overlay | Only valid MediaPipe connections are drawn, and only when both endpoints are visible. Green bones, cyan joints, yellow active joints, red/orange warnings. Line thickness, dot size and visibility threshold are configurable. |
| Activity recognition | Standing, Sitting, Walking in place, Raising arm, Squatting, Bending and Unknown, smoothed over a short time window. Evidence is reported as Strong / Moderate / Weak, not a fake percentage. |
| Exercise counting | Squats, Bicep Curls and Jumping Jacks with full-range state machines, phase feedback and session timing. Unvalidated exercises such as push-ups are intentionally not included. |
| Posture analysis | Shoulder tilt, torso inclination and head offset using neutral language. Optional calibration against your own neutral pose. Not a medical assessment. |
| Fall detection | Experimental multi-signal monitor (rapid hip drop, upright-to-horizontal torso change, sustained low posture) with dismiss and cooldown. It does not contact emergency services. |
| Settings | Camera index, resolution, FPS, mirror, pose model, confidence thresholds, skeleton appearance and exercise/fall sensitivity. Saved locally as JSON. |
| Threading | Capture and pose inference run on background threads. The GUI only reads the newest frame result on the Tk event loop, so the window stays responsive. |

The **main priority** is the first row: open the app, see yourself on the webcam and see a
bright green skeleton tracking your whole body in real time.

---

## Requirements

- Windows 10 or Windows 11, 64-bit
- A webcam that works in the Windows Camera app
- Python **3.12** for running from source (`3.12.14` was used to build and test this release)
- Internet access only for the initial dependency install. The bundled pose models are
  already in `src/humanbodyvision/resources/models/`, so runtime use is fully offline.

The installer build is self-contained; end users do not need Python.

---

## Install from source

From PowerShell in the project folder:

```powershell
# Option A: uv (used for this build)
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt

# Option B: standard Python launcher
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# Models are bundled. If they are missing, restore them:
.venv\Scripts\python.exe scripts\download_model.py
```

Runtime-only dependencies are in `requirements.txt`; test and packaging tools are in
`requirements-dev.txt`.

---

## Run the app

```powershell
.venv\Scripts\python.exe main.py
```

Equivalent commands:

```powershell
.venv\Scripts\python.exe -m humanbodyvision
# or, after `pip install -e .`
humanbodyvision
```

The first launch may trigger a Windows camera permission prompt. Allow camera access for
desktop applications, then press **Start Camera** on the Dashboard.

### Headless self-test

To verify the pose engine, camera and analysis pipeline without opening the GUI:

```powershell
.venv\Scripts\python.exe main.py --self-test
# Packaged build:
dist\humanbodyVision\humanbodyVision.exe --self-test
```

It runs for about 8 seconds, then prints `SELF-TEST PASS` with the processed frame count,
detections, capture FPS and frame size. Exit codes: `0` pass, `2` pose model failure,
`3` no frames. A body does not need to be in view for the pipeline check to pass.

---

## Using the app

1. Open **Settings** and choose the camera, resolution (`640x480`, `1280x720` or
   `1920x1080`), maximum FPS, mirror preference and model variant. Press **Save & Apply**.
2. Return to **Dashboard** or **Live Body Tracking** and press **Start Camera**.
3. Stand roughly 2–3 metres from the camera so your head, hands and feet are in frame.
4. The green skeleton should follow your body immediately. Step back if joints are cut off.
5. Use **Pause** to freeze the preview without releasing the session, and **Stop** to close
   the camera and release resources.
6. Open **Exercise Monitor**, choose Squats, Bicep Curls (with left/right arm) or Jumping
   Jacks, then press **Start** and perform full-range repetitions.
7. Open **Posture Analysis** and press **Calibrate Neutral Posture** while sitting or
   standing naturally, if you want relative feedback.
8. **Fall Detection** is on by default. Review its experimental warning and use **Dismiss**
   after a false alert. It can be disabled in Settings.

Keyboard/mouse only; no account or login is required.

---

## How each feature works

### Pose detection and the green skeleton

- `core/pose_detector.py` wraps the MediaPipe Tasks **Pose Landmarker** in `VIDEO` running
  mode. OpenCV frames are BGR; they are converted to contiguous RGB for MediaPipe. Video
  timestamps are forced to increase monotonically, as required by MediaPipe.
- `core/skeleton_renderer.py` contains the standard MediaPipe pose connection list. It draws
  bones first and joints second. A connection is skipped when either endpoint is below the
  configured visibility threshold, which prevents misleading “ghost” limbs.
- The displayed frame is mirrored when **Mirror preview** is on, so movement feels like a
  mirror. Landmark x-coordinates are mirrored only for drawing; inference always uses the
  original camera frame.
- The original camera image is preserved as the background. Only skeleton lines, joint dots
  and a small HUD are composited on top.

### Activity recognition

`core/activity_recognizer.py` is a rule-based classifier over pose geometry plus motion
features from `core/motion_tracker.py`:

- Deep torso lean or head below shoulder level → **Bending**
- One or both wrists above shoulders → **Raising arm**
- Deep upright knee bend → **Squatting**
- Alternating ankle motion → **Walking in place**
- Moderate knee flexion with a compressed hip-to-ankle span → **Sitting**
- Upright torso and extended legs → **Standing**
- Otherwise → **Unknown**

A rolling time window with hysteresis and a minimum hold time prevents single-frame label
flicker. “Evidence” describes how many recent frames agreed with the displayed label. It is
not a statistical probability.

### Exercise counting

`core/exercise_counter.py` uses explicit state machines:

- **Squats:** average knee angle. The user must reach the sensitivity-dependent bottom
  threshold and then return to standing. The bottom position must be held briefly and
  repetitions are rate-limited.
- **Bicep Curls:** elbow angle of the selected arm. Full flexion and full extension are both
  required before a rep counts.
- **Jumping Jacks:** both wrists above the shoulders with ankles apart, then arms down with
  feet together. A brief hold is required.

Partial repetitions do not count. The session tracks running/paused state and elapsed time.
These are fitness aids, not clinical measurements.

### Posture analysis

`core/posture_analyzer.py` measures:

- shoulder-line tilt in degrees,
- torso inclination from vertical,
- horizontal nose offset from the shoulder centre in torso units.

Optional calibration stores your neutral values and reports differences from that baseline.
Labels are deliberately neutral (“Aligned”, “Forward lean detected”, “Shoulder asymmetry
observed”, “Head position offset observed”, “Insufficient visibility”). No diagnosis is made.

### Experimental fall detection

`core/fall_detector.py` requires multiple concurrent signals, not a single pose:

1. a rapid downward hip movement normalized in frame heights per second,
2. a change from an upright torso to a horizontal torso within a short window,
3. sustained low posture.

Sensitivity presets change the drop and horizontal-angle thresholds. False positives and
false negatives are expected. An alert is dismissible and has a cooldown to avoid repeated
alerts. The app **does not** call emergency services and is **not** a medical or safety
device.

### Camera and threading

- `camera/frame_processor.py` runs two daemon threads:
  - **capture**: reads the newest frame only; old frames are replaced, never queued,
  - **processing**: performs pose inference and publishes the newest `FrameResult`.
- `camera/camera_manager.py` wraps `cv2.VideoCapture` with DirectShow → default-backend
  fallback, a bounded internal buffer, read-failure detection and reconnect attempts.
- The Tk GUI polls with `after(33 ms)` and only drains the latest result. Widgets are never
  touched from worker threads.
- Stop/shutdown joins workers and releases the camera and MediaPipe resources.

### Settings

`config/settings_manager.py` loads `settings.json`, validates every field, clamps numeric
values, ignores unknown keys and falls back to defaults if the file is corrupted. Saves are
atomic (`settings.json.tmp` then `os.replace`). Restart-sensitive changes rebuild the pose
pipeline and restart the camera if it was running.

---

## Settings and data locations

| Data | Location |
| --- | --- |
| Settings | `%APPDATA%\humanbodyVision\settings.json` |
| Logs (rotating, max 2 MB × 3) | `%APPDATA%\humanbodyVision\logs\humanbodyvision.log` |
| Bundled pose models | `src\humanbodyvision\resources\models\` (source) or `resources\models\` (packaged) |

Override the data directory for development or portable testing:

```powershell
$env:HUMANBODYVISION_DATA_DIR = "C:\temp\humanbodyvision-data"
.venv\Scripts\python.exe main.py
```

No image, video or audio recording is written by the application. Settings and logs never
leave the machine.

---

## Automated tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Coverage includes:

- `test_geometry.py` — angles, visibility, missing landmarks, torso/scale geometry
- `test_activity.py` — labels, smoothing/hysteresis, walking motion
- `test_exercise.py` — full vs partial reps, arm selection, session timing
- `test_posture.py` — aligned/lean/asymmetry/head-offset, calibration
- `test_fall_detection.py` — fall sequence, multi-signal requirement, dismiss/cooldown
- `test_settings.py` — defaults, clamping, corruption recovery, round-trip
- `test_camera.py` — fake capture: open/read failure, backend fallback, frame delivery,
  pause/resume, shutdown
- `test_pipeline.py` — fake detector: detection, green overlay, missing model, exceptions,
  posture calibration, settings, cleanup
- `test_gui.py` — headless import and navigation/palette metadata checks
- `test_app.py` — controller startup/shutdown, persistence, restart, model-failure fallback,
  headless self-test pass/fail paths

**Result for this release:** `77 passed, 1 skipped` (the skipped test needs a Tk display for
font creation; it is skipped in headless runs). The test suite uses synthetic 33-landmark poses.
It is **not** a substitute for manual webcam validation.

Verified on this machine:

- Source self-test with a real webcam: 86 frames processed, 86 with a body detected, 16.3 FPS
  capture, 1280×720.
- Packaged `humanbodyVision.exe --self-test`: 94 frames processed, 94 with a body detected,
  17.4 FPS capture, 1280×720, exit code 0.


---

## Package a Windows build

Requirements: `pyinstaller==6.22.3`, and optionally Inno Setup 6 for the installer.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

The script runs the tests, builds the PyInstaller bundle and (if `ISCC.exe` is installed)
compiles the installer. It finds Inno Setup in both machine-wide and per-user install
locations.

Manual steps:

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean packaging\humanbodyVision.spec
# Portable app:
dist\humanbodyVision\humanbodyVision.exe

# Installer (if Inno Setup 6 is installed):
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\installer.iss
# Output: dist\installer\humanbodyVision-1.0.0-windows-x64-setup.exe
```

The packaged app is a self-contained onedir build. Bundled pose models and the app icon are
included. No Python installation is required on the target machine.

**Build status for this release:** the portable bundle and the installer both compile. The
portable bundle is about 310 MB on disk; the installer is about 92 MB. The packaged
executable was launched and passed the headless self-test with the real webcam. The installer
was compiled but has not been installed on a clean machine, and the executable is not
code-signed, so Windows SmartScreen may warn on first launch.


---

## Project structure

```text
humanbodyVision/
├─ main.py                         # source launcher (adds src to sys.path)
├─ pyproject.toml                  # package metadata, dependencies, pytest config
├─ requirements.txt                # runtime pins
├─ requirements-dev.txt            # test + packaging pins
├─ src/humanbodyvision/
│  ├─ app.py                       # controller, lifecycle, entry point
│  ├─ __main__.py                  # python -m humanbodyvision
│  ├─ camera/
│  │  ├─ camera_manager.py         # OpenCV capture wrapper + enumeration
│  │  └─ frame_processor.py        # capture / processing worker threads
│  ├─ config/
│  │  ├─ defaults.py               # defaults, presets, validation bounds
│  │  └─ settings_manager.py       # JSON load/save/validation/corruption recovery
│  ├─ core/
│  │  ├─ landmark_geometry.py      # angle/scale/visibility helpers
│  │  ├─ pose_detector.py          # MediaPipe Pose Landmarker wrapper
│  │  ├─ skeleton_renderer.py      # green skeleton, joints, HUD, placeholder
│  │  ├─ motion_tracker.py         # temporal motion features
│  │  ├─ activity_recognizer.py    # smoothed rule-based activity labels
│  │  ├─ exercise_counter.py       # squat/curl/jumping-jack state machines
│  │  ├─ posture_analyzer.py       # geometric posture metrics + calibration
│  │  ├─ fall_detector.py          # experimental multi-signal fall logic
│  │  └─ pipeline.py               # frame orchestration and FrameResult
│  ├─ gui/                         # CustomTkinter theme, pages, reusable widgets
│  ├─ utils/                       # paths, logging, Windows audio feedback
│  └─ resources/
│     ├─ icons/icon.ico
│     └─ models/pose_landmarker_{lite,full}.task
├─ tests/                          # pytest suite + synthetic pose generator
├─ scripts/
│  ├─ download_model.py            # restore bundled MediaPipe models
│  ├─ generate_icon.py             # regenerate the multi-size .ico
│  └─ build_windows.ps1            # test + PyInstaller + Inno Setup
└─ packaging/
   ├─ humanbodyVision.spec         # PyInstaller onedir definition
   ├─ version_info.txt             # Windows file metadata
   └─ installer.iss                # Inno Setup 6 installer
```

---

## Versions

| Component | Version |
| --- | --- |
| humanbodyVision | 1.0.0 |
| Python (build/test) | 3.12.14 |
| MediaPipe | 1.2.0 |
| OpenCV (`opencv-python`) | 5.0.0.93 |
| NumPy | 2.5.4 |
| CustomTkinter | 6.0.0 |
| Pillow | 13.0.0 |
| pytest | 9.2.0 |
| PyInstaller | 6.22.3 |
| Pose models | `pose_landmarker_lite.task`, `pose_landmarker_full.task` (MediaPipe float16) |

---

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| “Camera 0 could not be opened” | Close Teams/Zoom/Camera apps. Check **Settings → Privacy & security → Camera**. Try another camera index. Press Stop, then Start. |
| Video appears but no skeleton | Step fully into frame; improve front lighting; lower the visibility threshold slightly; verify the pose model status in the sidebar. |
| Low FPS | Choose the Lite model, 640×480 resolution and a lower maximum FPS. Close other GPU/video apps. |
| Skeleton is mirrored the wrong way | Toggle **Mirror preview** in Settings. The default is mirror-like (natural selfie view). |
| Wrong activity label | Labels are heuristic. Face the camera, keep your full body visible, and hold the movement for about a second. |
| Reps are not counted | Use the full range of motion. Try the Relaxed sensitivity. Ensure the relevant joints (knees or the selected arm) are visible. |
| Posture calibration fails | Keep head, both shoulders and both hips visible; press Calibrate while holding a steady neutral pose. |
| Fall alert is a false positive | Press **Dismiss**. Raise sensitivity only if needed; this feature is experimental. |
| Settings file corrupted | The app restores defaults automatically and logs a warning. Use **Restore Defaults** to rewrite the file. |
| Model missing after packaging | Rebuild with `scripts\build_windows.ps1`; `packaging\humanbodyVision.spec` includes `resources`. |

Logs: `%APPDATA%\humanbodyVision\logs\humanbodyvision.log`.

---

## Known limitations

- Pose quality depends on lighting, camera placement, clothing and full-body visibility.
- Activity recognition and fall detection are **rule-based heuristics**, not trained or
  clinically validated classifiers. They will make mistakes.
- Only Squats, Bicep Curls and Jumping Jacks are counted. Push-ups and other exercises are
  intentionally excluded because they were not validated here.
- Posture analysis reports observable geometry only; it is **not** a medical diagnosis.
- Fall detection is experimental and cannot replace supervision, medical devices or
  emergency services. It never contacts anyone automatically.
- Theme changes take full effect after an application restart because the palette is built
  once at startup.
- Automated tests use synthetic landmarks and mocked camera hardware. Real webcam behavior
  must be verified on the target machine (see below).
- The project was developed and tested on Windows; non-Windows support is not claimed.

---

## Manual webcam verification checklist

These items require a real camera and a person in frame. They are listed so the build can be
validated honestly; automated tests do not prove them.

- [ ] App window opens at the expected size and the dark theme renders correctly.
- [ ] Camera starts and live video appears; status changes Connecting → Connected.
- [ ] Bright green skeleton tracks the whole body, including arms, legs, ankles and feet.
- [ ] Skeleton stays aligned when the preview is mirrored and unmirrored.
- [ ] Joints are not drawn through occluded/out-of-frame limbs.
- [ ] Pause freezes the preview; Resume continues; Stop releases the camera.
- [ ] Closing the window releases the camera (it can be reopened by another app).
- [ ] Activity labels match standing, sitting, walking in place, arm raise, squat and bend.
- [ ] Squats, curls and jumping jacks count only full-range repetitions.
- [ ] Pause/Resume/Reset behave correctly in Exercise Monitor.
- [ ] Posture calibration and reset work with the upper body visible.
- [ ] Fall detection remains quiet for normal sitting/bending; test a safe simulated fall on a
      mattress only, with another adult present, and dismiss the alert afterwards.
- [ ] Settings persist after closing and reopening the app.
- [x] Packaged `humanbodyVision.exe` launches and runs the camera/pose pipeline on this machine
      (verified by `--self-test`; a machine without Python has not been tested yet).


---

## License

MIT License. See [LICENSE](LICENSE).

MediaPipe is a trademark of Google LLC. This project is not affiliated with or endorsed by
Google. Pose models are downloaded from Google's public MediaPipe model storage and are used
under their applicable terms.
