"""Timers and alarms: "Take a break" every 30 minutes, or a message at a set time of day.

Rules (deterministic, no AI)
- Interval reminders are plain clock timers: "every 5 minutes" means every 5 minutes, whether or not you are at
  the keyboard. Changing the interval restarts its countdown.
- If the PC sleeps (or the clock is changed) while a reminder is pending, it is not replayed on wake-up: its
  countdown simply starts again.
- Daily reminders fire once at HH:MM (missed ones are skipped, not replayed).
- Only one reminder is on screen at a time, and none appears while a Shorts lockdown is open; they wait.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

SNOOZED = -1                 # marker in _armed: this key is waiting out a Snooze, not an interval
RESUME_GAP = 30              # seconds without a tick that mean the PC slept or was suspended
MAX_SNOOZE = 3600            # the longest legitimate Snooze (seconds), used to spot a clock set backwards


def _every_seconds(item: dict) -> int:
    """The interval in seconds, tolerant of a hand-edited or damaged value (1 to 720 minutes, default 30)."""
    try:
        minutes = int(float(item.get("every_min", 30)))
    except (TypeError, ValueError):
        minutes = 30
    return min(720, max(1, minutes)) * 60


def new_reminder() -> dict:
    return {"id": uuid.uuid4().hex[:8], "message": "Take a break", "mode": "interval",
            "every_min": 30, "time": "13:00", "enabled": True, "sound": True}


def valid_time(text: str) -> bool:
    try:
        datetime.strptime(text, "%H:%M")
        return True
    except (TypeError, ValueError):
        return False


class ReminderScheduler(QObject):
    due = Signal(dict)

    def __init__(self, cfg, engine, parent=None):
        super().__init__(parent)
        self.cfg, self.engine = cfg, engine
        self._next: dict[str, float] = {}      # interval due times and snoozes
        self._armed: dict[str, int] = {}       # the interval (s) each due time was computed with, or SNOOZED
        self._last_day: dict[str, tuple] = {}  # daily reminders already fired: (date, HH:MM)
        self._last_tick = 0.0
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
        gap = now - self._last_tick if self._last_tick else 0.0
        self._last_tick = now
        resumed = gap > RESUME_GAP or gap < -5          # asleep or suspended for a while, or the clock was changed
        stamp = datetime.now()
        live = set()
        items = self.cfg.get("reminder_items")
        for idx, item in enumerate(items if isinstance(items, list) else []):
            if not isinstance(item, dict):
                continue
            key = self._key(item, idx)
            if not item.get("enabled"):
                self._next.pop(key, None)
                self._armed.pop(key, None)
                continue
            live.add(key)
            due = self._next.get(key)
            if item.get("mode") == "daily":
                if due is not None:
                    if now >= due:                                   # a Snooze came back
                        self._fire(item, key)
                elif stamp.strftime("%H:%M") == item.get("time") and self._last_day.get(key) != (stamp.date().isoformat(), item.get("time")):
                    self._fire(item, key)       # once per day per time: editing the time re-arms it for the new one
                continue
            every = _every_seconds(item)
            if resumed and due is not None and due != float("inf") and (due <= now or due - now > max(every, MAX_SNOOZE)):
                due = None                   # it came due while the PC slept, or the clock moved: count again, don't replay
            if due is None or (self._armed.get(key) not in (SNOOZED, every) and due != float("inf")):
                self._next[key] = now + every                         # first sight, or the interval was edited
                self._armed[key] = every
            elif now >= due:
                self._fire(item, key)
        for key in list(self._next):
            if key not in live:
                del self._next[key]
                self._armed.pop(key, None)

    def _fire(self, item: dict, key: str) -> None:
        if self._open or self.engine.nudge_open:
            return                                   # wait for the screen to be free; checked again next second
        self._open = True
        self._next[key] = float("inf")               # parked until the user answers
        self._armed[key] = SNOOZED
        if item.get("mode") == "daily":
            self._last_day[key] = (datetime.now().date().isoformat(), item.get("time"))   # fired today at this time
            self._next.pop(key, None)
            self._armed.pop(key, None)
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
            self._armed[key] = SNOOZED
        elif item.get("mode") != "daily":
            every = _every_seconds(item)
            self._next[key] = now + every
            self._armed[key] = every
        else:
            self._next.pop(key, None)
            self._armed.pop(key, None)
