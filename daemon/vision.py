"""Track screen attention from the webcam using MediaPipe Face Landmarker."""

import argparse
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe as mp

if __package__:
    from .alert import AudioAlert
    from .state import AttentionTracker, Config, State
else:
    from alert import AudioAlert
    from state import AttentionTracker, Config, State

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
SOUND_PATH = ROOT / "assets" / "alert.wav"
DEFAULT_MODEL = Path(__file__).with_name("face_landmarker.task")
WINDOW_NAME = "LockIn Vision"


def head_angles(matrix):
    # MediaPipe's canonical face points toward +Z. Its camera space has +X
    # to image right and +Y up. The third column is the transformed forward
    # vector, so translation, uniform scale, and head roll do not affect it.
    x, y, z = (float(matrix[row, 2]) for row in range(3))
    yaw = math.degrees(math.atan2(-x, z))
    pitch = math.degrees(math.atan2(y, math.hypot(x, z)))
    return yaw, pitch


def run_camera(landmarker, debug, config, calibrate):
    backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
    camera = cv2.VideoCapture(0, backend)
    alert = AudioAlert(SOUND_PATH, config.repeat_seconds)
    window_open = False
    try:
        if not camera.isOpened():
            raise RuntimeError("Could not open the webcam. Check camera permissions.")

        started_at = time.monotonic()
        tracker = None if calibrate else AttentionTracker(config, started_at)
        calibration_ends_at = started_at + config.calibration_seconds
        calibration_samples = []
        last_countdown = None
        last_timestamp_ms = -1
        missing_reported = False

        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Could not read a frame from the webcam.")

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

            if tracker is None and now >= calibration_ends_at:
                if not calibration_samples:
                    raise RuntimeError("No face detected during calibration. Try --calibrate again.")
                yaws, pitches = zip(*calibration_samples)
                config.baseline_yaw = sum(yaws) / len(yaws)
                config.baseline_pitch = sum(pitches) / len(pitches)
                config.save(CONFIG_PATH)
                print(f"Calibration saved to {CONFIG_PATH}", flush=True)
                tracker = AttentionTracker(config, now)

            if tracker is None:
                countdown = math.ceil(calibration_ends_at - now)
                overlay = f"Look at your screen ({countdown})"
                if countdown != last_countdown:
                    print(overlay, flush=True)
                    last_countdown = countdown
                if angles is not None:
                    calibration_samples.append(angles)
            else:
                previous_state = tracker.state
                state = tracker.update(now, face_detected, angles)
                if state != previous_state:
                    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
                    print(f"[{timestamp}] {previous_state.value} -> {state.value}", flush=True)
                alert.update(now, state is State.ALERTING)

                if angles is not None:
                    yaw, pitch = angles
                    overlay = f"Yaw {yaw:+.1f} deg | Pitch {pitch:+.1f} deg"
                    print(overlay, flush=True)
                elif tracker.face_missing:
                    overlay = "face missing"
                    if not missing_reported:
                        print(overlay, flush=True)
                else:
                    overlay = "Face detected" if face_detected else "Looking for face"
                missing_reported = tracker.face_missing
                overlay = f"{state.value} | {overlay}"

            if debug:
                cv2.putText(
                    frame, overlay, (16, 32), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 0), 2, cv2.LINE_AA,
                )
                cv2.imshow(WINDOW_NAME, frame)
                window_open = True
                if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
                    break
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        camera.release()
        try:
            if window_open:
                cv2.destroyAllWindows()
        finally:
            alert.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Show the live webcam preview.")
    parser.add_argument("--calibrate", action="store_true", help="Record a new screen-facing baseline.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Path to the .task model.")
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error(f"Model not found at {args.model}. See README.md for the download command.")

    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        output_facial_transformation_matrixes=True,
    )
    try:
        try:
            config = Config.load(CONFIG_PATH)
        except FileNotFoundError:
            config = Config()
            args.calibrate = True
        with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
            run_camera(landmarker, args.debug, config, args.calibrate)
    except KeyboardInterrupt:
        return 0
    except (RuntimeError, ValueError, OSError, cv2.error) as error:
        print(f"Vision error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
