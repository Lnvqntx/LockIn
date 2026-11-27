"""Receive Chrome generation state over a loopback-only WebSocket."""

import asyncio
import json
from datetime import datetime
from http import HTTPStatus
from threading import Event, Thread

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

HEARTBEAT_TIMEOUT = 50
SOURCES = {"claude.ai", "chatgpt.com", "chat.openai.com"}


def log(message):
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    print(f"[{timestamp}] Extension: {message}", flush=True)


def check_origin(connection, request):
    origins = request.headers.get_all("Origin")
    if len(origins) != 1 or not origins[0].startswith("chrome-extension://"):
        return connection.respond(HTTPStatus.FORBIDDEN, "Chrome extension Origin required.\n")
    return None


class ExtensionServer:
    def __init__(self, port, activity, menu_events=None):
        self.port = port
        self.activity = activity
        self.menu_events = menu_events
        self.connections = {}
        self.busy = set()
        self.stop = Event()
        self.thread = Thread(target=self._run, name="LockIn WebSocket")

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join()

    def _run(self):
        try:
            asyncio.run(self._serve())
        except OSError as error:
            log(f"could not listen on 127.0.0.1:{self.port}: {error}")
            self._connection_status(False)

    async def _serve(self):
        async with serve(
            self._handle, "127.0.0.1", self.port, process_request=check_origin,
            ping_interval=None, close_timeout=1, open_timeout=3, max_size=1024,
        ):
            log(f"listening on 127.0.0.1:{self.port}")
            while not self.stop.is_set():
                await asyncio.sleep(0.1)

    def _connection_status(self, connected):
        if self.menu_events is not None:
            self.menu_events.put(("extension", connected))

    def _update_busy(self):
        previous = bool(self.busy)
        self.busy = set().union(*self.connections.values())
        if bool(self.busy) != previous:
            self.activity.put(bool(self.busy))

    async def _handle(self, connection):
        entries = set()
        self.connections[connection] = entries
        self._connection_status(True)
        log("connected")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + HEARTBEAT_TIMEOUT
        try:
            while True:
                async with asyncio.timeout_at(deadline):
                    raw = await connection.recv()
                if loop.time() >= deadline:
                    raise TimeoutError
                try:
                    message = json.loads(raw)
                except (ValueError, UnicodeError):
                    continue
                if not isinstance(message, dict):
                    continue

                kind = message.get("type")
                if kind == "ping":
                    deadline = loop.time() + HEARTBEAT_TIMEOUT
                    await connection.send('{"type":"pong"}')
                    continue
                source, tab = message.get("source"), message.get("tab")
                if not isinstance(source, str) or source not in SOURCES or type(tab) is not int or tab < 0:
                    continue
                if kind == "busy":
                    entries.add((source, tab))
                elif kind == "idle":
                    entries.discard((source, tab))
                else:
                    continue
                self._update_busy()
        except ConnectionClosed:
            pass
        except TimeoutError:
            log("heartbeat missed")
            await connection.close(code=1008, reason="heartbeat timeout")
        finally:
            del self.connections[connection]
            self._update_busy()
            self._connection_status(bool(self.connections))
            log("disconnected")
