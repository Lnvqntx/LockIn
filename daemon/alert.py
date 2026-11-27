"""Play macOS alert and mode sounds without overlapping or blocking the camera."""

import subprocess
import sys
from pathlib import Path


class AudioAlert:
    def __init__(self, sound: Path, repeat_seconds: float):
        self.sound = sound
        self.repeat_seconds = repeat_seconds
        self.next_play_at = None
        self.player = None
        self.pending_cue = None

    def _play(self, sound: Path):
        try:
            self.player = subprocess.Popen(["afplay", str(sound)])
        except OSError as error:
            print(f"Audio error: {error}", file=sys.stderr, flush=True)

    def cue(self, sound: Path):
        self._stop_player()
        self.next_play_at = None
        self.pending_cue = sound

    def update(self, now: float, active: bool):
        if self.player is not None and self.player.poll() is not None:
            self.player = None
        if not active:
            self.next_play_at = None
        if self.player is not None:
            return
        if self.pending_cue is not None:
            sound = self.pending_cue
            self.pending_cue = None
            self._play(sound)
        elif active and (self.next_play_at is None or now >= self.next_play_at):
            self.next_play_at = now + self.repeat_seconds
            self._play(self.sound)

    def _stop_player(self):
        if self.player is not None and self.player.poll() is None:
            self.player.kill()

    def close(self):
        self._stop_player()
        if self.player is not None:
            self.player.wait()
            self.player = None
