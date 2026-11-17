"""Local bridge between the browser extension and the desktop app.

Protocol (JSON over HTTP, 127.0.0.1 only):
    POST /v1/heartbeat   extension -> app, every ~4s while the browser runs
        {tabId, host, shorts, swipes, audible, active, incognito}
      reply: {"ok": true, "commands": [{"type": "close", "match": "shorts" | "<domain>"}]}
    GET  /v1/ping        health check

Only a hostname and a few booleans are sent: never full URLs, page titles or content.
Requests must carry `X-PHI: 1` and an extension Origin, so ordinary web pages cannot spoof events.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import PORT


class Bridge:
    """Thread-safe mailbox shared by the HTTP thread and the Qt engine."""

    def __init__(self):
        self._lock = threading.Lock()
        self._latest: dict | None = None
        self._commands: list[dict] = []

    def push(self, event: dict) -> None:
        event["_rx"] = time.time()
        with self._lock:
            self._latest = event

    def fresh(self, max_age: float) -> dict | None:
        with self._lock:
            hb = self._latest
        if hb and time.time() - hb["_rx"] <= max_age:
            return hb
        return None

    def queue_command(self, command: dict) -> None:
        with self._lock:
            self._commands.append(command)

    def pop_commands(self) -> list[dict]:
        with self._lock:
            out, self._commands = self._commands, []
        return out


def _make_handler(bridge: Bridge):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = 5          # a client that stops talking is dropped after 5 s instead of holding a thread forever

        def log_message(self, *args):  # silence
            pass

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin", "")
            return origin.startswith(("chrome-extension://", "moz-extension://"))

        def _send(self, code: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            origin = self.headers.get("Origin", "")
            if self._origin_ok():
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            try:
                self.wfile.write(data)
            except OSError:
                pass                                   # the client already hung up

        def do_OPTIONS(self):
            if not self._origin_ok():
                return self._send(403, {"ok": False})
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", ""))
            self.send_header("Access-Control-Allow-Headers", "content-type, x-phi")
            self.send_header("Access-Control-Allow-Methods", "POST, GET")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if self.path == "/v1/ping":
                return self._send(200, {"app": "phi", "v": 1})
            self._send(404, {"ok": False})

        def do_POST(self):
            if self.path != "/v1/heartbeat":
                return self._send(404, {"ok": False})
            if self.headers.get("X-PHI") != "1" or not self._origin_ok():
                return self._send(403, {"ok": False})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 4096:
                    return self._send(413, {"ok": False})
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError
            except OSError:
                self.close_connection = True      # the client stalled or vanished mid-body: just hang up
                return
            except (ValueError, TypeError):
                return self._send(400, {"ok": False})
            event = {
                "tabId": _int(payload.get("tabId")),
                "host": _text(payload.get("host"))[:253],
                "shorts": bool(payload.get("shorts")),
                "swipes": max(0, _int(payload.get("swipes"))),
                "audible": bool(payload.get("audible")),
                "active": bool(payload.get("active")),
                "incognito": bool(payload.get("incognito")),
            }
            bridge.push(event)
            self._send(200, {"ok": True, "commands": bridge.pop_commands()})

    return Handler


def _int(value) -> int:
    """A whole number from whatever the extension sent; anything unusable becomes 0 (never an exception)."""
    try:
        if isinstance(value, bool):
            return int(value)
        n = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0
    return n if -2**31 <= n < 2**31 else 0


def _text(value) -> str:
    return value if isinstance(value, str) else ""


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False              # on Windows reuse would let a second program share PHI's port silently

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)   # nobody else may bind this port
        super().server_bind()

    def handle_error(self, request, client_address):
        pass                                  # a client that hung up mid-request is normal, not a traceback on stderr


class BridgeServer:
    def __init__(self, bridge: Bridge, port: int = PORT):
        self.bridge, self.port = bridge, port
        self._httpd: ThreadingHTTPServer | None = None
        self.error: str | None = None

    def start(self) -> bool:
        try:
            self._httpd = _Server(("127.0.0.1", self.port), _make_handler(self.bridge))
        except OSError as exc:
            self.error = str(exc)
            return False
        threading.Thread(target=self._httpd.serve_forever, name="phi-bridge", daemon=True).start()
        return True

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
