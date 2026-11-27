"""Keep Cocoa on the main thread and exchange commands with the vision worker."""

from queue import Empty, SimpleQueue
from threading import Event, Thread

if __package__:
    from .login import launch_agent_path, set_launch_at_login
else:
    from login import launch_agent_path, set_launch_at_login


def run_menubar(config, config_path, sounds, run_worker, *, always_armed=False):
    import rumps
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory, NSWorkspace

    commands = SimpleQueue()
    events = SimpleQueue()
    stop = Event()
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    app = rumps.App("LockIn", title="IDLE", quit_button=None)

    def send(command, value=None):
        return lambda _: commands.put((command, value))

    def open_config(_):
        if not config_path.is_file():
            rumps.alert("LockIn", "Recalibrate to create config.json.")
        elif not NSWorkspace.sharedWorkspace().openFile_(str(config_path)):
            rumps.alert("LockIn", f"Could not open {config_path}.")

    agent_path = launch_agent_path()

    def toggle_login(item):
        enabled = not agent_path.is_file()
        try:
            set_launch_at_login(enabled, config_path.parent / "run.sh", agent_path)
        except OSError as error:
            rumps.alert("LockIn", f"Could not change launch at login: {error}")
        item.state = int(agent_path.is_file())

    def reset_stats(_):
        if rumps.alert("Reset stats?", "This clears the local session history.", cancel="Cancel"):
            commands.put(("reset_stats", None))

    def quit_app(_):
        shutdown()
        rumps.quit_application()

    status = rumps.MenuItem("Starting camera…")
    extension_status = rumps.MenuItem("Extension: not connected")
    pending_reason = "Starting camera" if config.has_baseline else "Calibration required"
    toggle = rumps.MenuItem(f"Arm ({config.hotkey}) — {pending_reason}")
    today = rumps.MenuItem("Today · 0 sessions · 0% focus · 0 alerts")
    reset = rumps.MenuItem("Reset stats")
    login = rumps.MenuItem("Launch at login", callback=toggle_login)
    login.state = int(agent_path.is_file())
    recalibrate = rumps.MenuItem("Recalibrate", callback=send("calibrate"))
    sensitivity = rumps.MenuItem("Sensitivity")
    sensitivity_items = {
        level: rumps.MenuItem(level)
        for level in ("Low", "Medium", "High")
    }
    sensitivity.update(sensitivity_items.values())
    sound_menu = rumps.MenuItem("Alert sound")
    sound_items = {
        name: rumps.MenuItem(name) for name in sounds
    }
    sound_menu.update(sound_items.values())
    app.menu = [
        status, extension_status, toggle, recalibrate, sensitivity, sound_menu,
        today, reset, login,
        rumps.MenuItem("Open config.json", callback=open_config),
        rumps.MenuItem("Quit", callback=quit_app),
    ]

    def enable_settings(enabled):
        for name, item in sensitivity_items.items():
            item.set_callback(send("sensitivity", name) if enabled else None)
        for name, item in sound_items.items():
            item.set_callback(send("sound", name) if enabled else None)

    def mark_settings(level, sound):
        for name, item in sensitivity_items.items():
            item.state = int(name == level)
        for name, item in sound_items.items():
            item.state = int(name == sound)

    def update_menu(_):
        while True:
            try:
                kind, value = events.get_nowait()
            except Empty:
                return
            if kind == "mode":
                app.title = value
                status.title = value
                action = "Arm" if value == "IDLE" else "Disarm"
                toggle.title = f"{action} ({config.hotkey})"
                if always_armed:
                    toggle.title += " — Always armed"
                toggle.set_callback(None if always_armed else send("toggle"))
                enable_settings(True)
            elif kind == "extension":
                extension_status.title = f"Extension: {'connected' if value else 'not connected'}"
            elif kind == "stats":
                today.title = value
                reset.set_callback(reset_stats)
            elif kind == "calibration_retry":
                app.title = "Face not found"
                status.title = value
                toggle.title = f"Arm ({config.hotkey}) — Calibration in progress"
                toggle.set_callback(None)
                enable_settings(False)
            elif kind == "countdown":
                app.title = f"Look at screen {value}…"
                status.title = app.title
                toggle.title = f"Arm ({config.hotkey}) — Calibration in progress"
                toggle.set_callback(None)
                enable_settings(False)
            elif kind == "settings":
                mark_settings(*value)
            elif kind == "needs_calibration":
                app.title = "IDLE"
                toggle.title = f"Arm ({config.hotkey}) — Calibration required"
                toggle.set_callback(None)
                enable_settings(False)
            elif kind == "message":
                status.title = value
            elif kind == "failure":
                app.title, status.title = value
                toggle.title = f"Arm ({config.hotkey}) — {app.title}"
                reset.set_callback(None)
                toggle.set_callback(None)
                recalibrate.set_callback(None)
                enable_settings(False)

    mark_settings(config.sensitivity, config.alert_sound)
    worker = Thread(target=run_worker, args=(commands, events, stop), name="LockIn vision")
    timer = rumps.Timer(update_menu, 0.1)

    def shutdown():
        if not stop.is_set():
            stop.set()
            timer.stop()
            worker.join()

    rumps.events.before_quit.register(shutdown)
    worker.start()
    try:
        timer.start()
        app.run()
    finally:
        shutdown()
        rumps.events.before_quit.unregister(shutdown)
