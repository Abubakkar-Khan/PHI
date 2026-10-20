"""Local SQLite store: usage buckets, interruption events and settings. Nothing leaves the machine."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
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
    "reminders": True,
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
    ],
    "excluded_sites": [],
}


def data_dir() -> str:
    base = os.environ.get("PHI_DATA_DIR") or os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"), "PHI")
    os.makedirs(base, exist_ok=True)
    return base


def iso(d: date) -> str:
    return d.isoformat()


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(data_dir(), "phi.db")
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            # WAL + NORMAL never corrupts; a power cut can only lose the last moments of stats. It also keeps
            # the 10s flush from stalling the UI thread on fsync.
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # ---- writes --------------------------------------------------------
    def add_usage(self, rows: Iterable[tuple[tuple[str, int, str, str], float]]) -> None:
        with self.lock:
            self.conn.executemany(
                "INSERT INTO usage(day,hour,kind,name,seconds) VALUES(?,?,?,?,?) "
                "ON CONFLICT(day,hour,kind,name) DO UPDATE SET seconds = seconds + excluded.seconds",
                [(d, h, k, n, s) for (d, h, k, n), s in rows],
            )
            self.conn.commit()

    def log_event(self, ts: float, day: str, kind: str, detail: str = "") -> None:
        with self.lock:
            self.conn.execute("INSERT INTO events(ts,day,kind,detail) VALUES(?,?,?,?)", (ts, day, kind, detail))
            self.conn.commit()

    def delete_all(self) -> None:
        with self.lock:
            self.conn.execute("DELETE FROM usage")
            self.conn.execute("DELETE FROM events")
            self.conn.commit()
            self.conn.execute("VACUUM")

    def purge_older_than(self, days: int) -> None:
        if days <= 0:
            return
        cutoff = iso(date.today() - timedelta(days=days))
        with self.lock:
            self.conn.execute("DELETE FROM usage WHERE day < ?", (cutoff,))
            self.conn.execute("DELETE FROM events WHERE day < ?", (cutoff,))
            self.conn.commit()

    # ---- settings ------------------------------------------------------
    def load_settings(self) -> dict:
        with self.lock:
            rows = self.conn.execute("SELECT key,value FROM settings").fetchall()
        out = {}
        for k, v in rows:
            try:
                out[k] = json.loads(v)
            except ValueError:
                pass
        return out

    def save_setting(self, key: str, value) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(value)),
            )
            self.conn.commit()

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


class Settings:
    """Dict-like settings with change callbacks. Values persist immediately."""

    def __init__(self, store: Store):
        self.store = store
        self._d = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULTS.items()}
        self._d.update(store.load_settings())
        self._subs: list[Callable[[str], None]] = []

    def get(self, key: str):
        return self._d[key]

    def set(self, key: str, value) -> None:
        self._d[key] = value
        self.store.save_setting(key, value)
        for cb in list(self._subs):
            cb(key)

    def subscribe(self, cb: Callable[[str], None]) -> None:
        self._subs.append(cb)
