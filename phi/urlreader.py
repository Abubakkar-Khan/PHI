"""Extension-free browser detection via Windows UI Automation.

Reads the address bar of the focused Chromium window (Chrome, Edge, Brave, Vivaldi, Opera) in a worker
thread. Only the hostname, a Shorts flag and a private-window flag are kept in memory; the full URL is
never stored, logged or sent anywhere. The browser extension, when connected, takes priority.

Consistency measures
- poke(): the engine wakes the reader the instant the window title or focus changes (every navigation and
  every Short swipe changes the title), so detection does not wait for the next poll.
- If the focused window is a popup/menu of the browser, the main browser window (root owner) is read instead.
- A transient read failure keeps the last good answer for a few seconds instead of "forgetting" Shorts.
"""
from __future__ import annotations

import re
import threading
import time
from urllib.parse import urlparse

from . import winapi

POLL_SECONDS = 0.08
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
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.available = True
        self.status = "idle"      # ok | no-omnibox | error:... (for the activity log)
        self.version = 0          # bumped whenever the host / Shorts state changes (engine reacts instantly)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="phi-urlreader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def set_target(self, hwnd: int) -> None:
        """hwnd of the focused browser window, or 0 when no browser is focused."""
        if hwnd != self._target:
            self._target = hwnd
            self._wake.set()

    def poke(self) -> None:
        """Read the address bar right now (title or focus just changed)."""
        self._wake.set()

    def latest(self, hwnd: int, max_age: float = 5.0) -> dict | None:
        with self._lock:
            r = self._result
        if r and r["hwnd"] == hwnd and time.time() - r["ts"] <= max_age:
            return r
        return None

    # ---- worker -----------------------------------------------------------
    def _find_omnibox(self, auto, hwnd: int):
        """Try the focused window, then its root owner (when the focus is on a popup of the browser)."""
        candidates = [hwnd]
        root = winapi.root_owner(hwnd)
        if root and root != hwnd:
            candidates.append(root)
        for h in candidates:
            win = auto.ControlFromHandle(h)
            edit = win.EditControl(searchDepth=14, ClassName="OmniboxViewViews")
            if edit.Exists(0.5, 0.1):
                return edit, win
            edit = win.EditControl(searchDepth=14, Name="Address and search bar")
            if edit.Exists(0.3, 0.1):
                return edit, win
        return None, None

    def _run(self) -> None:
        try:
            import uiautomation as auto
        except Exception:
            self.available = False
            self.status = "unavailable"
            return
        with auto.UIAutomationInitializerInThread():
            cache: dict[int, tuple] = {}
            last_id: dict[int, str] = {}
            swipes: dict[int, int] = {}
            while not self._stop.is_set():
                hwnd = self._target
                if not hwnd:
                    self._wake.wait(0.5)
                    self._wake.clear()
                    continue
                t_read = time.perf_counter()
                try:
                    if hwnd not in cache:
                        edit, win = self._find_omnibox(auto, hwnd)
                        if edit is None:
                            self.status = "no-omnibox"
                            self._wake.wait(POLL_SECONDS * 2)
                            self._wake.clear()
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
                    prev = self._result
                    changed = prev["changed"] if prev else time.time()
                    if not prev or prev["hwnd"] != hwnd or prev["host"] != host or prev["shorts"] != bool(shorts_id):
                        self.version += 1
                        changed = time.time()
                    with self._lock:
                        self._result = {
                            "hwnd": hwnd, "ts": time.time(), "host": host, "shorts": bool(shorts_id),
                            "changed": changed, "swipes": swipes.get(hwnd, 0), "incognito": bool(_PRIVATE.search(title)),
                        }
                    ms = (time.perf_counter() - t_read) * 1000
                    self.status = "ok" if ms < 250 else f"slow:{ms:.0f}ms"
                except Exception as exc:  # stale element etc.: re-find next round, keep last good result
                    cache.pop(hwnd, None)
                    self.status = f"error:{type(exc).__name__}"
                self._wake.wait(POLL_SECONDS)
                self._wake.clear()
