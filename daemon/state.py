"""Configuration and the attention state machine."""

import json
import math
from collections import deque
from dataclasses import asdict, dataclass, fields
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass
class Config:
    baseline_yaw: float = 0.0
    baseline_pitch: float = 0.0
    yaw_threshold: float = 28.0
    pitch_threshold: float = 20.0
    missing_seconds: float = 2.0
    grace_seconds: float = 3.0
    recovery_seconds: float = 1.0
    repeat_seconds: float = 5.0
    calibration_seconds: float = 3.0
    smoothing_frames: int = 5

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
            else:
                valid = type(value) in (int, float) and math.isfinite(value)
                if valid and not field.name.startswith("baseline_"):
                    valid = value > 0
            if not valid:
                raise ValueError(f"Invalid config value for {field.name}: {value!r}")
            setattr(config, field.name, value)
        return config

    def save(self, path: Path):
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            try:
                json.dump(asdict(self), temporary, indent=2)
                temporary.write("\n")
                temporary.close()
                temporary_path.replace(path)
            finally:
                temporary_path.unlink(missing_ok=True)


class State(Enum):
    FOCUSED = "FOCUSED"
    ALERTING = "ALERTING"


class AttentionTracker:
    def __init__(self, config: Config, now: float):
        self.config = config
        self.state = State.FOCUSED
        self.face_missing = False
        self.last_face_at = now
        self.samples = deque(maxlen=config.smoothing_frames)
        self.away_since = None
        self.on_screen_since = None

    def update(self, now: float, face_detected: bool, angles):
        """Process one frame and return the current state."""
        if face_detected:
            self.last_face_at = now
        self.face_missing = now - self.last_face_at >= self.config.missing_seconds

        away = None
        if angles is not None:
            self.samples.append(angles)
            yaws, pitches = zip(*self.samples)
            yaw_offset = sum(yaws) / len(yaws) - self.config.baseline_yaw
            pitch_offset = sum(pitches) / len(pitches) - self.config.baseline_pitch
            away = (
                abs(yaw_offset) > self.config.yaw_threshold
                or -pitch_offset > self.config.pitch_threshold
            )
        else:
            self.samples.clear()
            if self.face_missing:
                away = True

        if away is True:
            self.on_screen_since = None
            if self.away_since is None:
                self.away_since = now
            if now - self.away_since >= self.config.grace_seconds:
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
