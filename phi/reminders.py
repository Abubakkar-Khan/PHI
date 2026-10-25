"""Timers and alarms: "Take a break" every 30 minutes, or a message at a set time of day.

Rules (deterministic, no AI)
- Interval reminders count wall-clock time, but restart whenever you have been away from the keyboard for
  5+ minutes: you already took your break.
- Daily reminders fire once at HH:MM (missed ones are skipped, not replayed).
- Only one reminder is on screen at a time, and none appears while a Shorts lockdown is open; they wait.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from . import winapi

AWAY_RESETS_INTERVAL = 300   # seconds of no input that count as "already took a break"


def new_reminder() -> dict:
    return {"id": uuid.uuid4().hex[:8], "message": "Take a break", "mode": "interval",
            "every_min": 30, "time": "13:00", "enabled": True, "sound": True}


def valid_time(text: str) -> bool:
    try:
        datetime.strptime(text, "%H:%M")
        return True
    except ValueError:
        return False


class ReminderScheduler(QObject):
    due = Signal(dict)

    def __init__(self, cfg, engine, parent=None):
        super().__init__(parent)
        self.cfg, self.engine = cfg, engine
        self._next: dict[str, float] = {}      # interval due times and snoozes
        self._last_day: dict[str, str] = {}    # daily reminders already fired today
        self._open = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def start(self) -> None:
        self._timer.start()

    @staticmethod
    def _key(item: dict, idx: int) -> str:
        return item.get("id") or f"i{idx}"

    def _tick(self) -> None:
        now = time.time()
        idle = winapi.idle_seconds()
        stamp = datetime.now()
        live = set()
        for idx, item in enumerate(self.cfg.get("reminder_items")):
            key = self._key(item, idx)
            if not item.get("enabled"):
                self._next.pop(key, None)
                continue
            live.add(key)
            snooze_due = self._next.get(key)
            if item.get("mode") == "daily":
                if snooze_due is not None:
                    if now >= snooze_due:
                        self._fire(item, key)
                elif stamp.strftime("%H:%M") == item.get("time") and self._last_day.get(key) != stamp.date().isoformat():
                    self._fire(item, key)
                continue
            every = max(1, int(item.get("every_min", 30))) * 60
            if snooze_due is None or idle >= AWAY_RESETS_INTERVAL and not self._open:
                self._next[key] = now + every
            elif now >= snooze_due:
                self._fire(item, key)
        for key in list(self._next):
            if key not in live:
                del self._next[key]

    def _fire(self, item: dict, key: str) -> None:
        if self._open or self.engine.nudge_open:
            return                                   # wait for the screen to be free; checked again next second
        self._open = True
        self._next[key] = float("inf")               # parked until the user answers
        if item.get("mode") == "daily":
            self._last_day[key] = datetime.now().date().isoformat()
            self._next.pop(key, None)
        self.engine.log(f"REMINDER {item.get('message')!r} ({item.get('mode')})")
        self.due.emit(dict(item, _key=key))

    def test(self, item: dict) -> None:
        """Show a reminder right now without touching its schedule."""
        if not self._open and not self.engine.nudge_open:
            self._open = True
            self.due.emit(dict(item, _key="", _test=True))

    def finish(self, item: dict, snooze_min: int = 0) -> None:
        """Called when the user answers: Done (snooze_min=0) or Snooze."""
        self._open = False
        key = item.get("_key")
        if not key or item.get("_test"):
            return
        now = time.time()
        if snooze_min:
            self._next[key] = now + snooze_min * 60
        elif item.get("mode") != "daily":
            self._next[key] = now + max(1, int(item.get("every_min", 30))) * 60
        else:
            self._next.pop(key, None)
