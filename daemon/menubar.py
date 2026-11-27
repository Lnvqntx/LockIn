"""Keep Cocoa on the main thread and exchange commands with the vision worker."""

from queue import Empty, SimpleQueue
from threading import Event, Thread


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

    def quit_app(_):
        shutdown()
        rumps.quit_application()

    status = rumps.MenuItem("Starting camera…")
    extension_status = rumps.MenuItem("Extension: not connected")
    toggle = rumps.MenuItem(f"Arm ({config.hotkey})")
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
                toggle.set_callback(None if always_armed else send("toggle"))
                enable_settings(True)
            elif kind == "extension":
                extension_status.title = f"Extension: {'connected' if value else 'not connected'}"
            elif kind == "countdown":
                app.title = f"Look at screen {value}…"
                status.title = app.title
                toggle.set_callback(None)
                enable_settings(False)
            elif kind == "settings":
                mark_settings(*value)
            elif kind == "needs_calibration":
                app.title = "IDLE"
                toggle.set_callback(None)
                enable_settings(False)
            elif kind == "message":
                status.title = value
            elif kind == "failure":
                app.title, status.title = value
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
