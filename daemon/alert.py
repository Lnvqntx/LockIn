"""Repeat an audible macOS alert without blocking the camera loop."""

import subprocess
import sys
from pathlib import Path


class AudioAlert:
    def __init__(self, sound: Path, repeat_seconds: float):
        self.sound = sound
        self.repeat_seconds = repeat_seconds
        self.next_play_at = None
        self.player = None

    def update(self, now: float, active: bool):
        if self.player is not None and self.player.poll() is not None:
            self.player = None
        if not active:
            self.next_play_at = None
            return
        if self.player is not None:
            return
        if self.next_play_at is not None and now < self.next_play_at:
            return

        self.next_play_at = now + self.repeat_seconds
        try:
            self.player = subprocess.Popen(["afplay", str(self.sound)])
        except OSError as error:
            print(f"Audio alert error: {error}", file=sys.stderr, flush=True)

    def close(self):
        if self.player is not None:
            if self.player.poll() is None:
                self.player.terminate()
            self.player.wait()
            self.player = None
