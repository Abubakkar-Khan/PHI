"""Settings: four short tabs (General, Apps, Websites, Timers). Changes apply instantly."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QColorDialog, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import autostart
from ..utils import clean_domain, pretty_app, pretty_site
from . import theme as T
from .apppicker import AppPicker
from .hiddendialog import HiddenDialog
from .mascot import VARIANTS
from .pages import Ctx, Page, mk_label
from .widgets import Hairline, LinkButton, Panel, PillButton, Segmented, Stepper, Toggle


def section(text: str) -> QLabel:
    lb = mk_label(text, T.sans(17, T.QFont.Weight.Medium), T.INK)
    lb.setContentsMargins(2, 10, 0, 4)
    return lb


def note(text: str) -> QLabel:
    lb = mk_label(text, T.sans(13), T.GRAY)
    lb.setWordWrap(True)
    return lb


def tile(text: str) -> QLabel:
    t = QLabel(text[:1].upper())
    t.setFixedSize(34, 34)
    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
    t.setFont(T.sans(15, T.QFont.Weight.Medium))
    t.setStyleSheet(f"background:{T.SOFT}; color:{T.INK}; border-radius:10px;")
    return t


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
        p.setFont(T.sans(12))
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
        col.addWidget(mk_label(title, T.sans(14, T.QFont.Weight.Medium)))
        if desc:
            col.addWidget(mk_label(desc, T.sans(12), T.GRAY))
        row.addLayout(col, 1)
        row.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        v.addLayout(row)
        if not last:
            line = Hairline()
            line.setContentsMargins(18, 0, 18, 0)
            v.addWidget(line)


class LimitRow(QWidget):
    """Name + sub-line, a daily limit, an on/off switch and remove. Used for apps and websites."""

    def __init__(self, entry: dict, name: str, sub: str, on_change, on_remove):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 8, 18, 8)
        lay.setSpacing(12)
        lay.addWidget(tile(name))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(mk_label(name, T.sans(14, T.QFont.Weight.Medium)))
        col.addWidget(mk_label(sub, T.sans(12), T.GRAY))
        lay.addLayout(col, 1)
        step = Stepper(entry["limit"], 1, 1440, 5, "min/day")
        step.setFixedWidth(150)
        step.changed.connect(lambda val: (entry.__setitem__("limit", val), on_change()))
        lay.addWidget(step)
        tog = Toggle(entry["enabled"])
        tog.toggled.connect(lambda on: (entry.__setitem__("enabled", on), on_change()))
        lay.addWidget(tog)
        rm = LinkButton("Remove", size=12)
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
        self.msg.setPlaceholderText("Message, e.g. Take a break")
        self.msg.setFixedHeight(30)
        self.msg.setMinimumWidth(160)
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
        self.at.setFont(T.sans(13))
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

        test = LinkButton("Test", size=12)
        test.clicked.connect(lambda: on_test(item))
        rm = LinkButton("Remove", size=12)
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
    TABS = ["General", "Apps", "Websites", "Timers"]

    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 10, 0, 0)
        outer.setSpacing(16)
        outer.addWidget(mk_label("Settings", T.sans(32, T.QFont.Weight.Medium)))
        self.tabs = Segmented(self.TABS)
        outer.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignLeft)
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        for build in (self._general, self._apps, self._websites, self._timers):
            self.stack.addWidget(self._scrolled(build()))
        self.tabs.changed.connect(self.stack.setCurrentIndex)

    # ---- shared builders
    @staticmethod
    def _scrolled(body: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        scroll.setWidget(body)
        return scroll

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 40, 32)
        v.setSpacing(10)
        return w, v

    @staticmethod
    def _group(rows: list[QWidget]) -> Panel:
        p = Panel(hoverable=False)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(0)
        for r in rows:
            lay.addWidget(r)
        return p

    @staticmethod
    def _list_panel() -> tuple[Panel, QVBoxLayout]:
        p = Panel(hoverable=False)
        lay = QVBoxLayout(p)
        lay.setContentsMargins(0, 6, 0, 6)
        lay.setSpacing(0)
        return p, lay

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
        edit.setFixedHeight(36)
        btn = PillButton("Add", "primary", height=36)
        btn.setFixedWidth(84)

        def go():
            if on_submit(edit.text()):
                edit.clear()
        edit.returnPressed.connect(go)
        btn.clicked.connect(go)
        lay.addWidget(edit, 1)
        lay.addWidget(btn)
        return w

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            w = layout.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    # ---- General
    def _general(self) -> QWidget:
        cfg = self.ctx.cfg
        page, v = self._page()

        v.addWidget(section("Appearance"))
        mode = cfg.get("theme_mode")
        seg = Segmented(["Light", "Dark", "Custom"])
        seg.set_index(["light", "dark", "custom"].index(mode) if mode in ("light", "dark", "custom") else 0)
        seg.changed.connect(lambda i: cfg.set("theme_mode", ["light", "dark", "custom"][i]))
        rows = [SettingRow("Theme", "", seg, last=(mode != "custom"))]
        if mode == "custom":
            rows += [
                SettingRow("Background", "", Swatch(cfg.get("theme_bg"), "Background colour", lambda c: cfg.set("theme_bg", c))),
                SettingRow("Text", "", Swatch(cfg.get("theme_text"), "Text colour", lambda c: cfg.set("theme_text", c))),
                SettingRow("Accent", "", Swatch(cfg.get("theme_accent"), "Accent colour", lambda c: cfg.set("theme_accent", c)), last=True),
            ]
        v.addWidget(self._group(rows))

        v.addSpacing(8)
        v.addWidget(section("When a limit is reached"))
        v.addWidget(self._group([
            SettingRow("Remind me", "Show a message when a limit is reached.", self._toggle("reminders")),
            SettingRow("Full-screen lock", "Cover the screen instead of showing a small card.", self._toggle("lockdown")),
            SettingRow("Countdown", "Seconds before PHI minimizes or closes it for you.", self._stepper("lockdown_seconds", 5, 40, 5, "s")),
            SettingRow("“More time” adds", "", self._stepper("extend_min", 1, 60, 1, "min")),
            SettingRow("Pause the video", "Stops playback behind the lock.", self._toggle("pause_video"), last=True),
        ]))

        v.addSpacing(8)
        v.addWidget(section("General"))
        name = QLineEdit(cfg.get("name"))
        name.setPlaceholderText("Optional")
        name.setFixedSize(180, 30)
        name.editingFinished.connect(lambda: cfg.set("name", name.text().strip()))
        keys = list(VARIANTS)
        char_seg = Segmented(list(VARIANTS.values()))
        char_seg.set_index(keys.index(cfg.get("character")) if cfg.get("character") in keys else 0)
        char_seg.changed.connect(lambda i: cfg.set("character", keys[i]))
        v.addWidget(self._group([
            SettingRow("Character", "Your companion: Phi or Fia.", char_seg),
            SettingRow("Your name", "Used in the greeting.", name),
            SettingRow("Start with Windows", "", self._toggle("autostart")),
            SettingRow("Keep history for", "Older days are deleted automatically.", self._stepper("retention_days", 7, 730, 7, "days"), last=True),
        ]))
        v.addWidget(section("Privacy"))
        review = PillButton("Review\u2026", "secondary", height=32)
        review.setFixedWidth(104)
        review.clicked.connect(lambda: HiddenDialog(cfg, self.window()).exec())
        v.addWidget(self._group([
            SettingRow("Hidden activity", "Apps and websites you hid from Activity. Hide one by hovering its row.", review, last=True),
        ]))
        v.addWidget(note("Everything stays on this computer. PHI never records keystrokes, screenshots or page content."))
        v.addStretch(1)
        return page

    # ---- Apps
    def _apps(self) -> QWidget:
        page, v = self._page()
        v.addWidget(note("Set a daily limit for any app. When it is reached, PHI minimizes the app. Nothing is closed, so you never lose work."))
        self.apps_panel, self.apps_lay = self._list_panel()
        v.addWidget(self.apps_panel)
        row = QHBoxLayout()
        add = PillButton("Add app\u2026", "primary", "plus", height=36)
        add.setFixedWidth(150)
        add.clicked.connect(self._pick_app)
        row.addWidget(add)
        row.addStretch(1)
        v.addLayout(row)
        v.addStretch(1)
        self._build_apps()
        return page

    def _save_apps(self) -> None:
        self.ctx.cfg.set("watched_apps", list(self.ctx.cfg.get("watched_apps")))

    def _build_apps(self) -> None:
        self._clear(self.apps_lay)
        apps = self.ctx.cfg.get("watched_apps")
        if not apps:
            msg = mk_label("No limits yet. Add an app to start.", T.sans(13), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(70)
            self.apps_lay.addWidget(msg)
        for e in apps:
            label = e.get("label") or pretty_app(e["exe"])
            self.apps_lay.addWidget(LimitRow(e, label, e["exe"], self._save_apps, self._remove_app))

    def _pick_app(self) -> None:
        taken = {a["exe"].lower() for a in self.ctx.cfg.get("watched_apps")}
        dlg = AppPicker(self.window(), self.ctx.store, taken)
        if dlg.exec() and dlg.choice:
            exe = dlg.choice["exe"].lower()
            apps = list(self.ctx.cfg.get("watched_apps"))
            if not any(a["exe"].lower() == exe for a in apps):
                apps.append({"exe": exe, "label": dlg.choice["name"], "limit": 60, "enabled": True})
                self.ctx.cfg.set("watched_apps", apps)
                self._build_apps()

    def _remove_app(self, entry: dict) -> None:
        self.ctx.cfg.set("watched_apps", [a for a in self.ctx.cfg.get("watched_apps") if a is not entry])
        self._build_apps()

    # ---- Websites
    def _websites(self) -> QWidget:
        page, v = self._page()
        v.addWidget(note("Daily limits for websites. YouTube here counts everything except Shorts."))
        self.sites_panel, self.sites_lay = self._list_panel()
        v.addWidget(self.sites_panel)
        v.addWidget(self._add_field("Add a website, e.g. reddit.com", self._add_watched))
        self._build_sites()

        v.addSpacing(8)
        v.addWidget(section("YouTube Shorts"))
        v.addWidget(self._group([
            SettingRow("Session limit", "Continuous time before a reminder. 0 means right away.", self._stepper("shorts_limit_min", 0, 240, 1, "min")),
            SettingRow("Daily limit", "0 turns it off.", self._stepper("shorts_daily_min", 0, 600, 10, "min"), last=True),
        ]))

        v.addSpacing(8)
        v.addWidget(section("Never record"))
        self.ex_panel, self.ex_lay = self._list_panel()
        v.addWidget(self.ex_panel)
        v.addWidget(self._add_field("Add a website to ignore, e.g. mybank.com", self._add_excluded))
        self._build_excluded()
        v.addStretch(1)
        return page

    def _save_sites(self) -> None:
        self.ctx.cfg.set("watched_sites", list(self.ctx.cfg.get("watched_sites")))

    def _build_sites(self) -> None:
        self._clear(self.sites_lay)
        sites = self.ctx.cfg.get("watched_sites")
        if not sites:
            msg = mk_label("No websites yet. Add one below.", T.sans(13), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(70)
            self.sites_lay.addWidget(msg)
        for e in sites:
            yt = e["domain"] == "youtube.com"
            name = "YouTube" if yt else pretty_site(e["domain"])
            self.sites_lay.addWidget(LimitRow(e, name, "youtube.com, without Shorts" if yt else e["domain"], self._save_sites, self._remove_watched))

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

    def _remove_watched(self, entry: dict) -> None:
        self.ctx.cfg.set("watched_sites", [s for s in self.ctx.cfg.get("watched_sites") if s["domain"] != entry["domain"]])
        self._build_sites()

    def _build_excluded(self) -> None:
        self._clear(self.ex_lay)
        items = self.ctx.cfg.get("excluded_sites")
        if not items:
            msg = mk_label("Nothing ignored.", T.sans(13), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(56)
            self.ex_lay.addWidget(msg)
        for d in items:
            w = QWidget()
            row = QHBoxLayout(w)
            row.setContentsMargins(18, 8, 18, 8)
            row.addWidget(mk_label(d, T.sans(14)), 1)
            rm = LinkButton("Remove", size=12)
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

    def _remove_excluded(self, d: str) -> None:
        self.ctx.cfg.set("excluded_sites", [x for x in self.ctx.cfg.get("excluded_sites") if x != d])
        self._build_excluded()

    # ---- Timers
    def _timers(self) -> QWidget:
        page, v = self._page()
        v.addWidget(note("Full-screen reminders, for example \u201cTake a break\u201d every 30 minutes, or a message at a set time."))
        self.rem_panel, self.rem_lay = self._list_panel()
        v.addWidget(self.rem_panel)
        row = QHBoxLayout()
        add = PillButton("Add timer", "primary", "plus", height=36)
        add.setFixedWidth(150)
        add.clicked.connect(self._add_reminder)
        row.addWidget(add)
        row.addStretch(1)
        v.addLayout(row)
        v.addSpacing(8)
        v.addWidget(self._group([
            SettingRow("Snooze", "How long Snooze waits.", self._stepper("reminder_snooze_min", 1, 60, 1, "min"), last=True),
        ]))
        v.addStretch(1)
        self._build_reminders()
        return page

    def _save_reminders(self) -> None:
        self.ctx.cfg.set("reminder_items", list(self.ctx.cfg.get("reminder_items")))

    def _build_reminders(self) -> None:
        self._clear(self.rem_lay)
        items = self.ctx.cfg.get("reminder_items")
        if not items:
            msg = mk_label("No timers yet.", T.sans(13), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(70)
            self.rem_lay.addWidget(msg)
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
