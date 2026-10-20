"""Extension-free browser detection via Windows UI Automation.

Reads the address bar of the focused Chromium window (Chrome, Edge, Brave, Vivaldi, Opera) in a worker
thread. Only the hostname, a Shorts flag and a private-window flag are kept in memory; the full URL is
never stored, logged or sent anywhere. The browser extension, when connected, takes priority.
"""
from __future__ import annotations

import re
import threading
import time
from urllib.parse import urlparse

POLL_SECONDS = 1.5
_SHORTS_ID = re.compile(r"^/shorts/([^/?#]+)")
_PRIVATE = re.compile(r"incognito|inprivate|private", re.I)


def parse_address(value: str) -> tuple[str, str | None]:
    """'youtube.com/shorts/abc' -> ('youtube.com', 'abc'). Returns ('', None) if it isn't an address."""
    value = (value or "").strip()
    if not value or " " in value:
        return "", None
    parsed = urlparse(value if "://" in value else "//" + value)
    host = (parsed.hostname or "").lower()
    if "." not in host and host != "localhost":
        return "", None
    m = _SHORTS_ID.match(parsed.path or "")
    shorts_id = m.group(1) if m and host.endswith("youtube.com") else None
    return host, shorts_id


class UrlReader:
    def __init__(self):
        self._target = 0
        self._lock = threading.Lock()
        self._result: dict | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.available = True

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="phi-urlreader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def set_target(self, hwnd: int) -> None:
        """hwnd of the focused browser window, or 0 when no browser is focused."""
        self._target = hwnd

    def latest(self, hwnd: int, max_age: float = 5.0) -> dict | None:
        with self._lock:
            r = self._result
        if r and r["hwnd"] == hwnd and time.time() - r["ts"] <= max_age:
            return r
        return None

    # ---- worker -----------------------------------------------------------
    def _find_omnibox(self, auto, hwnd: int):
        win = auto.ControlFromHandle(hwnd)
        edit = win.EditControl(searchDepth=14, ClassName="OmniboxViewViews")
        if not edit.Exists(1.0, 0.2):
            edit = win.EditControl(searchDepth=14, Name="Address and search bar")
            if not edit.Exists(1.0, 0.2):
                return None, win
        return edit, win

    def _run(self) -> None:
        try:
            import uiautomation as auto
        except Exception:
            self.available = False
            return
        with auto.UIAutomationInitializerInThread():
            cache: dict[int, tuple] = {}
            last_id: dict[int, str] = {}
            swipes: dict[int, int] = {}
            while not self._stop.is_set():
                hwnd = self._target
                if not hwnd:
                    self._stop.wait(0.5)
                    continue
                try:
                    if hwnd not in cache:
                        edit, win = self._find_omnibox(auto, hwnd)
                        if edit is None:
                            self._stop.wait(POLL_SECONDS * 2)
                            continue
                        if len(cache) > 8:
                            cache.clear()
                        cache[hwnd] = (edit, win)
                    edit, win = cache[hwnd]
                    value = edit.GetValuePattern().Value
                    title = win.Name or ""
                    host, shorts_id = parse_address(value)
                    if shorts_id and last_id.get(hwnd) != shorts_id:
                        last_id[hwnd] = shorts_id
                        swipes[hwnd] = swipes.get(hwnd, 0) + 1
                    elif not shorts_id:
                        last_id.pop(hwnd, None)
                    with self._lock:
                        self._result = {
                            "hwnd": hwnd, "ts": time.time(), "host": host, "shorts": bool(shorts_id),
                            "swipes": swipes.get(hwnd, 0), "incognito": bool(_PRIVATE.search(title)),
                        }
                except Exception:
                    cache.pop(hwnd, None)
                self._stop.wait(POLL_SECONDS)
