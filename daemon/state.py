"""Configuration and the attention state machine."""

import json
import math
from collections import deque
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile


SENSITIVITY_SCALE = {"Low": 1.25, "Medium": 1.0, "High": 0.75}


@dataclass
class Config:
    baseline_yaw: float | None = None
    baseline_pitch: float | None = None
    yaw_threshold: float = 28.0
    pitch_threshold: float = 20.0
    missing_seconds: float = 2.0
    grace_seconds: float = 3.0
    recovery_seconds: float = 1.0
    repeat_seconds: float = 5.0
    calibration_seconds: float = 3.0
    smoothing_frames: int = 5
    hotkey: str = "<ctrl>+<alt>+l"
    armed_timeout_seconds: float = 300.0
    websocket_port: int = 8765
    extension_timeout_seconds: float = 1200.0
    sensitivity: str = "Medium"
    alert_sound: str = "alert.wav"

    @property
    def has_baseline(self):
        return self.baseline_yaw is not None and self.baseline_pitch is not None

    @classmethod
    def load(cls, path: Path):
        values = json.loads(path.read_text(encoding="utf-8"))
        config = cls()
        if not isinstance(values, dict):
            raise ValueError("config.json must contain a JSON object.")
        for field in fields(config):
            value = values.get(field.name, getattr(config, field.name))
            if field.name == "smoothing_frames":
                valid = type(value) is int and value >= 1
            elif field.name == "websocket_port":
                valid = type(value) is int and 1 <= value <= 65535
            elif field.name == "hotkey":
                valid = isinstance(value, str) and bool(value.strip())
            elif field.name == "sensitivity":
                valid = isinstance(value, str) and value in SENSITIVITY_SCALE
            elif field.name == "alert_sound":
                valid = isinstance(value, str) and bool(value) and Path(value).name == value
            elif field.name.startswith("baseline_") and value is None:
                valid = True
            else:
                valid = type(value) in (int, float) and math.isfinite(value)
                if valid and not field.name.startswith("baseline_"):
                    valid = value > 0
            if not valid:
                raise ValueError(f"Invalid config value for {field.name}: {value!r}")
            setattr(config, field.name, value)
        return config

    def save(self, path: Path):
        write_json(path, asdict(self))


def write_json(path, value):
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            json.dump(value, temporary, indent=2)
            temporary.write("\n")
            temporary.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


class State(Enum):
    IDLE = "IDLE"
    FOCUSED = "FOCUSED"
    ALERTING = "ALERTING"


class AttentionTracker:
    def __init__(self, config: Config):
        self.config = config
        self.state = State.IDLE
        self.armed = False
        self.armed_since = None
        self.armed_by_extension = False
        self.samples = deque(maxlen=config.smoothing_frames)
        self.face_missing = False
        self.last_face_at = None
        self.away_since = None
        self.on_screen_since = None

    def set_armed(self, armed: bool, now: float, *, by_extension=False):
        if self.armed == armed:
            return
        self.armed = armed
        self.armed_by_extension = armed and by_extension
        self.armed_since = now if armed else None
        self.state = State.FOCUSED if armed else State.IDLE
        self.samples.clear()
        self.face_missing = False
        self.last_face_at = now
        self.away_since = None
        self.on_screen_since = None

    def update(self, now: float, face_detected: bool, angles, *, always_armed=False):
        """Process one frame and return the current state."""
        if not self.armed:
            return self.state
        timeout = (
            self.config.extension_timeout_seconds if self.armed_by_extension
            else self.config.armed_timeout_seconds
        )
        if not always_armed and now - self.armed_since >= timeout:
            self.set_armed(False, now)
            return self.state

        if face_detected:
            self.last_face_at = now
        self.face_missing = now - self.last_face_at >= self.config.missing_seconds

        scale = SENSITIVITY_SCALE[self.config.sensitivity]
        away = None
        if angles is not None:
            self.samples.append(angles)
            yaws, pitches = zip(*self.samples)
            yaw_offset = sum(yaws) / len(yaws) - self.config.baseline_yaw
            pitch_offset = sum(pitches) / len(pitches) - self.config.baseline_pitch
            away = (
                abs(yaw_offset) > self.config.yaw_threshold * scale
                or -pitch_offset > self.config.pitch_threshold * scale
            )
        else:
            self.samples.clear()
            if self.face_missing:
                away = True

        if away is True:
            self.on_screen_since = None
            if self.away_since is None:
                self.away_since = now
            if now - self.away_since >= self.config.grace_seconds * scale:
                self.state = State.ALERTING
        elif away is False:
            self.away_since = None
            if self.on_screen_since is None:
                self.on_screen_since = now
            if now - self.on_screen_since >= self.config.recovery_seconds:
                self.state = State.FOCUSED
        else:
            self.away_since = None
            self.on_screen_since = None

        return self.state
