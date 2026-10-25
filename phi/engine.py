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
SESSION_GAP = 4        # seconds away from Shorts that end a session (reopening Shorts = fresh check)
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
        self._extra_app: dict[str, float] = defaultdict(float)
        self._last_swipes: dict[int, int] = {}
        self._status = "monitoring"
        self._browser_hwnd = 0
        self._repeat = 0
        self._pin_hwnd = 0
        self._pin_until = 0.0
        self._load_today()
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._tick)
        self._title_key = None
        self._reader_version = 0
        self.watch = QTimer(self)
        self.watch.setInterval(40)
        self.watch.timeout.connect(self._watch_title)

    # ---- lifecycle ----------------------------------------------------
    def start(self) -> None:
        self._last = time.time()
        self.timer.start()
        self.watch.start()

    def stop(self) -> None:
        self.timer.stop()
        self.watch.stop()
        self.flush()

    def _load_today(self) -> None:
        self._day = date.today().isoformat()
        self._today = defaultdict(float, self.store.day_totals(self._day))
        self._session = 0.0
        self._extra_session = self._extra_daily = 0.0
        self._extra_site.clear()
        self._extra_app.clear()

    # ---- public controls -----------------------------------------------
    def set_tracking_paused(self, paused: bool) -> None:
        self.tracking_paused = paused

    def pause_reminders(self, minutes: float) -> None:
        self.reminders_paused_until = time.time() + minutes * 60 if minutes > 0 else 0.0

    @property
    def reminders_paused(self) -> bool:
        return time.time() < self.reminders_paused_until

    def today_sum(self, kind: str) -> float:
        """Total seconds today for one kind (app, site, ...), live including unsaved time."""
        return sum(v for (k, _n), v in self._today.items() if k == kind)

    def site_used(self, domain: str) -> float:
        """Seconds on a site today. For youtube.com this is YouTube *without* Shorts, which has its own limits."""
        used = self.today_seconds("site", normalize_host(domain))
        if normalize_host(domain) == "youtube.com":
            used = max(0.0, used - self.today_seconds("shorts", "youtube"))
        return used

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
    def _watch_title(self) -> None:
        """Every navigation and Short swipe changes the browser's window title: use that as a trigger
        to read the address bar immediately and re-evaluate, instead of waiting for the next poll."""
        if not self.reader or self.tracking_paused:
            return
        if self.reader and self.reader.version != self._reader_version:
            self._reader_version = self.reader.version
            self._tick()                  # the address bar just changed: evaluate right now
        fg = winapi.foreground()
        if not fg or fg.exe.lower() not in BROWSERS or fg.exe.lower() == "firefox.exe":
            return
        key = (fg.hwnd, winapi.window_title(fg.hwnd))
        if key != self._title_key:
            self._title_key = key
            self._browser_hwnd = fg.hwnd
            self.reader.set_target(fg.hwnd)
            self.reader.poke()
            QTimer.singleShot(250, self._tick)

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
                pinned = self._pin_hwnd if time.time() < self._pin_until else 0
                self.reader.set_target(fg.hwnd if exe in BROWSERS and exe != "firefox.exe" else pinned)
            src = None
            if exe in BROWSERS:
                if self.reader:                       # address-bar reading is live; prefer it
                    src = self.reader.latest(fg.hwnd)
                if src is None and hb and hb["active"]:
                    src = hb                          # extension heartbeat is only a fallback
            if src and not src["incognito"] and src["host"]:
                self._src_changed = src.get("changed")
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
                else:
                    self._check_app(exe, fg.hwnd)

        rs = self.reader.status if (self.reader and fg and fg.exe.lower() in BROWSERS) else None
        if rs and rs != getattr(self, "_last_rs", None):
            self._last_rs = rs
            self.log(f"reader: {rs}")
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
            used = self.site_used(site)
            if used >= entry["limit"] * 60 + self._extra_site[domain] and self._can_nudge(now):
                self._emit_nudge({"kind": "site", "seconds": used, "label": pretty_site(site), "domain": domain})
            return

    def _check_app(self, exe: str, hwnd: int) -> None:
        """Daily limits for desktop apps (Settings -> Watched apps)."""
        now = time.time()
        for entry in self.cfg.get("watched_apps"):
            key = entry["exe"].lower()
            if key != exe or not entry.get("enabled") or not entry.get("limit"):
                continue
            used = self.today_seconds("app", exe)
            if used >= entry["limit"] * 60 + self._extra_app[key] and self._can_nudge(now):
                self._emit_nudge({"kind": "app", "seconds": used, "label": pretty_app(exe), "domain": key, "hwnd": hwnd})
            return

    def _emit_nudge(self, payload: dict) -> None:
        self._repeat += 1
        payload["repeat"] = self._repeat
        shorts_kind = payload["kind"] in ("shorts", "daily")
        payload["today_s"] = self.today_seconds("shorts", "youtube") if shorts_kind else payload["seconds"]
        payload["count"] = int(self.today_seconds("swipes", "shorts")) if shorts_kind else 0
        self.nudge_open = True
        lag = f" detect-lag={time.time() - self._src_changed:.2f}s" if getattr(self, "_src_changed", None) else ""
        self.log(f"NUDGE {payload['kind']} session={self._session:.0f}s{lag}")
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
            if kind == "app":
                # An app is never force-closed (unsaved work): it is minimised.
                QTimer.singleShot(200, lambda: winapi.minimize(payload.get("hwnd", 0)))
            else:
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
            self._last_shorts = now   # time spent on the lock screen must not end the session
            if kind in ("shorts", "daily"):
                today = self.today_seconds("shorts", "youtube")
                self._extra_session = max(0.0, self._session + extend - self.cfg.get("shorts_limit_min") * 60)
                self._extra_daily = max(0.0, today + extend - self.cfg.get("shorts_daily_min") * 60)
            elif kind == "app":
                d = payload["domain"]
                used = self.today_seconds("app", d)
                limit = next((e["limit"] for e in self.cfg.get("watched_apps") if e["exe"].lower() == d), 0)
                self._extra_app[d] = max(0.0, used + extend - limit * 60)
            else:
                d = payload["domain"]
                used = self.site_used(d)
                limit = next((e["limit"] for e in self.cfg.get("watched_sites") if e["domain"] == d), 0)
                self._extra_site[d] = max(0.0, used + extend - limit * 60)
        elif action == "pause":
            self.reminders_paused_until = now + self.cfg.get("pause_min") * 60
        elif action == "bypass":
            self.bypass_until = now + self.cfg.get("bypass_min") * 60

    # ---- closing without the extension -------------------------------------
    def _close_by_keys(self, match: str) -> None:
        """Focus the browser, re-read its address bar, and Ctrl+W only if it is still on the nudged page."""
        hwnd = self._browser_hwnd
        if not (hwnd and self.reader):
            return
        self._pin_hwnd, self._pin_until = hwnd, time.time() + 4
        winapi.focus(hwnd)
        QTimer.singleShot(900, lambda: self._verify_close(hwnd, match))

    def _verify_close(self, hwnd: int, match: str) -> None:
        res = self.reader.latest(hwnd, max_age=3.0)
        self.log(f"close-by-keys hwnd={hwnd} reader={'none' if not res else (res['host'], res['shorts'])}")
        if not res:
            return
        ok = res["shorts"] if match == "shorts" else host_matches(normalize_host(res["host"]), match)
        if ok:
            winapi.send_ctrl_w()