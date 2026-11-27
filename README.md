# LockIn

## Webcam head pose

From the repository root, use Python 3.12 to install the dependencies and download
the MediaPipe Face Landmarker model.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
curl --fail --location \
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task \
  --output daemon/face_landmarker.task
python daemon/vision.py
```

On the first run, look at your screen during the three-second countdown. LockIn
averages the yaw and pitch it sees during that time and saves your baseline in
the repository's `config.json`. Run `python daemon/vision.py --calibrate` to
record a new baseline while keeping your current settings. The countdown
appears in the terminal and in the preview when `--debug` is enabled.

The script prints yaw and pitch in degrees. Positive yaw means you turned to
your right, and positive pitch means you looked up. It logs transitions between
`FOCUSED` and `ALERTING` with timestamps and prints `face missing` once per
absence after the configured timeout. Video frames are processed locally in
memory.

Run `python daemon/vision.py --debug` for a live preview with the angles and
current state overlaid. Press **Q** or **Esc** in the preview, or **Ctrl+C** in
your terminal, to stop.

### Attention settings and alert sound

Edit `config.json` after the first calibration and restart LockIn to apply
changes. The generated file contains your baseline and these defaults.

| Setting | Default | Meaning |
| --- | --- | --- |
| `yaw_threshold` | 28° | Left or right offset from the calibrated baseline |
| `pitch_threshold` | 20° | Downward offset from the calibrated baseline |
| `missing_seconds` | 2 | Time without a face before it counts as looking away |
| `grace_seconds` | 3 | Continuous time away before the alert starts |
| `recovery_seconds` | 1 | Continuous time back on screen before the alert ends |
| `repeat_seconds` | 5 | Minimum interval between alert sound starts |
| `calibration_seconds` | 3 | Countdown and baseline sampling duration |
| `smoothing_frames` | 5 | Number of recent angle readings to average |

While alerting, LockIn plays `assets/alert.wav` using macOS's built-in `afplay`.
To change the placeholder chime, replace that file with a WAV of your choice.
If your sound lasts longer than the repeat interval, the next play waits until
the current one finishes.

### Camera permission on macOS

When macOS prompts for camera access, click **Allow**. If you previously denied
access, open **System Settings → Privacy & Security → Camera** and enable access
for the app you launched Python from, such as Terminal, iTerm, or your IDE.
Quit and reopen that app, then run the script again. If the app isn't listed,
run the script from the app once to trigger the permission prompt.
