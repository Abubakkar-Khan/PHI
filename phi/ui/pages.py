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


# ======================================================================== TODAY
class TodayPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        v = QVBoxLayout(self)
        v.setContentsMargins(30, 6, 30, 26)
        v.setSpacing(18)

        head = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)
        self.greet = mk_label("", T.sans(30, T.QFont.Weight.Medium))
        self.greet.setWordWrap(True)
        left.addWidget(self.greet)
        left.addWidget(mk_label("Stay intentional. Your time matters.", T.sans(13), T.GRAY))
        head.addLayout(left, 1)
        right = QVBoxLayout()
        right.setSpacing(2)
        right.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.date_lbl = mk_label("", T.mono(11, spacing=1.2), T.GRAY, Qt.AlignmentFlag.AlignRight)
        self.chip = StatusChip()
        self.link_lbl = mk_label("", T.mono(10, spacing=1.0), T.GRAY, Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.date_lbl)
        right.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignRight)
        right.addWidget(self.link_lbl)
        head.addLayout(right)
        v.addLayout(head)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.c_active = StatCard("Active time")
        self.c_shorts = StatCard("YouTube Shorts")
        self.c_nudges = StatCard("Nudges")
        for c in (self.c_active, self.c_shorts, self.c_nudges):
            cards.addWidget(c, 1)
        v.addLayout(cards)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        tl_panel = Panel(hoverable=False)
        tl = QVBoxLayout(tl_panel)
        tl.setContentsMargins(20, 16, 20, 12)
        tl.addWidget(caps("Today's activity"))
        self.timeline = Timeline()
        tl.addWidget(self.timeline, 1)
        bottom.addWidget(tl_panel, 5)

        top_panel = Panel(hoverable=False)
        self.top_layout = QVBoxLayout(top_panel)
        self.top_layout.setContentsMargins(14, 16, 14, 12)
        self.top_layout.setSpacing(0)
        t = caps("Top apps & sites")
        t.setContentsMargins(6, 0, 0, 6)
        self.top_layout.addWidget(t)
        self.top_rows = QVBoxLayout()
        self.top_rows.setSpacing(0)
        self.top_layout.addLayout(self.top_rows)
        self.top_layout.addStretch(1)
        bottom.addWidget(top_panel, 3)
        v.addLayout(bottom, 1)
        self._top_keys: list | None = None
        self._top_widgets: list[TopRow] = []

    def enter(self) -> None:
        for i, c in enumerate((self.c_active, self.c_shorts, self.c_nudges)):
            c.replay(i * 70)
        self.timeline.replay()
        for i, row in enumerate(self._top_widgets):
            row.replay(180 + i * 70)

    def refresh(self) -> None:
        eng, s = self.ctx.engine, self.ctx.store
        eng.flush()
        now = datetime.now()
        today, yday = date.today(), date.today() - timedelta(days=1)
        name = self.ctx.cfg.get("name").strip()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        self.greet.setText(f"Good {part},\n{name}." if name else f"Good {part}.")
        self.date_lbl.setText(now.strftime("%a\n%b %d %Y").upper().replace("\n", "  ·  "))

        total = eng.today_seconds("total", "*")
        shorts = eng.today_seconds("shorts", "youtube")
        swipes = int(eng.today_seconds("swipes", "shorts"))
        nudges = s.event_count(today.isoformat(), "nudge")
        stopped = s.event_count(today.isoformat(), "stop")

        def delta(cur: float, prev: float, thresh: float = 60):
            if prev < thresh:
                return "", 0
            pct = round((cur - prev) / prev * 100)
            if pct == 0:
                return "SAME AS YDAY", 0
            return f"{abs(pct)}% VS YDAY", 1 if pct > 0 else -1

        p_total = s.total_until(yday.isoformat(), "total", "*", now.hour)
        p_shorts = s.total_until(yday.isoformat(), "shorts", "youtube", now.hour)
        d, dr = delta(total, p_total)
        self.c_active.set_data(total, fmt_dur, "SINCE MIDNIGHT", d, dr, False, s.daily_series(today, 7, "total", "*"))
        d, dr = delta(shorts, p_shorts)
        sub = f"{swipes} SHORTS WATCHED" if swipes else "NOTHING TO REPORT" if shorts < 60 else "KEEP AN EYE ON IT"
        self.c_shorts.set_data(shorts, fmt_dur, sub, d, dr, dr > 0, s.daily_series(today, 7, "shorts", "youtube"))
        sub = f"{stopped} STOPPED WHEN ASKED" if nudges else "NO INTERRUPTIONS"
        self.c_nudges.set_data(nudges, lambda x: f"{round(x)}", sub, "", 0, False, s.event_series(today, 7, "nudge"))

        # timeline rows: Shorts first, then the three heaviest items
        items = self._ranked(today.isoformat())
        rows = []
        if shorts > 0:
            rows.append(("YouTube Shorts", s.hourly(today.isoformat(), "shorts", "youtube"), True))
        for kind, nm, _secs in items[:3 if shorts > 0 else 4]:
            rows.append((display_name(kind, nm), s.hourly(today.isoformat(), kind, nm), False))
        self.timeline.set_rows(rows)

        self._fill_top(items[:5], total)

        # header status
        self.update_status(getattr(self, "_last_snap", None))

    def _ranked(self, day: str):
        return self.ctx.store.by_name(day, day, ("app", "site"))

    def _fill_top(self, items, total):
        keys = [(k, n) for k, n, _ in items]
        if keys == self._top_keys:                     # same apps in the same order: just update the numbers
            for row, (_k, _n, secs) in zip(self._top_widgets, items):
                row.set_secs(secs)
            return
        self._top_keys, self._top_widgets = keys, []
        while self.top_rows.count():
            w = self.top_rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        if not items:
            empty = QWidget()
            lay = QVBoxLayout(empty)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            m = Mascot(px=3, mood="idle", fill=T.SURFACE)
            lay.addWidget(m, 0, Qt.AlignmentFlag.AlignHCenter)
            lay.addWidget(mk_label("Nothing logged yet.", T.sans(13, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignHCenter))
            lay.addWidget(mk_label("PHI is watching quietly_", T.mono(10), T.GRAY, Qt.AlignmentFlag.AlignHCenter))
            self.top_rows.addWidget(empty)
            return
        for i, (kind, nm, secs) in enumerate(items):
            row = TopRow(display_name(kind, nm), kind, secs, delay=i * 70)
            self._top_widgets.append(row)
            self.top_rows.addWidget(row)

    def update_status(self, snap: dict | None) -> None:
        if snap is None:
            return
        self._last_snap = snap
        st = snap["status"]
        if st == "paused":
            self.chip.set_state("PAUSED", "off")
        elif st == "shorts":
            self.chip.set_state("SHORTS DETECTED", "alert")
        elif st == "idle":
            self.chip.set_state("IDLE", "off")
        else:
            self.chip.set_state("MONITORING", "on")
        if snap["link"]:
            self.link_lbl.setText("BROWSER LINK ● ONLINE")
        else:
            self.link_lbl.setText("BROWSER LINK ○ OFFLINE")


class TopRow(QWidget):
    def __init__(self, name: str, kind: str, secs: float, delay: int = 0):
        super().__init__()
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        tile = QLabel(name[:1].upper())
        tile.setFixedSize(28, 28)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setFont(T.mono(12, T.QFont.Weight.Bold))
        tile.setStyleSheet(f"background:{T.PAPER}; color:{T.INK}; border:1px solid {T.LINE}; border-radius:8px;")
        lay.addWidget(tile)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(mk_label(name, T.sans(13, T.QFont.Weight.Medium)))
        col.addWidget(mk_label(kind.upper(), T.mono(9, spacing=1.2), T.GRAY))
        lay.addLayout(col, 1)
        self.time_lbl = mk_label(fmt_dur(secs), T.mono(12, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.time_lbl)
        self._secs_text = self.time_lbl.text()
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.timeout.connect(self._fade_in)
        self.replay(delay)

    def set_secs(self, secs: float) -> None:
        text = fmt_dur(secs)
        if text != self._secs_text:
            self._secs_text = text
            self.time_lbl.setText(text)

    def replay(self, delay: int = 0) -> None:
        """Fade in. The effect lives only for the fade (these rows are tiny, so it is cheap)."""
        eff = QGraphicsOpacityEffect(self)
        eff.setOpacity(0.0)
        self.setGraphicsEffect(eff)
        self._delay.start(max(0, delay))

    def _fade_in(self) -> None:
        eff = self.graphicsEffect()
        if eff is None:
            return
        a = QPropertyAnimation(eff, b"opacity", self)
        a.setDuration(380)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(lambda: self.setGraphicsEffect(None))
        a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


# ======================================================================== APPS & SITES
class AppsPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        v = QVBoxLayout(self)
        v.setContentsMargins(30, 6, 30, 26)
        v.setSpacing(16)
        v.addWidget(mk_label("Apps & Sites", T.sans(26, T.QFont.Weight.Medium)))
        v.addWidget(mk_label("Where your time actually went.", T.sans(13), T.GRAY))

        bar = QHBoxLayout()
        self.range_seg = Segmented(["Today", "7 days"])
        self.kind_seg = Segmented(["All", "Apps", "Sites"])
        bar.addWidget(self.range_seg)
        bar.addStretch(1)
        self.sum_lbl = mk_label("", T.mono(11, spacing=.8), T.GRAY, Qt.AlignmentFlag.AlignRight)
        bar.addWidget(self.sum_lbl)
        bar.addSpacing(14)
        bar.addWidget(self.kind_seg)
        v.addLayout(bar)

        chart_panel = Panel(hoverable=False)
        cl = QVBoxLayout(chart_panel)
        cl.setContentsMargins(20, 14, 20, 10)
        legend = QHBoxLayout()
        legend.addWidget(caps("Active time"))
        legend.addStretch(1)
        legend.addWidget(mk_label("■ ACTIVE   ", T.mono(9, spacing=1), T.INK))
        legend.addWidget(mk_label("■ SHORTS", T.mono(9, spacing=1), T.RED))
        cl.addLayout(legend)
        self.chart = PixelChart()
        cl.addWidget(self.chart)
        v.addWidget(chart_panel, 3)

        list_panel = Panel(hoverable=False)
        ll = QVBoxLayout(list_panel)
        ll.setContentsMargins(10, 12, 10, 10)
        ll.setSpacing(0)
        t = caps("Breakdown")
        t.setContentsMargins(10, 0, 0, 4)
        ll.addWidget(t)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.holder = QWidget()
        self.holder.setAutoFillBackground(False)
        self.rows = QVBoxLayout(self.holder)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(0)
        self.rows.addStretch(1)
        self.scroll.setWidget(self.holder)
        ll.addWidget(self.scroll)
        v.addWidget(list_panel, 4)

        self.range_seg.changed.connect(lambda _: self.refresh(True))
        self.kind_seg.changed.connect(lambda _: self.refresh(True))
        self._keys: list | None = None
        self._rows_w: list[UsageRow] = []

    def enter(self) -> None:
        self.chart.replay()
        for i, row in enumerate(self._rows_w):
            row.replay(60 + 40 * i)

    def refresh(self, force: bool = False) -> None:
        s = self.ctx.store
        self.ctx.engine.flush()        # cheap now (WAL + synchronous=NORMAL); the page reads from the database
        today = date.today()
        week = self.range_seg.index == 1
        days = 7 if week else 1
        d0 = today - timedelta(days=days - 1)

        if week:
            totals = s.daily_series(today, 7, "total", "*")
            shorts = s.daily_series(today, 7, "shorts", "youtube")
            cols = [((today - timedelta(days=6 - i)).strftime("%a").upper(), totals[i], shorts[i], i == 6) for i in range(7)]
            avg = sum(totals) / 7
            self.sum_lbl.setText(f"TOTAL {fmt_dur(sum(totals))}  ·  AVG {fmt_dur(avg)}/DAY")
        else:
            hours = s.hourly(today.isoformat(), "total", "*")
            sh = s.hourly(today.isoformat(), "shorts", "youtube")
            cols = [(f"{h:02d}" if h % 3 == 0 else "", hours[h], sh[h], h == datetime.now().hour) for h in range(24)]
            self.sum_lbl.setText(f"TOTAL {fmt_dur(sum(hours))}  ·  SHORTS {fmt_dur(sum(sh))}")
        self.chart.set_columns(cols, replay=force)

        kinds = {0: ("app", "site"), 1: ("app",), 2: ("site",)}[self.kind_seg.index]
        data = s.by_name(d0.isoformat(), today.isoformat(), kinds)
        shorts_total = sum(s.daily_series(today, days, "shorts", "youtube"))
        denom = max(sum(sec for _, _, sec in data), 1.0)
        entries = []                                   # (key, name, tag, seconds, share, red)
        if shorts_total >= 1 and self.kind_seg.index != 1:
            entries.append((("shorts", "youtube"), "YouTube Shorts", "inside youtube", shorts_total, min(1.0, shorts_total / denom), True))
        for kind, nm, sec in data:
            entries.append(((kind, nm), display_name(kind, nm), kind, sec, sec / denom, False))

        keys = [e[0] for e in entries]
        if keys == self._keys and not force:           # same rows: slide the bars and numbers, rebuild nothing
            for row, e in zip(self._rows_w, entries):
                row.set_values(e[3], e[4])
            return
        self._keys, self._rows_w = keys, []
        while self.rows.count() > 1:
            w = self.rows.takeAt(0).widget()
            if w:
                w.deleteLater()
        for idx, (_key, name, tag, sec, share, red) in enumerate(entries):
            row = UsageRow(name, tag, sec, share, red, 40 * (idx + 1))
            self._rows_w.append(row)
            self.rows.insertWidget(idx, row)
        if not entries:
            self.rows.insertWidget(0, mk_label("Nothing here yet. Use your computer and come back_", T.mono(11), T.GRAY, Qt.AlignmentFlag.AlignCenter))


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
        col.addWidget(mk_label(pretty_site(entry["domain"]), T.sans(13, T.QFont.Weight.Medium)))
        col.addWidget(mk_label(entry["domain"], T.mono(10), T.GRAY))
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

        # --- watched sites
        v.addSpacing(8)
        v.addWidget(caps("Watched sites"))
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
        self.del_btn = PillButton("Delete all data", "secondary", height=32)
        self.del_btn.setFixedWidth(150)
        self.del_btn.clicked.connect(self._delete)
        self._armed = False
        open_btn = PillButton("Open folder", "secondary", height=32)
        open_btn.setFixedWidth(120)
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(ctx.store.path))))
        btns = QWidget()
        bl = QHBoxLayout(btns)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(open_btn)
        bl.addWidget(self.del_btn)
        v.addWidget(self._group([
            SettingRow("Keep history for", "Older days are deleted automatically.", self._stepper("retention_days", 7, 730, 7, "days")),
            SettingRow("Stored locally", "No keystrokes. No screenshots. No page content. Only app names, site names and durations.", btns, last=True),
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

    def _delete(self):
        if not self._armed:
            self._armed = True
            self.del_btn.setText("Click again to confirm")
            self.del_btn.setFixedWidth(190)
            from PySide6.QtCore import QTimer
            QTimer.singleShot(3500, self._disarm)
            return
        self.ctx.engine.flush()
        self.ctx.store.delete_all()
        self.ctx.engine._load_today()
        self._disarm()
        self.del_btn.setText("Deleted ✓")

    def _disarm(self):
        self._armed = False
        if self.del_btn.text() != "Deleted ✓":
            self.del_btn.setText("Delete all data")
            self.del_btn.setFixedWidth(150)
