"""Monitoring engine: deterministic rules, no AI.

Every second it asks: what is in focus, is the user actually active, and is it Shorts?
Time is only counted while there was recent input (or audio playing in the browser tab).
"""
from __future__ import annotations

import os
import time
import traceback
from collections import defaultdict
from datetime import date, datetime

from PySide6.QtCore import QObject, QTimer, Signal

from . import winapi
from .db import Settings, Store, data_dir
from .server import Bridge
from .urlreader import UrlReader
from .utils import host_matches, normalize_host, pretty_app, pretty_site

BROWSERS = {"chrome.exe", "msedge.exe", "brave.exe", "vivaldi.exe", "opera.exe", "firefox.exe", "arc.exe"}
SESSION_GAP = 300      # seconds away from Shorts before a new "session" starts
HEARTBEAT_MAX_AGE = 9  # extension data older than this is ignored
FLUSH_EVERY = 10
DISMISS_RECHECK = 20   # seconds before PHI asks again after the popup's X is clicked


class Engine(QObject):
    snapshot = Signal(dict)     # emitted every second for the UI
    nudge = Signal(dict)        # a popup should be shown
    celebrated = Signal()       # user chose to stop: mascot celebrates

    def __init__(self, store: Store, cfg: Settings, bridge: Bridge, parent=None, reader: UrlReader | None = None):
        super().__init__(parent)
        self.store, self.cfg, self.bridge = store, cfg, bridge
        self.reader = reader
        self.own_pid = os.getpid()

        self.tracking_paused = False
        self.reminders_paused_until = 0.0
        self.bypass_until = 0.0
        self.nudge_open = False

        self._buf: dict[tuple[str, int, str, str], float] = defaultdict(float)
        self._today: dict[tuple[str, str], float] = defaultdict(float)
        self._day = ""
        self._last = time.time()
        self._last_flush = time.time()

        self._session = 0.0
        self._last_shorts = 0.0
        self._extra_session = 0.0
        self._extra_daily = 0.0
        self._extra_site: dict[str, float] = defaultdict(float)
        self._last_swipes: dict[int, int] = {}
        self._status = "monitoring"
        self._browser_hwnd = 0
        self._repeat = 0
        self._load_today()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

    # ---- lifecycle ----------------------------------------------------
    def start(self) -> None:
        self._last = time.time()
        self.timer.start()

    def stop(self) -> None:
        self.timer.stop()
        self.flush()

    def _load_today(self) -> None:
        self._day = date.today().isoformat()
        self._today = defaultdict(float, self.store.day_totals(self._day))
        self._session = 0.0
        self._extra_session = self._extra_daily = 0.0
        self._extra_site.clear()

    # ---- public controls -----------------------------------------------
    def set_tracking_paused(self, paused: bool) -> None:
        self.tracking_paused = paused

    def pause_reminders(self, minutes: float) -> None:
        self.reminders_paused_until = time.time() + minutes * 60 if minutes > 0 else 0.0

    @property
    def reminders_paused(self) -> bool:
        return time.time() < self.reminders_paused_until

    def today_seconds(self, kind: str, name: str) -> float:
        return self._today.get((kind, name), 0.0)

    def flush(self) -> None:
        if self._buf:
            self.store.add_usage(list(self._buf.items()))
            self._buf.clear()
        self._last_flush = time.time()

    # ---- recording -----------------------------------------------------
    def _add(self, hour: int, kind: str, name: str, secs: float) -> None:
        self._buf[(self._day, hour, kind, name)] += secs
        self._today[(kind, name)] += secs

    def _excluded(self, host: str) -> bool:
        return any(host_matches(host, d) for d in self.cfg.get("excluded_sites"))

    # ---- main tick -----------------------------------------------------
    def log(self, msg: str) -> None:
        try:
            path = os.path.join(data_dir(), "phi.log")
            if os.path.exists(path) and os.path.getsize(path) > 200_000:
                os.replace(path, path + ".old")
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(time.strftime("%H:%M:%S ") + msg + "\n")
        except OSError:
            pass

    def _tick(self) -> None:
        try:
            self._tick_inner()
        except Exception:
            self.log("TICK ERROR " + traceback.format_exc())

    def _tick_inner(self) -> None:
        now = time.time()
        dt = now - self._last
        self._last = now
        if dt < 0 or dt > 5:  # clock jump or sleep/resume: do not count it
            dt = 0.0
        if date.today().isoformat() != self._day:
            self.flush()
            self._load_today()
        hour = datetime.now().hour

        hb = self.bridge.fresh(HEARTBEAT_MAX_AGE)
        link = self.bridge.fresh(20) is not None
        fg = winapi.foreground()
        idle = winapi.idle_seconds()

        label, mood, shorts, site = "", "monitoring", False, None

        if self.tracking_paused:
            self._status, mood, label = "paused", "sleep", "Paused"
        elif fg is None:
            self._status, mood, label = "idle", "idle", "Away"
        else:
            exe = fg.exe.lower()
            if exe in BROWSERS:
                self._browser_hwnd = fg.hwnd
            if self.reader:
                self.reader.set_target(fg.hwnd if exe in BROWSERS and exe != "firefox.exe" else 0)
            src = None
            if exe in BROWSERS:
                if hb and hb["active"]:
                    src = hb
                elif self.reader:
                    src = self.reader.latest(fg.hwnd)
            if src and not src["incognito"] and src["host"]:
                hb = src
                site = normalize_host(src["host"])
                shorts = bool(src["shorts"]) and site == "youtube.com"
                link = True
            audible = bool(site and hb and hb.get("audible"))
            active = idle < self.cfg.get("idle_threshold_s") or audible

            if fg.pid == self.own_pid:
                self._status, label = "monitoring", "PHI"
            elif site and self._excluded(site):
                self._status, label = "excluded", "Excluded"
            elif not active:
                self._status, mood, label = "idle", "idle", "Idle"
            else:
                self._status = "shorts" if shorts else "active"
                label = pretty_site(site) if site else pretty_app(fg.exe)
                if dt > 0:
                    self._add(hour, "total", "*", dt)
                    if site:
                        self._add(hour, "site", site, dt)
                    elif self.cfg.get("track_apps"):
                        self._add(hour, "app", fg.exe.lower(), dt)
                    if shorts:
                        self._add(hour, "shorts", "youtube", dt)
                        self._count_swipes(hb, hour)
                if shorts:
                    label, mood = "YouTube Shorts", "alert"
                    self._on_shorts(now, dt)
                elif site:
                    self._check_site(site, label)

        sig = (self._status, label)
        if sig != getattr(self, "_last_sig", None):
            self._last_sig = sig
            self.log(f"state {self._status} / {label} / link={link}")

        if now - self._last_flush >= FLUSH_EVERY:
            self.flush()

        self.snapshot.emit({
            "status": self._status,
            "label": label,
            "mood": mood,
            "link": link,
            "session": self._session,
            "shorts_today": self.today_seconds("shorts", "youtube"),
            "total_today": self.today_seconds("total", "*"),
            "reminders_paused": self.reminders_paused,
            "tracking_paused": self.tracking_paused,
        })

    # ---- shorts rules ----------------------------------------------------
    def _count_swipes(self, hb: dict, hour: int) -> None:
        tab, n = hb.get("tabId", 0) or hb.get("hwnd", 0), hb["swipes"]
        prev = self._last_swipes.get(tab)
        self._last_swipes[tab] = n
        if prev is None:
            return
        delta = n - prev if n >= prev else n
        if 0 < delta < 50:
            self._add(hour, "swipes", "shorts", float(delta))

    def _can_nudge(self, now: float) -> bool:
        return (self.cfg.get("reminders") and not self.nudge_open
                and now >= self.reminders_paused_until and now >= self.bypass_until)

    def _on_shorts(self, now: float, dt: float) -> None:
        if self._last_shorts and now - self._last_shorts > SESSION_GAP:
            self._session = 0.0
            self._extra_session = 0.0
            self._repeat = 0
        self._last_shorts = now
        self._session += dt

        session_limit = self.cfg.get("shorts_limit_min") * 60
        daily_limit = self.cfg.get("shorts_daily_min") * 60
        today = self.today_seconds("shorts", "youtube")
        reason = None
        if self._session >= session_limit + self._extra_session:  # 0 = nudge as soon as Shorts opens
            reason = "shorts"
        elif daily_limit and today >= daily_limit + self._extra_daily:
            reason = "daily"
        if reason and self._can_nudge(now):
            seconds = self._session if reason == "shorts" else today
            self._emit_nudge({"kind": reason, "seconds": seconds, "label": "YouTube Shorts", "domain": "youtube.com"})

    def _check_site(self, site: str, label: str) -> None:
        now = time.time()
        for entry in self.cfg.get("watched_sites"):
            domain = entry["domain"]
            if not entry.get("enabled") or not entry.get("limit") or not host_matches(site, domain):
                continue
            used = self.today_seconds("site", site)
            if used >= entry["limit"] * 60 + self._extra_site[domain] and self._can_nudge(now):
                self._emit_nudge({"kind": "site", "seconds": used, "label": pretty_site(site), "domain": domain})
            return

    def _emit_nudge(self, payload: dict) -> None:
        self._repeat += 1
        payload["repeat"] = self._repeat
        payload["today_s"] = self.today_seconds("shorts", "youtube") if payload["kind"] != "site" else payload["seconds"]
        payload["count"] = int(self.today_seconds("swipes", "shorts")) if payload["kind"] != "site" else 0
        self.nudge_open = True
        self.log(f"NUDGE {payload['kind']} session={self._session:.0f}s")
        self.store.log_event(time.time(), self._day, "nudge", payload["kind"])
        self.nudge.emit(payload)

    # ---- popup results -----------------------------------------------------
    def resolve(self, payload: dict, action: str) -> None:
        """action: stop | more | pause | bypass | dismiss"""
        now = time.time()
        self.nudge_open = False
        self.store.log_event(now, self._day, action, payload["kind"])
        extend = self.cfg.get("extend_min") * 60
        kind = payload["kind"]
        self.log(f"RESOLVE {action} ({kind})")

        if action == "stop":
            match = "shorts" if kind in ("shorts", "daily") else payload["domain"]
            if self.bridge.fresh(12):
                self.bridge.queue_command({"type": "close", "match": match})   # extension closes the tab
            else:
                QTimer.singleShot(150, lambda: self._close_by_keys(match))      # no extension: Ctrl+W
            # fresh start: reopening Shorts is a new session and is checked again right away
            self._session = 0.0
            self._last_shorts = 0.0
            self._repeat = 0
            self._extra_session = self._extra_daily = 0.0
            self.bypass_until = max(self.bypass_until, now + 5)
            self.celebrated.emit()
        elif action == "dismiss":
            # The X button is not a decision: keep watching and ask again shortly if Shorts is still on.
            self.bypass_until = max(self.bypass_until, now + DISMISS_RECHECK)
        elif action == "more":
            if kind in ("shorts", "daily"):
                today = self.today_seconds("shorts", "youtube")
                self._extra_session = max(0.0, self._session + extend - self.cfg.get("shorts_limit_min") * 60)
                self._extra_daily = max(0.0, today + extend - self.cfg.get("shorts_daily_min") * 60)
            else:
                d = payload["domain"]
                used = self.today_seconds("site", normalize_host(d))
                limit = next((e["limit"] for e in self.cfg.get("watched_sites") if e["domain"] == d), 0)
                self._extra_site[d] = max(0.0, used + extend - limit * 60)
        elif action == "pause":
            self.reminders_paused_until = now + self.cfg.get("pause_min") * 60
        elif action == "bypass":
            self.bypass_until = now + self.cfg.get("bypass_min") * 60

    # ---- closing without the extension -------------------------------------
    def _close_by_keys(self, match: str) -> None:
        """Close the active tab with Ctrl+W, but only if it is still the page the nudge was about."""
        hwnd = self._browser_hwnd
        res = self.reader.latest(hwnd, max_age=6.0) if (hwnd and self.reader) else None
        self.log(f"close-by-keys hwnd={hwnd} reader={'none' if not res else (res['host'], res['shorts'])}")
        if not res:
            return
        ok = res["shorts"] if match == "shorts" else host_matches(normalize_host(res["host"]), match)
        if not ok:
            return
        winapi.focus(hwnd)
        QTimer.singleShot(200, winapi.send_ctrl_w)