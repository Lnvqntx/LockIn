"""Local per-session totals, using elapsed time instead of camera frame counts."""

import json
import sys
from datetime import datetime

if __package__:
    from .state import State, write_json
else:
    from state import State, write_json


class SessionStats:
    def __init__(self, path):
        self.path = path
        self.current = None
        self.previous = State.IDLE
        self.last_at = None
        self.records = []
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                raise ValueError("expected a list of sessions")
            for session in records:
                datetime.fromisoformat(session["start_time"])
                for key in ("focused_seconds", "distracted_seconds", "alert_count"):
                    if type(session[key]) not in (int, float) or session[key] < 0:
                        raise ValueError(f"invalid value for {key}")
            self.records = records
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError) as error:
            print(f"Could not read statistics: {error}", file=sys.stderr)

    def update(self, now, state):
        """Record time in the previous state up to this observation."""
        changed = state is not self.previous
        if self.current is not None:
            key = "distracted_seconds" if self.previous is State.ALERTING else "focused_seconds"
            self.current[key] += now - self.last_at

        if state is State.IDLE and self.current is not None:
            self.records.append(self.current)
            self.current = None
            self._save()
        elif state is not State.IDLE:
            if self.current is None:
                self.current = {
                    "start_time": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "focused_seconds": 0.0,
                    "distracted_seconds": 0.0,
                    "alert_count": 0,
                }
            if state is State.ALERTING and changed:
                self.current["alert_count"] += 1
        self.previous = state
        self.last_at = now
        return changed

    def _save(self):
        records = [
            dict(row, duration_seconds=row["focused_seconds"] + row["distracted_seconds"])
            for row in self.records
        ]
        try:
            write_json(self.path, records)
        except OSError as error:
            print(f"Could not save statistics: {error}", file=sys.stderr)
            return False
        return True

    def reset(self, now):
        old_records = self.records
        self.records = []
        if not self._save():
            self.records = old_records
            return False
        if self.current is not None:
            state = self.previous
            self.current = None
            self.update(now, state)
        return True

    def summary(self):
        today = datetime.now().astimezone().date()
        rows = [
            row for row in self.records
            if datetime.fromisoformat(row["start_time"]).astimezone().date() == today
        ]
        if self.current is not None and datetime.fromisoformat(self.current["start_time"]).date() == today:
            rows.append(self.current)
        focused = sum(row["focused_seconds"] for row in rows)
        total = focused + sum(row["distracted_seconds"] for row in rows)
        percent = 100 * focused / total if total else 0
        alerts = sum(row["alert_count"] for row in rows)
        session_label = "session" if len(rows) == 1 else "sessions"
        alert_label = "alert" if alerts == 1 else "alerts"
        return f"Today · {len(rows)} {session_label} · {percent:.0f}% focus · {alerts} {alert_label}"
