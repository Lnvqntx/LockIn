# Security

LockIn processes webcam frames in memory and keeps session statistics on the
local machine. The extension checks generation controls and sends only
generation status, site hostname, tab ID, and heartbeats to the daemon.
The WebSocket server listens on `127.0.0.1` and checks for a
`chrome-extension://` Origin prefix. This check does not authenticate a
particular extension or other local clients.

Use GitHub Issues for ordinary bugs. For a vulnerability, use GitHub's
private vulnerability reporting if available. If it is unavailable, open an
issue asking for a private reporting channel and leave sensitive details
out of the public issue. [Issues](https://github.com/Lnvqntx/LockIn/issues) · [Security](https://github.com/Lnvqntx/LockIn/security)
