"""Manage the per-user macOS login launcher."""

import plistlib
from pathlib import Path
from tempfile import NamedTemporaryFile

LABEL = "com.lockin.daemon"


def launch_agent_path():
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def set_launch_at_login(enabled, launcher, path):
    if not enabled:
        path.unlink(missing_ok=True)
        return

    launcher = launcher.resolve(strict=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            plistlib.dump({
                "Label": LABEL,
                "ProgramArguments": ["/bin/sh", str(launcher)],
                "WorkingDirectory": str(launcher.parent),
                "RunAtLoad": True,
                "LimitLoadToSessionType": "Aqua",
            }, temporary)
            temporary.close()
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)
