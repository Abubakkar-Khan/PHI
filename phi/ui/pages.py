"""The three primary screens: Today, Apps & Sites, Settings."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPen
from PySide6.QtWidgets import (QColorDialog, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QVBoxLayout, QWidget)

from .. import autostart
from ..db import Settings, Store
from ..engine import BROWSERS, Engine
from ..utils import clean_domain, fmt_dur, pretty_app, pretty_site
from . import theme as T
from .mascot import Mascot
from .widgets import (Hairline, LinkButton, Panel, PillButton, PixelChart, Segmented, StatCard, StatusChip,
                      Stepper, Timeline, Toggle, UsageRow)


@dataclass
class Ctx:
    store: Store
    cfg: Settings
    engine: Engine
    scheduler: object = None      # ReminderScheduler, set by the app after startup


def mk_label(text: str, font, color: str | None = None, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    lb = QLabel(text)
    lb.setFont(font)
    lb.setStyleSheet(f"color:{color or T.INK}; background:transparent;")
    lb.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    return lb


def caps(text: str, color: str | None = None) -> QLabel:
    return mk_label(text.upper(), T.mono(10, spacing=1.4), color or T.GRAY)


def display_name(kind: str, name: str) -> str:
    return pretty_site(name) if kind == "site" else pretty_app(name)


class Page(QWidget):
    def refresh(self) -> None:  # overridden
        pass

    def enter(self) -> None:
        """Play the page's entrance (staggered count-ups, growing bars). Called when the page becomes visible."""


# ======================================================================== SETTINGS
class Swatch(QWidget):
    """A colour chip with its hex value; click to pick a new colour."""

    def __init__(self, color: str, title: str, on_pick):
        super().__init__()
        self.color, self.title, self.on_pick = color, title, on_pick
        self.setFixedSize(132, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        picked = QColorDialog.getColor(QColor(self.color), self.window(), self.title)
        if picked.isValid() and picked.name().lower() != self.color.lower():
            self.on_pick(picked.name())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(T.INK if self._hover else T.LINE), 1))
        p.setBrush(QColor(T.PAPER))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)
        p.setPen(QPen(QColor(T.EDGE), 1))
        p.setBrush(QColor(self.color))
        p.drawEllipse(8, 6, 18, 18)
        p.setFont(T.mono(12))
        p.setPen(QColor(T.INK))
        p.drawText(self.rect().adjusted(34, 0, 0, 0), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.color.upper())


class SettingRow(QWidget):
    def __init__(self, title: str, desc: str, control: QWidget, last: bool = False):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        row = QHBoxLayout()
        row.setContentsMargins(18, 12, 18, 12)
        col = QVBoxLayout()
        col.setSpacing(1)
        col.addWidget(mk_label(title, T.sans(13, T.QFont.Weight.Medium)))
        if desc:
            col.addWidget(mk_label(desc, T.sans(12), T.GRAY))
        row.addLayout(col, 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(row)
        if not last:
            line = Hairline()
            line.setContentsMargins(18, 0, 18, 0)
            v.addWidget(line)


class SiteRow(QWidget):
    def __init__(self, entry: dict, on_change, on_remove):
        super().__init__()
        self.entry = entry
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(12)
        tile = QLabel(pretty_site(entry["domain"])[:1].upper())
        tile.setFixedSize(28, 28)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setFont(T.mono(12, T.QFont.Weight.Bold))
        tile.setStyleSheet(f"background:{T.PAPER}; color:{T.INK}; border:1px solid {T.LINE}; border-radius:8px;")
        lay.addWidget(tile)
        col = QVBoxLayout()
        col.setSpacing(0)
        yt = entry["domain"] == "youtube.com"
        col.addWidget(mk_label("YouTube (without Shorts)" if yt else pretty_site(entry["domain"]), T.sans(13, T.QFont.Weight.Medium)))
        col.addWidget(mk_label("youtube.com · Shorts have their own limits" if yt else entry["domain"], T.mono(10), T.GRAY))
        lay.addLayout(col, 1)
        self.step = Stepper(entry["limit"], 1, 600, 5, "min/day")
        self.step.setFixedWidth(150)
        self.step.changed.connect(lambda val: (entry.__setitem__("limit", val), on_change()))
        lay.addWidget(self.step)
        tog = Toggle(entry["enabled"])
        tog.toggled.connect(lambda on: (entry.__setitem__("enabled", on), on_change()))
        lay.addWidget(tog)
        rm = LinkButton("remove", size=11)
        rm.clicked.connect(lambda: on_remove(entry))
        lay.addWidget(rm)


class AppRow(QWidget):
    """A desktop app with a daily limit."""

    def __init__(self, entry: dict, on_change, on_remove):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(12)
        tile = QLabel(pretty_app(entry["exe"])[:1].upper())
        tile.setFixedSize(28, 28)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setFont(T.mono(12, T.QFont.Weight.Bold))
        tile.setStyleSheet(f"background:{T.PAPER}; color:{T.INK}; border:1px solid {T.LINE}; border-radius:8px;")
        lay.addWidget(tile)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(mk_label(pretty_app(entry["exe"]), T.sans(13, T.QFont.Weight.Medium)))
        col.addWidget(mk_label(entry["exe"], T.mono(10), T.GRAY))
        lay.addLayout(col, 1)
        step = Stepper(entry["limit"], 1, 1440, 5, "min/day")
        step.setFixedWidth(150)
        step.changed.connect(lambda val: (entry.__setitem__("limit", val), on_change()))
        lay.addWidget(step)
        tog = Toggle(entry["enabled"])
        tog.toggled.connect(lambda on: (entry.__setitem__("enabled", on), on_change()))
        lay.addWidget(tog)
        rm = LinkButton("remove", size=11)
        rm.clicked.connect(lambda: on_remove(entry))
        lay.addWidget(rm)


class ReminderRow(QWidget):
    """One timer/alarm: on/off, message, every N minutes or at a time of day, sound, test, remove."""

    def __init__(self, item: dict, on_change, on_remove, on_test):
        super().__init__()
        self.item = item
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(10)

        on = Toggle(bool(item.get("enabled")))
        on.toggled.connect(lambda v: (item.__setitem__("enabled", v), on_change()))
        lay.addWidget(on)

        self.msg = QLineEdit(item.get("message", ""))
        self.msg.setPlaceholderText("message, e.g. Take a break")
        self.msg.setFixedHeight(30)
        self.msg.setMinimumWidth(180)
        self.msg.editingFinished.connect(lambda: (item.__setitem__("message", self.msg.text().strip() or "Take a break"), on_change()))
        lay.addWidget(self.msg, 1)

        seg = Segmented(["Every", "At"])
        seg.set_index(1 if item.get("mode") == "daily" else 0)
        lay.addWidget(seg)

        self.every = Stepper(int(item.get("every_min", 30)), 1, 720, 5, "min")
        self.every.changed.connect(lambda val: (item.__setitem__("every_min", val), on_change()))
        lay.addWidget(self.every)

        self.at = QLineEdit(item.get("time", "13:00"))
        self.at.setInputMask("99:99")
        self.at.setFixedSize(76, 30)
        self.at.setFont(T.mono(12))
        self.at.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.at.editingFinished.connect(self._commit_time(on_change))
        lay.addWidget(self.at)

        def show_mode(daily: bool) -> None:
            self.every.setVisible(not daily)
            self.at.setVisible(daily)
        show_mode(item.get("mode") == "daily")
        seg.changed.connect(lambda i: (item.__setitem__("mode", "daily" if i else "interval"), show_mode(bool(i)), on_change()))

        snd = Toggle(bool(item.get("sound", True)))
        snd.setToolTip("Play a chime")
        snd.toggled.connect(lambda v: (item.__setitem__("sound", v), on_change()))
        lay.addWidget(snd)

        test = LinkButton("test", size=11)
        test.clicked.connect(lambda: on_test(item))
        rm = LinkButton("remove", size=11)
        rm.clicked.connect(lambda: on_remove(item))
        lay.addWidget(test)
        lay.addWidget(rm)

    def _commit_time(self, on_change):
        def go():
            from ..reminders import valid_time
            text = self.at.text()
            if valid_time(text):
                self.item["time"] = text
                on_change()
            else:
                self.at.setText(self.item.get("time", "13:00"))
        return go


class SettingsPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        cfg = ctx.cfg
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 6, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        body = QWidget()
        body.setAutoFillBackground(False)
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 30, 26)
        v.setSpacing(10)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        v.addWidget(mk_label("Settings", T.sans(26, T.QFont.Weight.Medium)))
        v.addWidget(mk_label("Changes apply instantly. Everything stays on this computer.", T.sans(13), T.GRAY))
        v.addSpacing(6)

        # --- appearance
        v.addWidget(caps("Appearance"))
        mode = cfg.get("theme_mode")
        seg = Segmented(["Light", "Dark", "Custom"])
        seg.set_index(["light", "dark", "custom"].index(mode) if mode in ("light", "dark", "custom") else 0)
        seg.changed.connect(lambda i: cfg.set("theme_mode", ["light", "dark", "custom"][i]))
        rows = [SettingRow("Theme", "Applies to the app, the lock screen and the popup.", seg, last=(mode != "custom"))]
        if mode == "custom":
            rows += [
                SettingRow("Background", "", Swatch(cfg.get("theme_bg"), "Background colour", lambda c: cfg.set("theme_bg", c))),
                SettingRow("Text", "", Swatch(cfg.get("theme_text"), "Text colour", lambda c: cfg.set("theme_text", c))),
                SettingRow("Accent", "Warnings, the timer, small highlights.", Swatch(cfg.get("theme_accent"), "Accent colour", lambda c: cfg.set("theme_accent", c)), last=True),
            ]
        v.addWidget(self._group(rows))
        v.addSpacing(8)

        # --- attention
        v.addWidget(caps("Attention"))
        v.addWidget(self._group([
            SettingRow("Reminders", "Show the PHI nudge when a limit is crossed.", self._toggle("reminders")),
            SettingRow("Full-screen lockdown", "Take over the screen and close Shorts for you. Off = a small card.", self._toggle("lockdown")),
            SettingRow("Pause the video behind", "Pauses playback when the lock appears; resumes if you buy more time.", self._toggle("pause_video")),
            SettingRow("Lockdown countdown", "Seconds before PHI closes Shorts for you.", self._stepper("lockdown_seconds", 5, 40, 5, "s")),
            SettingRow("Shorts session limit", "Continuous Shorts time before a nudge. 0 = right away.", self._stepper("shorts_limit_min", 0, 240, 1, "min")),
            SettingRow("Shorts daily budget", "Total Shorts time per day. 0 turns it off.", self._stepper("shorts_daily_min", 0, 600, 10, "min")),
            SettingRow("“Give me more” adds", "How long a snooze lasts.", self._stepper("extend_min", 1, 60, 1, "min")),
            SettingRow("“Pause reminders” lasts", "", self._stepper("pause_min", 5, 480, 5, "min")),
            SettingRow("“It's for something important” lasts", "No nudges for this long.", self._stepper("bypass_min", 5, 480, 5, "min"), last=True),
        ]))

        # --- timers & alarms
        v.addSpacing(8)
        v.addWidget(caps("Timers & alarms"))
        self.rem_panel = Panel(hoverable=False)
        self.rem_lay = QVBoxLayout(self.rem_panel)
        self.rem_lay.setContentsMargins(0, 6, 0, 6)
        self.rem_lay.setSpacing(0)
        v.addWidget(self.rem_panel)
        add_row = QWidget()
        arl = QHBoxLayout(add_row)
        arl.setContentsMargins(0, 0, 0, 0)
        add_btn = PillButton("Add timer / alarm", "primary", "plus", height=34)
        add_btn.setFixedWidth(190)
        add_btn.clicked.connect(self._add_reminder)
        arl.addWidget(add_btn)
        arl.addSpacing(12)
        arl.addWidget(mk_label("Full-screen, in your theme. Interval timers restart when you step away for 5 min.", T.sans(12), T.GRAY), 1)
        v.addWidget(add_row)
        v.addWidget(self._group([
            SettingRow("Snooze lasts", "How long the Snooze button waits.", self._stepper("reminder_snooze_min", 1, 60, 1, "min"), last=True),
        ]))
        self._build_reminders()

        # --- watched apps
        v.addSpacing(8)
        v.addWidget(caps("Watched apps"))
        self.apps_panel = Panel(hoverable=False)
        self.apps_lay = QVBoxLayout(self.apps_panel)
        self.apps_lay.setContentsMargins(0, 6, 0, 6)
        self.apps_lay.setSpacing(0)
        v.addWidget(self.apps_panel)
        v.addWidget(self._add_field("add an app, e.g. discord", self._add_app))
        self.recent_box = QWidget()
        self.recent_lay = QHBoxLayout(self.recent_box)
        self.recent_lay.setContentsMargins(0, 0, 0, 0)
        self.recent_lay.setSpacing(8)
        v.addWidget(self.recent_box)
        self._build_apps()

        # --- watched sites
        v.addSpacing(8)
        v.addWidget(caps("Watched websites"))
        self.sites_panel = Panel(hoverable=False)
        self.sites_lay = QVBoxLayout(self.sites_panel)
        self.sites_lay.setContentsMargins(0, 6, 0, 6)
        self.sites_lay.setSpacing(0)
        v.addWidget(self.sites_panel)
        v.addWidget(self._add_field("add a site, e.g. reddit.com", self._add_watched))
        self._build_sites()

        # --- excluded
        v.addSpacing(8)
        v.addWidget(caps("Never track these sites"))
        self.ex_panel = Panel(hoverable=False)
        self.ex_lay = QVBoxLayout(self.ex_panel)
        self.ex_lay.setContentsMargins(18, 14, 18, 14)
        v.addWidget(self.ex_panel)
        v.addWidget(self._add_field("exclude a site, e.g. mybank.com", self._add_excluded))
        self._build_excluded()

        # --- monitoring
        v.addSpacing(8)
        v.addWidget(caps("Monitoring"))
        name = QLineEdit(cfg.get("name"))
        name.setPlaceholderText("optional")
        name.setFixedSize(180, 30)
        name.editingFinished.connect(lambda: cfg.set("name", name.text().strip()))
        auto = self._toggle("autostart")
        v.addWidget(self._group([
            SettingRow("Your name", "Used in the greeting.", name),
            SettingRow("Start with Windows", "PHI waits quietly in the tray.", auto),
            SettingRow("Track apps", "Record which desktop apps you use. Browser sites use the extension.", self._toggle("track_apps")),
            SettingRow("Idle after", "No keyboard or mouse for this long counts as away.", self._stepper("idle_threshold_s", 30, 900, 30, "s"), last=True),
        ]))

        # --- data
        v.addSpacing(8)
        v.addWidget(caps("Data"))
        v.addWidget(self._group([
            SettingRow("Keep history for", "Older days are deleted automatically.", self._stepper("retention_days", 7, 730, 7, "days")),
            SettingRow("Stored locally", "No keystrokes. No screenshots. No page content. Only app names, site names and durations.",
                       mk_label("LOCAL ONLY", T.mono(11, T.QFont.Weight.Medium, 1.6), T.GRAY, Qt.AlignmentFlag.AlignRight), last=True),
        ]))
        v.addStretch(1)

    # ---- builders
    def _group(self, rows: list[QWidget]) -> Panel:
        p = Panel(hoverable=False)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(0)
        for r in rows:
            lay.addWidget(r)
        return p

    def _toggle(self, key: str) -> Toggle:
        t = Toggle(bool(self.ctx.cfg.get(key)))
        t.toggled.connect(lambda on: self._set_toggle(key, on))
        return t

    def _set_toggle(self, key: str, on: bool):
        self.ctx.cfg.set(key, on)
        if key == "autostart":
            autostart.set_enabled(on)

    def _stepper(self, key: str, lo: int, hi: int, step: int, unit: str) -> Stepper:
        s = Stepper(self.ctx.cfg.get(key), lo, hi, step, unit)
        s.changed.connect(lambda val: self.ctx.cfg.set(key, val))
        return s

    def _add_field(self, placeholder: str, on_submit) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setFixedHeight(34)
        edit.setFont(T.mono(12))
        btn = PillButton("Add", "primary", "plus", height=34)
        btn.setFixedWidth(84)

        def go():
            if on_submit(edit.text()):
                edit.clear()
        edit.returnPressed.connect(go)
        btn.clicked.connect(go)
        lay.addWidget(edit, 1)
        lay.addWidget(btn)
        return w

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _save_reminders(self) -> None:
        self.ctx.cfg.set("reminder_items", list(self.ctx.cfg.get("reminder_items")))

    def _build_reminders(self) -> None:
        self._clear(self.rem_lay)
        items = self.ctx.cfg.get("reminder_items")
        if not items:
            self.rem_lay.addWidget(mk_label("  No timers yet. Add one, e.g. \"Take a break\" every 30 min.", T.mono(11), T.GRAY))
        for it in items:
            self.rem_lay.addWidget(ReminderRow(it, self._save_reminders, self._remove_reminder, self._test_reminder))

    def _add_reminder(self) -> None:
        from ..reminders import new_reminder
        self.ctx.cfg.set("reminder_items", list(self.ctx.cfg.get("reminder_items")) + [new_reminder()])
        self._build_reminders()

    def _remove_reminder(self, item: dict) -> None:
        self.ctx.cfg.set("reminder_items", [r for r in self.ctx.cfg.get("reminder_items") if r is not item])
        self._build_reminders()

    def _test_reminder(self, item: dict) -> None:
        if self.ctx.scheduler:
            self.ctx.scheduler.test(item)

    def _save_apps(self) -> None:
        self.ctx.cfg.set("watched_apps", list(self.ctx.cfg.get("watched_apps")))

    def _build_apps(self) -> None:
        self._clear(self.apps_lay)
        apps = self.ctx.cfg.get("watched_apps")
        if not apps:
            self.apps_lay.addWidget(mk_label("  No watched apps. Add one below, or pick a recent one.", T.mono(11), T.GRAY))
        for e in apps:
            self.apps_lay.addWidget(AppRow(e, self._save_apps, self._remove_app))
        # one-click suggestions: the apps you used most in the last week
        self._clear(self.recent_lay)
        watched = {e["exe"].lower() for e in apps}
        today = date.today()
        rows = self.ctx.store.by_name((today - timedelta(days=7)).isoformat(), today.isoformat(), ("app",))
        picks = [name for _k, name, secs in rows if name not in watched and secs >= 60][:6]
        if picks:
            self.recent_lay.addWidget(mk_label("RECENT", T.mono(9, spacing=1.4), T.GRAY))
        for exe in picks:
            btn = PillButton(f"+ {pretty_app(exe)}", "secondary", height=28)
            btn.setFixedWidth(max(90, 24 + 8 * len(pretty_app(exe))))
            btn.clicked.connect(lambda _=False, x=exe: self._add_app(x))
            self.recent_lay.addWidget(btn)
        self.recent_lay.addStretch(1)

    def _add_app(self, text: str) -> bool:
        exe = text.strip().lower().replace(" ", "")
        if not exe or any(ch in exe for ch in '\\/:*?"<>|'):
            return False
        if not exe.endswith(".exe"):
            exe += ".exe"
        apps = list(self.ctx.cfg.get("watched_apps"))
        if not any(a["exe"].lower() == exe for a in apps):
            apps.append({"exe": exe, "limit": 60, "enabled": True})
            self.ctx.cfg.set("watched_apps", apps)
            self._build_apps()
        return True

    def _remove_app(self, entry: dict) -> None:
        self.ctx.cfg.set("watched_apps", [a for a in self.ctx.cfg.get("watched_apps") if a is not entry])
        self._build_apps()

    def _build_sites(self):
        self._clear(self.sites_lay)
        sites = self.ctx.cfg.get("watched_sites")
        if not sites:
            self.sites_lay.addWidget(mk_label("  No watched sites. Add one below.", T.mono(11), T.GRAY))
        for e in sites:
            self.sites_lay.addWidget(SiteRow(e, lambda: self.ctx.cfg.set("watched_sites", list(self.ctx.cfg.get("watched_sites"))), self._remove_watched))

    def _add_watched(self, text: str) -> bool:
        d = clean_domain(text)
        if "." not in d:
            return False
        sites = list(self.ctx.cfg.get("watched_sites"))
        if not any(s["domain"] == d for s in sites):
            sites.append({"domain": d, "limit": 15, "enabled": True})
            self.ctx.cfg.set("watched_sites", sites)
            self._build_sites()
        return True

    def _remove_watched(self, entry: dict):
        self.ctx.cfg.set("watched_sites", [s for s in self.ctx.cfg.get("watched_sites") if s["domain"] != entry["domain"]])
        self._build_sites()

    def _build_excluded(self):
        self._clear(self.ex_lay)
        items = self.ctx.cfg.get("excluded_sites")
        if not items:
            self.ex_lay.addWidget(mk_label("Nothing excluded. Time on excluded sites is never recorded.", T.mono(11), T.GRAY))
        for d in items:
            row = QHBoxLayout()
            w = QWidget()
            w.setLayout(row)
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(mk_label(d, T.mono(12)), 1)
            rm = LinkButton("remove", size=11)
            rm.clicked.connect(lambda _=False, dom=d: self._remove_excluded(dom))
            row.addWidget(rm)
            self.ex_lay.addWidget(w)

    def _add_excluded(self, text: str) -> bool:
        d = clean_domain(text)
        if "." not in d:
            return False
        items = list(self.ctx.cfg.get("excluded_sites"))
        if d not in items:
            items.append(d)
            self.ctx.cfg.set("excluded_sites", items)
            self._build_excluded()
        return True

    def _remove_excluded(self, d: str):
        self.ctx.cfg.set("excluded_sites", [x for x in self.ctx.cfg.get("excluded_sites") if x != d])
        self._build_excluded()

