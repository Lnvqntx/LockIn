"""Global arm/disarm shortcut with a debug-window fallback."""

import sys
from queue import Empty, SimpleQueue


class ArmHotkey:
    def __init__(self, shortcut: str):
        self.listener = None
        self.toggles = SimpleQueue()
        try:
            from pynput import keyboard

            if sys.platform == "darwin":
                from HIServices import AXIsProcessTrusted
                from Quartz import CGPreflightListenEventAccess

                if not (AXIsProcessTrusted() and CGPreflightListenEventAccess()):
                    raise PermissionError("macOS keyboard access has not been granted")

            self.listener = keyboard.GlobalHotKeys({shortcut: self.request_toggle})
            self.listener.start()
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.close()
            self.report_unavailable(error)

    def report_unavailable(self, error):
        print(
            f"Global hotkey unavailable ({error}). On macOS, grant Terminal (or "
            "your launcher) Input Monitoring and Accessibility in System Settings > "
            "Privacy & Security, then restart Terminal and LockIn. "
            "Run with --debug to toggle with the spacebar in the preview.",
            file=sys.stderr,
            flush=True,
        )

    def available(self):
        if self.listener is not None and not self.listener.is_alive():
            self.close()
            self.report_unavailable("keyboard listener stopped")
        return self.listener is not None

    def request_toggle(self):
        self.toggles.put(None)

    def take_toggle(self):
        toggle = False
        while True:
            try:
                self.toggles.get_nowait()
            except Empty:
                return toggle
            toggle = not toggle

    def close(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
