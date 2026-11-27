# LockIn Chrome extension

Chromium 116 or later is required (Chrome, Arc, Edge, or Brave). Safari is unsupported.
The extension is plain JavaScript and runs directly from this directory.

## Install

1. Follow the main README to set up LockIn. Start it with `./run.sh` for menu
   bar mode, or `.venv/bin/python -m daemon.vision --debug` for the video preview.
2. Open `chrome://extensions` and turn on **Developer mode**.
3. Click **Load unpacked** and select this repository's `extension/` directory.
4. Reload any already-open Claude, ChatGPT, or Gemini tabs so the content script loads.
5. Open the LockIn toolbar popup. It should show **Connected**. The default
   port is **8765**. If you change `websocket_port` in the daemon's
   `config.json`, restart the daemon and save the same port in the popup.

The popup lists busy tabs by site and tab ID. Disabling automation in the
popup closes the local connection. The extension inspects generation buttons
and sends only busy/idle state, site, and tab ID to the local daemon. It never
reads or transfers conversation text.

## Troubleshooting

- **Not connected** means the daemon is unreachable on the configured port.
  Check that it is running and that the extension port matches
  `websocket_port`. The daemon logs connection errors in Terminal.
- **Connected but generation isn't detected** usually means the site changed
  its Stop button. While a response generates, use Chrome DevTools to inspect
  that button's attributes. Update the matching site's selectors or
  accessible-label pattern in the `SITE_CONFIG` object in [sites.js](sites.js).
  Prefer a stable `data-testid` or `aria-label`.
  Reload LockIn on `chrome://extensions` and then reload the affected tab.
- If another busy tab is still listed, the daemon stays armed until that tab
  goes idle too. A manual disarm suppresses automation until a new group of
  busy tabs starts.

The selector presets for Claude, ChatGPT (both hostnames), and Gemini are
fixture-tested. Their live signed-in pages remain unverified.
