"""Track screen attention from the webcam using MediaPipe Face Landmarker."""

import argparse
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from queue import Empty

import cv2
import mediapipe as mp

if __package__:
    from .alert import AudioAlert
    from .hotkey import ArmHotkey
    from .menubar import run_menubar
    from .state import AttentionTracker, Config, State
else:
    from alert import AudioAlert
    from hotkey import ArmHotkey
    from menubar import run_menubar
    from state import AttentionTracker, Config, State

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
ASSETS = ROOT / "assets"
DEFAULT_MODEL = Path(__file__).with_name("face_landmarker.task")
WINDOW_NAME = "LockIn Vision"
CAMERA_HELP = "Camera access needed: System Settings > Privacy & Security > Camera"
AUDIO_EXTENSIONS = {".wav", ".aif", ".aiff", ".caf", ".m4a", ".mp3", ".aac"}


class CameraError(RuntimeError):
    pass


def menu_mode(state):
    return "ARMED" if state is State.FOCUSED else state.value


def head_angles(matrix):
    # MediaPipe's canonical face points toward +Z. Its camera space has +X
    # to image right and +Y up. The third column is the transformed forward
    # vector, so translation, uniform scale, and head roll do not affect it.
    x, y, z = (float(matrix[row, 2]) for row in range(3))
    yaw = math.degrees(math.atan2(-x, z))
    pitch = math.degrees(math.atan2(y, math.hypot(x, z)))
    return yaw, pitch


def log_transition(before, after, reason=None):
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    detail = f" ({reason})" if reason else ""
    print(f"[{timestamp}] {before.value} -> {after.value}{detail}", flush=True)


def run_camera(
    landmarker, debug, config, calibrate, always_armed=False,
    *, commands=None, events=None, stop=None, sounds=(),
):
    backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
    try:
        camera = cv2.VideoCapture(0, backend)
    except cv2.error as error:
        raise CameraError("Could not open the webcam. Check camera permissions.") from error
    alert = AudioAlert(ASSETS / config.alert_sound, config.repeat_seconds)
    hotkey = None
    window_open = False
    try:
        if not camera.isOpened():
            raise CameraError("Could not open the webcam. Check camera permissions.")

        tracker = AttentionTracker(config)
        if not always_armed:
            hotkey = ArmHotkey(config.hotkey)
        fallback_toggle = False
        started_at = time.monotonic()
        calibration_ends_at = started_at + config.calibration_seconds
        calibration_samples = []
        last_countdown = None
        last_timestamp_ms = -1
        missing_reported = False
        has_baseline = not calibrate or CONFIG_PATH.is_file()
        if events is not None and not calibrate:
            events.put(("mode", "IDLE"))

        while stop is None or not stop.is_set():
            try:
                ok, frame = camera.read()
            except cv2.error as error:
                raise CameraError("Could not read a frame from the webcam.") from error
            if not ok:
                raise CameraError("Could not read a frame from the webcam.")

            if stop is not None and stop.is_set():
                break
            now = time.monotonic()
            timestamp_ms = max(last_timestamp_ms + 1, int((now - started_at) * 1000))
            last_timestamp_ms = timestamp_ms
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(image, timestamp_ms)
            face_detected = bool(result.face_landmarks)
            angles = None
            if face_detected and result.facial_transformation_matrixes:
                angles = head_angles(result.facial_transformation_matrixes[0])

            toggle_requested = fallback_toggle
            fallback_toggle = False

            if commands is not None:
                while True:
                    try:
                        command, value = commands.get_nowait()
                    except Empty:
                        break
                    if command == "toggle" and not calibrate and has_baseline:
                        toggle_requested = not toggle_requested
                    elif command == "calibrate":
                        if tracker.armed:
                            log_transition(tracker.state, State.IDLE, "recalibrating")
                            tracker.set_armed(False, now)
                        calibrate = True
                        calibration_ends_at = now + config.calibration_seconds
                        calibration_samples.clear()
                        last_countdown = None
                    elif command in ("sensitivity", "sound"):
                        old_sensitivity, old_sound = config.sensitivity, config.alert_sound
                        if command == "sensitivity":
                            config.sensitivity = value
                        elif value in sounds:
                            config.alert_sound = value
                        try:
                            if has_baseline:
                                config.save(CONFIG_PATH)
                        except OSError as error:
                            config.sensitivity, config.alert_sound = old_sensitivity, old_sound
                            events.put(("message", f"Could not save settings: {error}"))
                        else:
                            if command == "sensitivity" and config.sensitivity != old_sensitivity:
                                tracker.away_since = None
                            elif command == "sound" and value in sounds:
                                alert.sound = ASSETS / config.alert_sound
                                alert.cue(alert.sound)
                            events.put(("settings", (config.sensitivity, config.alert_sound)))

            calibration_confirmed = False
            if calibrate and now >= calibration_ends_at:
                calibrate = False
                message = None
                if not calibration_samples:
                    message = "No face detected during calibration. Choose Recalibrate to try again."
                    if events is None:
                        raise RuntimeError("No face detected during calibration. Try --calibrate again.")
                else:
                    previous_baseline = config.baseline_yaw, config.baseline_pitch
                    yaws, pitches = zip(*calibration_samples)
                    config.baseline_yaw = sum(yaws) / len(yaws)
                    config.baseline_pitch = sum(pitches) / len(pitches)
                    try:
                        config.save(CONFIG_PATH)
                    except OSError as error:
                        config.baseline_yaw, config.baseline_pitch = previous_baseline
                        if events is None:
                            raise
                        message = f"Could not save calibration: {error}"
                    else:
                        has_baseline = True
                        print(f"Calibration saved to {CONFIG_PATH}", flush=True)
                        if events is not None:
                            alert.cue(ASSETS / "calibrated.wav")
                            calibration_confirmed = True
                calibration_samples.clear()
                if events is not None:
                    events.put(("mode" if has_baseline else "needs_calibration", "IDLE"))
                    if message:
                        events.put(("message", message))

            hotkey_available = hotkey is not None and hotkey.available()
            if hotkey is not None and hotkey.take_toggle():
                toggle_requested = not toggle_requested

            if calibrate:
                countdown = math.ceil(calibration_ends_at - now)
                prompt = f"Look at your screen ({countdown})"
                overlay = f"IDLE | {prompt}"
                if countdown != last_countdown:
                    print(prompt, flush=True)
                    last_countdown = countdown
                    if events is not None:
                        events.put(("countdown", countdown))
                        alert.cue(ASSETS / "tick.wav")
                alert.update(now, False)
                if angles is not None:
                    calibration_samples.append(angles)
            else:
                previous_state = tracker.state
                was_armed = tracker.armed
                if always_armed and has_baseline:
                    tracker.set_armed(True, now)
                elif toggle_requested and has_baseline and not always_armed:
                    tracker.set_armed(not tracker.armed, now)

                state = tracker.update(now, face_detected, angles, always_armed=always_armed)
                if was_armed != tracker.armed:
                    if tracker.armed:
                        reason = "always armed" if always_armed else "armed"
                        if not calibration_confirmed:
                            alert.cue(ASSETS / "arm.wav")
                    else:
                        reason = "disarmed" if toggle_requested else "armed timeout"
                        alert.cue(ASSETS / "disarm.wav")
                    log_transition(previous_state, state, reason)
                elif state is not previous_state:
                    log_transition(previous_state, state)
                if events is not None and state is not previous_state:
                    events.put(("mode", menu_mode(state)))
                alert.update(now, state is State.ALERTING)

                if angles is not None:
                    yaw, pitch = angles
                    overlay = f"Yaw {yaw:+.1f} deg | Pitch {pitch:+.1f} deg"
                    if events is None:
                        print(overlay, flush=True)
                elif tracker.face_missing:
                    overlay = "face missing"
                    if not missing_reported:
                        print(overlay, flush=True)
                else:
                    overlay = "Face detected" if face_detected else "Looking for face"
                missing_reported = tracker.face_missing
                mode = f"ARMED / {state.value}" if tracker.armed else "IDLE"
                overlay = f"{mode} | {overlay}"

            if debug:
                cv2.putText(
                    frame, overlay, (16, 32), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0), 2, cv2.LINE_AA,
                )
                cv2.imshow(WINDOW_NAME, frame)
                window_open = True
                key = cv2.waitKey(1) & 0xFF
                if key == ord(" ") and not hotkey_available and not always_armed:
                    fallback_toggle = True
                if key in (27, ord("q")):
                    break
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        try:
            camera.release()
            if window_open:
                cv2.destroyAllWindows()
        finally:
            try:
                alert.close()
            finally:
                if hotkey is not None:
                    hotkey.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--debug", action="store_true", help="Show the live webcam preview.")
    mode.add_argument("--menubar", action="store_true", help="Run as a macOS menu bar app.")
    parser.add_argument("--calibrate", action="store_true", help="Record a new screen-facing baseline.")
    parser.add_argument(
        "--always-armed", action="store_true",
        help="Stay armed for testing, with no hotkey or automatic timeout.",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Path to the .task model.")
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error(f"Model not found at {args.model}. See README.md for the download command.")

    if args.menubar and sys.platform != "darwin":
        parser.error("--menubar requires macOS.")

    try:
        try:
            config = Config.load(CONFIG_PATH)
        except FileNotFoundError:
            config = Config()
            args.calibrate = True

        sounds = sorted(
            path.name for path in ASSETS.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        )
        if config.alert_sound not in sounds:
            config.alert_sound = "alert.wav"

        def run_worker(commands=None, events=None, stop=None):
            try:
                options = mp.tasks.vision.FaceLandmarkerOptions(
                    base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
                    running_mode=mp.tasks.vision.RunningMode.VIDEO,
                    output_facial_transformation_matrixes=True,
                )
                with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
                    run_camera(
                        landmarker, args.debug, config, args.calibrate, args.always_armed,
                        commands=commands, events=events, stop=stop, sounds=sounds,
                    )
            except (RuntimeError, ValueError, OSError, cv2.error) as error:
                if events is None:
                    raise
                print(f"Vision error: {error}", file=sys.stderr, flush=True)
                failure = ("Camera access needed", CAMERA_HELP) if isinstance(error, CameraError) else (
                    "LockIn error", f"Vision error: {error}",
                )
                events.put(("failure", failure))

        if args.menubar:
            run_menubar(config, CONFIG_PATH, sounds, run_worker, always_armed=args.always_armed)
        else:
            run_worker()
    except KeyboardInterrupt:
        return 0
    except (ImportError, RuntimeError, ValueError, OSError, cv2.error) as error:
        print(f"Vision error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
