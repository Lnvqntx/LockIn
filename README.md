# LockIn

## Webcam head pose

### Setup on macOS

Run these commands from the repository root. The Python dependencies install
from prebuilt wheels on Intel Macs with Python 3.12, so no compiler, Xcode, or
Xcode Command Line Tools are needed. **Do not paste the whole setup block
twice.** If a command fails, fix the error and resume at that command.
The repository bundles the rumps wheel because PyPI publishes rumps as source.

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12
uv pip install -r requirements.txt --only-binary :all:
curl --fail --location \
  https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task \
  --output daemon/face_landmarker.task
./run.sh
```

On the first run, look at your screen during the three-second countdown. LockIn
averages the yaw and pitch it sees during that time and saves your baseline in
the repository's `config.json`. Run `.venv/bin/python daemon/vision.py --calibrate` to
record a new baseline while keeping your current settings. The countdown
appears in the terminal and in the preview when `--debug` is enabled.

### Menu bar mode

Run `./run.sh` from the repository root. It activates the virtual environment
and runs `python -m daemon.vision --menubar`. The title shows **IDLE**, **ARMED**,
or **ALERTING**. This mode uses the camera without opening a video window.
Use `--debug` separately for a video preview.

- **Arm/Disarm** shows your configured shortcut and works when macOS blocks
  the global hotkey.
- **Recalibrate** pauses monitoring. Look at your screen while the title counts
  down. A tick plays each second and a confirmation sounds when the baseline is
  saved. Arm again to resume monitoring.
- **Sensitivity** scales the configured yaw threshold, pitch threshold, and
  grace time by **1.25×** for Low, **1×** for Medium, or **0.75×** for High.
- **Alert sound** lists supported audio files in `assets/` at startup and
  previews the selected file. Sensitivity and sound choices are saved to
  `config.json`.
- **Open config.json** opens the saved settings in your default editor.
  **Quit** stops playback and releases the camera.

If the title displays **Camera access needed**, check **System Settings →
Privacy & Security → Camera** for the app you used to launch LockIn. Restart
LockIn after granting permission.

### Arm and disarm

LockIn starts **IDLE**. Press **Control + Option + L** to arm and press it again
to disarm. LockIn plays a short cue for each action. After five minutes armed,
it disarms and plays the disarm cue. Disarming immediately stops any active
attention alert.

Run `.venv/bin/python daemon/vision.py --debug` to show live angles and
`ARMED` or `IDLE` in the preview. Press **Q** or **Esc** in the preview, or
**Ctrl+C** in Terminal, to quit. For testing, add `--always-armed` to stay armed
without the global shortcut or automatic timeout.

If the global shortcut fails, open **System Settings → Privacy & Security**
and enable **Input Monitoring** and **Accessibility** for Terminal or the app
that launches LockIn. Restart that app and LockIn. You can also press **Space**
in the focused debug window when the global shortcut is unavailable.

The script prints yaw and pitch in degrees. Positive yaw means you turned to
your right, and positive pitch means you looked up. It timestamps transitions
between `IDLE`, `FOCUSED`, and `ALERTING`. Webcam frames stay in memory.

### Chrome automation

Install the unpacked [LockIn Chrome extension](extension/README.md) to arm
LockIn while Claude or ChatGPT generates a response. The daemon listens on
`127.0.0.1:8765` by default in both menu bar and debug modes. Its menu bar menu
shows whether an extension is connected.

The first busy tab arms LockIn. When the last one goes idle or its connection
drops, LockIn disarms and plays the disarm cue. Extension-driven sessions also
time out after 20 minutes by default. A manual disarm holds until the next
group of busy tabs, and a manually armed session follows the manual timeout.
The extension sends generation state, site, and tab ID over loopback. It
doesn't read or send conversation text.

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
| `hotkey` | `<ctrl>+<alt>+l` | Global arm/disarm shortcut in pynput syntax |
| `armed_timeout_seconds` | 300 | Time manually armed before automatic disarm |
| `websocket_port` | 8765 | Loopback port used by the Chrome extension |
| `extension_timeout_seconds` | 1200 | Time extension-armed before automatic disarm |
| `sensitivity` | Medium | Sensitivity preset applied to thresholds and grace time |
| `alert_sound` | `alert.wav` | Audio filename in `assets/` |

While alerting, LockIn plays the selected sound using macOS's built-in `afplay`.
The default alert is `assets/alert.wav`. The arm and disarm cues use
`assets/arm.wav` and `assets/disarm.wav`. Replace
any of these files with a WAV of your choice to change its sound.
If your sound lasts longer than the repeat interval, the next play waits until
the current one finishes.

### Camera permission on macOS

When macOS prompts for camera access, click **Allow**. If you previously denied
access, open **System Settings → Privacy & Security → Camera** and enable access
for the app you launched Python from, such as Terminal, iTerm, or your IDE.
Quit and reopen that app, then run the script again. If the app isn't listed,
run the script from the app once to trigger the permission prompt.
