# LockIn architecture

`run.sh` activates the repository's virtual environment and starts
`python -m daemon.vision --menubar`. In menu bar mode, rumps runs the UI on the
main thread and exchanges commands and events with the vision worker through
queues. The WebSocket server has its own thread and asyncio event loop.
`--debug` runs a separate mode with an OpenCV preview.

## Daemon components

| Component | Responsibility |
| --- | --- |
| [Vision loop](../daemon/vision.py) | Captures webcam frames with OpenCV, runs MediaPipe Face Landmarker in video mode, and derives yaw and pitch from the facial transformation matrix. Calibration averages samples from a continuous window of valid face poses and retries up to three times if the attempt loses the face pose. |
| [Attention state machine](../daemon/state.py) | Smooths angles, compares offsets against the calibrated baseline, and applies sensitivity, grace, recovery, and timeout settings. The code states are `IDLE`, `FOCUSED`, and `ALERTING`. The menu bar labels `FOCUSED` as **ARMED**. |
| [Audio](../daemon/alert.py) | Uses macOS `afplay` for non-overlapping playback of alerts, previews, and mode or calibration cues. A new cue stops current playback. |
| [Global hotkey](../daemon/hotkey.py) | Checks macOS keyboard permissions and uses pynput to queue a toggle. The default is Control + Option + L. The debug window supports Space when the global hotkey is unavailable. |
| [WebSocket server](../daemon/server.py) | Checks the request origin, tracks which tabs are busy on each connection, and queues changes between zero and one or more busy tabs. |
| [Session stats](../daemon/stats.py) | Accumulates time in `FOCUSED` and `ALERTING` and counts entries into `ALERTING`. Completed sessions are stored locally in `stats.json`. |

The vision loop processes webcam frames even while idle. Frames remain in
memory. When armed, an offset beyond the left/right yaw threshold, downward
pitch threshold, or a missing face beyond the configured duration counts as
away. Sustained time away triggers an alert. Sustained time back on screen
returns the state to `FOCUSED`.

With a valid baseline, a transition from no busy tabs to at least one can
arm an idle daemon. When the busy set becomes empty, an extension-owned
session disarms. A manual session has its own timeout and stays armed when
browser tabs finish. Manual disarm can suppress auto-arming for the current
busy period. Extension-owned sessions have a separate timeout.

## Browser extension

- [Content script](../extension/content.js) observes DOM changes and checks
  visible, enabled generation controls against [site selectors](../extension/sites.js).
  It reports `busy` or `idle` using Chrome runtime messaging. It does not read
  prompt or response text.
- [Background worker](../extension/background.js) validates the sender's
  hostname and tracks busy tabs by tab ID. It clears entries when tabs
  close or navigate, sends heartbeats, and resends current busy states
  when its WebSocket reconnects.
- [Popup](../extension/popup.js) displays connection status and busy tabs.
  It manages the automation toggle and port through worker messages.
  The browser stores those settings in extension storage.

## WebSocket protocol

The worker connects to `ws://127.0.0.1:<websocket_port>` (default `8765`).
The server binds to that IPv4 loopback address. At handshake it requires
exactly one `Origin` header beginning with `chrome-extension://`. A missing,
duplicate, or mismatched header gets HTTP 403. The prefix check does not
identify a particular extension.

Generation messages are JSON. The `source` must be one of `claude.ai`,
`chatgpt.com`, `chat.openai.com`, or `gemini.google.com`, and `tab` must be a
nonnegative integer. A busy message adds the pair for that connection. An
idle message removes it. The source and tab ID travel over loopback. Page
URLs, conversation text, and camera frames are absent from these messages.

```json
{"type":"busy","source":"claude.ai","tab":123}
```

```json
{"type":"idle","source":"claude.ai","tab":123}
```

The two heartbeat messages are application-level JSON, separate from
WebSocket protocol control frames.

| Direction | JSON | Behavior |
| --- | --- | --- |
| Worker → daemon | `{"type":"ping"}` | Sent on connection and every 20 seconds while the connection is healthy. |
| Daemon → worker | `{"type":"pong"}` | Acknowledges a heartbeat. |

The server removes all busy entries for a connection when it disconnects
or times out after 50 seconds without an application heartbeat. Busy entries
that belong to other connections remain active.
