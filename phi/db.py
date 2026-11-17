"""Local SQLite store: usage buckets, interruption events and settings. Nothing leaves the machine."""
from __future__ import annotations

import copy
import json
import math
import os
import re
import sqlite3
import threading
import time
from datetime import date, timedelta
from typing import Callable, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    day     TEXT NOT NULL,
    hour    INTEGER NOT NULL,
    kind    TEXT NOT NULL,      -- total | app | site | shorts | swipes
    name    TEXT NOT NULL,
    seconds REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (day, hour, kind, name)
);
CREATE TABLE IF NOT EXISTS events (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     REAL NOT NULL,
    day    TEXT NOT NULL,
    kind   TEXT NOT NULL,       -- nudge | stop | more | pause | bypass | dismiss
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_day ON events(day, kind);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULTS = {
    "name": "",
    "character": "classic",        # classic | buns
    "theme_mode": "light",         # light | dark | custom
    "theme_bg": "#F0EFEB",         # custom theme colours
    "theme_text": "#171717",
    "theme_accent": "#E53935",
    "reminder_snooze_min": 5,
    "reminder_items": [            # timers and alarms; shown full-screen
        {"id": "break30", "message": "Take a break", "mode": "interval", "every_min": 30,
         "time": "13:00", "enabled": False, "sound": True},
    ],
    "reminders": True,
    "pause_video": True,           # pause the video behind the lock; resumes if you buy more time
    "lockdown": True,              # full-screen takeover instead of a small card
    "lockdown_seconds": 10,        # auto-close countdown (grows if PHI has to ask again)
    "shorts_limit_min": 20,        # continuous Shorts session before a nudge
    "shorts_daily_min": 60,        # total Shorts budget per day
    "extend_min": 5,               # "give me N more minutes"
    "pause_min": 60,               # "pause reminders"
    "bypass_min": 30,              # "I'm using it for something important"
    "idle_threshold_s": 120,       # no input for this long = not active
    "track_apps": True,
    "autostart": True,
    "retention_days": 90,
    "watched_sites": [
        {"domain": "instagram.com", "limit": 15, "enabled": True},
        {"domain": "reddit.com", "limit": 15, "enabled": True},
        {"domain": "tiktok.com", "limit": 15, "enabled": False},
        {"domain": "x.com", "limit": 15, "enabled": False},
        {"domain": "youtube.com", "limit": 60, "enabled": False},   # YouTube without Shorts
    ],
    "excluded_sites": [],
    "hidden_items": [],            # [{"kind": "app|site|shorts", "key": "...", "label": "..."}] display-only
    "watched_apps": [],            # [{"exe": "discord.exe", "limit": 60, "enabled": true}]
}


def data_dir() -> str:
    base = os.environ.get("PHI_DATA_DIR") or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), "PHI")
    os.makedirs(base, exist_ok=True)
    return base


def iso(d: date) -> str:
    return d.isoformat()


class Store:
    """The local SQLite file. It is built to keep PHI running: a damaged file is moved aside and replaced, and a
    failed write (locked file, full disk) is reported by returning False instead of raising into the UI."""

    BUSY_SECONDS = 1.0          # how long a locked database may hold the calling thread

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(data_dir(), "phi.db")
        self.lock = threading.RLock()
        self.recovered: str | None = None     # where a damaged database was moved to, if that happened
        self.volatile = False                 # True when no file could be used: data then lives in memory only
        self.errors = 0
        self.last_error = ""
        self.conn = self._open()

    def _connect(self, path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(path, check_same_thread=False, timeout=self.BUSY_SECONDS)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            # WAL + NORMAL never corrupts; a power cut can only lose the last moments of stats. It also keeps
            # the 10s flush from stalling the UI thread on fsync.
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(SCHEMA)
            conn.commit()
        except Exception:
            conn.close()
            raise
        return conn

    def _open(self) -> sqlite3.Connection:
        try:
            return self._connect(self.path)
        except sqlite3.OperationalError as exc:        # locked by another program, folder not writable, disk full
            self.last_error = f"open: {exc}"
        except sqlite3.DatabaseError as exc:           # "file is not a database", "disk image is malformed"
            self.last_error = f"open: {exc}"
            try:                                       # keep the damaged file aside so nothing is silently destroyed
                aside = f"{self.path}.damaged-{time.strftime('%Y%m%d-%H%M%S')}"
                os.replace(self.path, aside)
                for ext in ("-wal", "-shm"):
                    if os.path.exists(self.path + ext):
                        os.replace(self.path + ext, aside + ext)
                conn = self._connect(self.path)
                self.recovered = aside
                return conn
            except Exception as again:
                self.last_error = f"recover: {again}"
        self.volatile = True                           # still running beats refusing to start
        return self._connect(":memory:")

    def _safe(self, what: str, fn) -> bool:
        """Run a write under the lock. A failure is remembered in last_error and returns False; it never raises."""
        try:
            with self.lock:
                fn()
            return True
        except sqlite3.Error as exc:
            self.errors += 1
            self.last_error = f"{what}: {exc}"
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass
            return False

    # ---- writes --------------------------------------------------------
    def add_usage(self, rows: Iterable[tuple[tuple[str, int, str, str], float]]) -> bool:
        """Add seconds. Returns False if nothing was written (the caller keeps its buffer and tries again)."""
        clean = []
        for (d, h, k, n), s in rows:
            if isinstance(s, (int, float)) and not isinstance(s, bool) and math.isfinite(s) and s > 0:
                clean.append((str(d), int(h), str(k), str(n), float(s)))   # NaN/inf/negative would poison every later total
        if not clean:
            return True

        def run():
            self.conn.executemany(
                "INSERT INTO usage(day,hour,kind,name,seconds) VALUES(?,?,?,?,?) "
                "ON CONFLICT(day,hour,kind,name) DO UPDATE SET seconds = seconds + excluded.seconds", clean)
            self.conn.commit()
        return self._safe("add_usage", run)

    def log_event(self, ts: float, day: str, kind: str, detail: str = "") -> bool:
        row = (float(ts), str(day), str(kind or "unknown"), "" if detail is None else str(detail))

        def run():
            self.conn.execute("INSERT INTO events(ts,day,kind,detail) VALUES(?,?,?,?)", row)
            self.conn.commit()
        return self._safe("log_event", run)

    def delete_all(self) -> bool:
        def run():
            self.conn.execute("DELETE FROM usage")
            self.conn.execute("DELETE FROM events")
            self.conn.commit()
        ok = self._safe("delete_all", run)
        if ok:
            self._safe("vacuum", lambda: self.conn.execute("VACUUM"))
        return ok

    def purge_older_than(self, days: int) -> None:
        """Delete days older than `days`, one day at a time so the lock is never held for long (safe off the UI thread)."""
        if not isinstance(days, (int, float)) or days <= 0:
            return
        cutoff = iso(date.today() - timedelta(days=days))
        try:
            with self.lock:
                old = sorted({r[0] for r in self.conn.execute(
                    "SELECT day FROM usage WHERE day < ? UNION SELECT day FROM events WHERE day < ?", (cutoff, cutoff))})
        except sqlite3.Error as exc:
            self.last_error = f"purge: {exc}"
            return
        for day in old:
            def run(day=day):
                self.conn.execute("DELETE FROM usage WHERE day = ?", (day,))
                self.conn.execute("DELETE FROM events WHERE day = ?", (day,))
                self.conn.commit()
            if not self._safe("purge", run):
                return

    # ---- settings ------------------------------------------------------
    def load_settings(self) -> dict:
        try:
            with self.lock:
                rows = self.conn.execute("SELECT key,value FROM settings").fetchall()
        except sqlite3.Error as exc:
            self.last_error = f"load_settings: {exc}"
            return {}
        out = {}
        for k, v in rows:
            try:
                out[k] = json.loads(v)
            except ValueError:
                pass
        return out

    def save_setting(self, key: str, value) -> bool:
        try:
            text = json.dumps(value)
        except (TypeError, ValueError):
            return False

        def run():
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, text))
            self.conn.commit()
        return self._safe("save_setting", run)

    # ---- reads ---------------------------------------------------------
    def day_totals(self, day: str) -> dict[tuple[str, str], float]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT kind,name,SUM(seconds) FROM usage WHERE day=? GROUP BY kind,name", (day,)).fetchall()
        return {(k, n): s for k, n, s in rows}

    def by_name(self, d0: str, d1: str, kinds: tuple[str, ...]) -> list[tuple[str, str, float]]:
        marks = ",".join("?" * len(kinds))
        with self.lock:
            return self.conn.execute(
                f"SELECT kind,name,SUM(seconds) s FROM usage WHERE day BETWEEN ? AND ? AND kind IN ({marks}) "
                "GROUP BY kind,name ORDER BY s DESC", (d0, d1, *kinds)).fetchall()

    def hourly(self, day: str, kind: str, name: str) -> list[float]:
        out = [0.0] * 24
        with self.lock:
            rows = self.conn.execute(
                "SELECT hour,SUM(seconds) FROM usage WHERE day=? AND kind=? AND name=? GROUP BY hour",
                (day, kind, name)).fetchall()
        for h, s in rows:
            out[int(h)] = s
        return out

    def daily_series(self, end: date, days: int, kind: str, name: str) -> list[float]:
        start = end - timedelta(days=days - 1)
        with self.lock:
            rows = self.conn.execute(
                "SELECT day,SUM(seconds) FROM usage WHERE day BETWEEN ? AND ? AND kind=? AND name=? GROUP BY day",
                (iso(start), iso(end), kind, name)).fetchall()
        lookup = dict(rows)
        return [lookup.get(iso(start + timedelta(days=i)), 0.0) for i in range(days)]

    def total_until(self, day: str, kind: str, name: str, hour: int) -> float:
        with self.lock:
            row = self.conn.execute(
                "SELECT SUM(seconds) FROM usage WHERE day=? AND kind=? AND name=? AND hour<=?",
                (day, kind, name, hour)).fetchone()
        return row[0] or 0.0

    def daily_kind_range(self, d0: str, d1: str, kinds: tuple[str, ...], name: str | None = None) -> dict[str, float]:
        """Seconds per day between d0 and d1 for the given kinds (summed)."""
        marks = ",".join("?" * len(kinds))
        sql = f"SELECT day,SUM(seconds) FROM usage WHERE day BETWEEN ? AND ? AND kind IN ({marks})"
        args: list = [d0, d1, *kinds]
        if name is not None:
            sql += " AND name=?"
            args.append(name)
        with self.lock:
            rows = self.conn.execute(sql + " GROUP BY day", args).fetchall()
        return {d: s or 0.0 for d, s in rows}

    def hourly_kinds(self, day: str, kinds: tuple[str, ...]) -> list[float]:
        """Seconds per hour of one day for the given kinds (summed)."""
        marks = ",".join("?" * len(kinds))
        with self.lock:
            rows = self.conn.execute(
                f"SELECT hour,SUM(seconds) FROM usage WHERE day=? AND kind IN ({marks}) GROUP BY hour", (day, *kinds)).fetchall()
        out = [0.0] * 24
        for h, s in rows:
            out[int(h)] = s or 0.0
        return out

    def event_count(self, day: str, kind: str) -> int:
        with self.lock:
            row = self.conn.execute("SELECT COUNT(*) FROM events WHERE day=? AND kind=?", (day, kind)).fetchone()
        return int(row[0])

    def event_series(self, end: date, days: int, kind: str) -> list[float]:
        start = end - timedelta(days=days - 1)
        with self.lock:
            rows = self.conn.execute(
                "SELECT day,COUNT(*) FROM events WHERE day BETWEEN ? AND ? AND kind=? GROUP BY day",
                (iso(start), iso(end), kind)).fetchall()
        lookup = dict(rows)
        return [float(lookup.get(iso(start + timedelta(days=i)), 0)) for i in range(days)]

    def close(self) -> None:
        with self.lock:
            self.conn.close()


# ---- validation ---------------------------------------------------------------------------------------------
# Every setting has a type and a range. A damaged, hand-edited or newer-version value is repaired to something the
# rest of the program can use instead of crashing the 500 ms loop. The ranges match the steppers in Settings.
NUMERIC = {                       # key: (low, high)
    "reminder_snooze_min": (1, 60), "lockdown_seconds": (5, 40), "shorts_limit_min": (0, 240), "shorts_daily_min": (0, 600),
    "extend_min": (1, 60), "pause_min": (1, 1440), "bypass_min": (1, 1440), "idle_threshold_s": (10, 3600),
    "retention_days": (7, 730),
}
BOOLEAN = ("reminders", "pause_video", "lockdown", "track_apps", "autostart")
CHOICES = {"theme_mode": ("light", "dark", "custom"), "character": ("classic", "buns")}
COLOURS = ("theme_bg", "theme_text", "theme_accent")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _num(value, lo, hi, default):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        try:
            value = float(value)
            if not math.isfinite(value):
                return default
        except (TypeError, ValueError):
            return default
    return int(min(hi, max(lo, round(value))))


def _limit(value, default=15):
    return _num(value, 0, 1440, default)


def _clean_sites(value, default):
    """Keep the same list object where possible, because the Settings screen edits its dicts in place."""
    if not isinstance(value, list):
        return copy.deepcopy(default)
    keep = [e for e in value if isinstance(e, dict) and isinstance(e.get("domain"), str) and e["domain"].strip()]
    for e in keep:
        e["domain"] = e["domain"].strip().lower()
        e["limit"] = _limit(e.get("limit"))
        e["enabled"] = bool(e.get("enabled", True))
    value[:] = keep
    return value


def _clean_apps(value):
    if not isinstance(value, list):
        return []
    keep = [e for e in value if isinstance(e, dict) and isinstance(e.get("exe"), str) and e["exe"].strip()]
    for e in keep:
        e["exe"] = e["exe"].strip().lower()
        e["limit"] = _limit(e.get("limit"), 60)
        e["enabled"] = bool(e.get("enabled", True))
        e["label"] = str(e.get("label") or e["exe"])
    value[:] = keep
    return value


def _clean_reminders(value, default):
    if not isinstance(value, list):
        return copy.deepcopy(default)
    keep = [e for e in value if isinstance(e, dict)]
    for i, e in enumerate(keep):
        e["id"] = str(e.get("id") or f"r{i}")
        e["message"] = str(e.get("message") or "Take a break")[:300]
        e["mode"] = "daily" if e.get("mode") == "daily" else "interval"
        e["every_min"] = _num(e.get("every_min"), 1, 720, 30)
        t = e.get("time")
        try:
            time.strptime(t, "%H:%M")
        except (TypeError, ValueError):
            t = "13:00"
        e["time"] = t
        e["enabled"] = bool(e.get("enabled", False))
        e["sound"] = bool(e.get("sound", True))
    value[:] = keep
    return value


def sanitize(key: str, value):
    """Return a safe value for `key`, repairing it in place where that is possible. Unknown keys pass through."""
    default = DEFAULTS.get(key)
    if key in NUMERIC:
        return _num(value, *NUMERIC[key], default)
    if key in BOOLEAN:
        return value if isinstance(value, bool) else (bool(value) if isinstance(value, (int, float)) else default)
    if key in CHOICES:
        return value if value in CHOICES[key] else default
    if key in COLOURS:
        return value if isinstance(value, str) and HEX.match(value) else default
    if key == "name":
        return value.strip()[:60] if isinstance(value, str) else ""
    if key == "watched_sites":
        return _clean_sites(value, default)
    if key == "watched_apps":
        return _clean_apps(value)
    if key == "reminder_items":
        return _clean_reminders(value, default)
    if key == "excluded_sites":
        if not isinstance(value, list):
            return []
        value[:] = [d.strip().lower() for d in value if isinstance(d, str) and d.strip()]
        return value
    if key == "hidden_items":
        if not isinstance(value, list):
            return []
        value[:] = [h for h in value if isinstance(h, dict) and "kind" in h and "key" in h]
        return value
    return value


class Settings:
    """Dict-like settings with change callbacks. Values persist immediately and are always valid."""

    def __init__(self, store: Store):
        self.store = store
        self._d = {k: copy.deepcopy(v) for k, v in DEFAULTS.items()}
        for k, v in store.load_settings().items():
            self._d[k] = sanitize(k, v)
        self._subs: list[Callable[[str], None]] = []

    def get(self, key: str, default=None):
        if key in self._d:
            return self._d[key]
        return DEFAULTS.get(key, default)

    def set(self, key: str, value) -> None:
        value = sanitize(key, value)
        self._d[key] = value
        self.store.save_setting(key, value)
        for cb in list(self._subs):
            try:
                cb(key)
            except Exception as exc:               # one broken listener must not stop the others or the caller
                self.store.last_error = f"settings listener for {key}: {exc!r}"

    def subscribe(self, cb: Callable[[str], None]) -> None:
        self._subs.append(cb)
