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
            self.wfile.write(data)

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
            except (ValueError, TypeError):
                return self._send(400, {"ok": False})
            event = {
                "tabId": int(payload.get("tabId") or 0),
                "host": str(payload.get("host") or "")[:253],
                "shorts": bool(payload.get("shorts")),
                "swipes": int(payload.get("swipes") or 0),
                "audible": bool(payload.get("audible")),
                "active": bool(payload.get("active")),
                "incognito": bool(payload.get("incognito")),
            }
            bridge.push(event)
            self._send(200, {"ok": True, "commands": bridge.pop_commands()})

    return Handler


class BridgeServer:
    def __init__(self, bridge: Bridge, port: int = PORT):
        self.bridge, self.port = bridge, port
        self._httpd: ThreadingHTTPServer | None = None
        self.error: str | None = None

    def start(self) -> bool:
        try:
            self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), _make_handler(self.bridge))
        except OSError as exc:
            self.error = str(exc)
            return False
        self._httpd.daemon_threads = True
        threading.Thread(target=self._httpd.serve_forever, name="phi-bridge", daemon=True).start()
        return True

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
