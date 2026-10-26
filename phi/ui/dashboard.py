"""Today and Activity.

Three summary cards, a chart, and a ranked list. Apps come first; websites only when asked.
Plain language, one idea per card, nothing you have to decode.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import stats
from ..stats import Item
from ..utils import fmt_dur
from . import theme as T
from .pages import Ctx, Page, mk_label
from .widgets import (BarChart, ItemRow, LinkButton, Panel, PillButton, SectionTitle, Segmented, StatCard, StatusChip)

SCOPES = ("apps", "sites")           # the list switch: apps first, websites only when asked
SCOPE_NOUN = {"apps": "app", "sites": "website"}


def scrolling_body(page: QWidget, margins=(40, 12, 40, 36), spacing: int = 18) -> QVBoxLayout:
    """Give a page a transparent vertical scroll area and return the layout to fill."""
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.viewport().setAutoFillBackground(False)
    body = QWidget()
    body.setAutoFillBackground(False)
    v = QVBoxLayout(body)
    v.setContentsMargins(*margins)
    v.setSpacing(spacing)
    scroll.setWidget(body)
    outer.addWidget(scroll)
    return v


def _forget(layout: QVBoxLayout) -> None:
    """Remove every widget at once (deleteLater alone leaves them painted until the next event-loop turn)."""
    while layout.count():
        w = layout.takeAt(0).widget()
        if w:
            w.hide()
            w.setParent(None)
            w.deleteLater()


class ItemList(QWidget):
    """A ranked list. Reuses its rows when the ranking is unchanged.

    Rows can be hidden for good (display only); a short Undo bar appears under the list."""

    def __init__(self, empty_text: str, on_hide=None, on_undo=None):
        super().__init__()
        self.empty_text = empty_text
        self.on_hide, self.on_undo = on_hide, on_undo
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._rows_box = QWidget()
        self._lay = QVBoxLayout(self._rows_box)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        outer.addWidget(self._rows_box)
        self._toast = QWidget()
        tl = QHBoxLayout(self._toast)
        tl.setContentsMargins(20, 6, 20, 6)
        self._toast_lbl = mk_label("", T.sans(13), T.GRAY)
        self._undo = LinkButton("Undo", size=13)
        tl.addWidget(self._toast_lbl, 1)
        tl.addWidget(self._undo)
        self._toast.hide()
        outer.addWidget(self._toast)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._toast.hide)
        self._undo.clicked.connect(self._do_undo)
        self._undo_item: Item | None = None
        self._keys: list | None = None
        self._rows: list[ItemRow] = []

    def _hide_item(self, it: Item) -> None:
        if not self.on_hide:
            return
        self._undo_item = it
        self._toast_lbl.setText(f"\u201c{it.label}\u201d is hidden. Manage it in Settings \u203a General.")
        self._toast.show()
        self._timer.start(6000)
        self.on_hide(it)

    def _do_undo(self) -> None:
        it, self._undo_item = self._undo_item, None
        self._toast.hide()
        self._timer.stop()
        if it and self.on_undo:
            self.on_undo(it)

    def set_items(self, items: list[Item], force: bool = False) -> None:
        top = items[0].seconds if items else 1.0
        keys = [(i.kind, i.key) for i in items]
        if keys == self._keys and not force:
            for row, it in zip(self._rows, items):
                row.set_values(it.seconds, it.seconds / top)
            return
        self._keys, self._rows = keys, []
        _forget(self._lay)
        if not items:
            msg = mk_label(self.empty_text, T.sans(14), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(110)
            self._lay.addWidget(msg)
            return
        for idx, it in enumerate(items):
            row = ItemRow(it.label, it.seconds, it.seconds / top, last=idx == len(items) - 1, delay=50 * idx, index=idx + 1)
            row.hide_requested.connect(lambda it=it: self._hide_item(it))
            self._rows.append(row)
            self._lay.addWidget(row)

    def replay(self) -> None:
        for i, row in enumerate(self._rows):
            row.replay(80 + 50 * i)


def _hide_hooks(ctx: Ctx, page):
    def hide(it: Item) -> None:
        stats.hide_item(ctx.cfg, it.kind, it.key, it.label)
        page.refresh(True)

    def undo(it: Item) -> None:
        stats.unhide_item(ctx.cfg, it.kind, it.key)
        page.refresh(True)
    return hide, undo


def card_with(title_widget: QWidget, body: QWidget, margins=(18, 14, 18, 14)) -> Panel:
    card = Panel(hoverable=False)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(*margins)
    lay.setSpacing(6)
    lay.addWidget(title_widget)
    lay.addWidget(body)
    return card


# ======================================================================== TODAY
class TodayPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        v = scrolling_body(self)

        head = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        self.date_lbl = mk_label("", T.sans(13), T.GRAY)
        self.greet = mk_label("", T.sans(32, T.QFont.Weight.Medium))
        left.addWidget(self.date_lbl)
        left.addWidget(self.greet)
        head.addLayout(left, 1)
        self.chip = StatusChip()
        head.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        v.addLayout(head)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.c_time = StatCard("Screen time today")
        self.c_top = StatCard("Most used app")
        self.c_alerts = StatCard("Limits reached")
        self.cards = (self.c_time, self.c_top, self.c_alerts)
        for c in self.cards:
            cards.addWidget(c, 1)
        v.addLayout(cards)

        self.chart = BarChart()
        v.addWidget(card_with(SectionTitle("Activity by hour"), self.chart))

        self.kind_seg = Segmented(["Apps", "Websites"])
        self.list_title = SectionTitle("Where your time went", self.kind_seg)
        self.list = ItemList("Nothing over a minute yet.", *_hide_hooks(ctx, self))
        v.addWidget(card_with(self.list_title, self.list, margins=(12, 14, 12, 8)))
        v.addStretch(1)

        self.kind_seg.changed.connect(lambda _: self.refresh(True))

    def enter(self) -> None:
        for i, c in enumerate(self.cards):
            c.replay(i * 70)
        self.chart.replay()
        self.list.replay()

    def _series7(self, hidden) -> list[float]:
        today = date.today()
        got, _sh = stats.daily_scope(self.ctx.store, today - timedelta(days=6), today, "all", hidden)
        return [got.get((today - timedelta(days=6 - i)).isoformat(), 0.0) for i in range(7)]

    def refresh(self, force: bool = False) -> None:
        eng, s = self.ctx.engine, self.ctx.store
        eng.flush()
        now = datetime.now()
        today = date.today()
        name = self.ctx.cfg.get("name").strip()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        self.greet.setText(f"Good {part}, {name}." if name else f"Good {part}.")
        self.date_lbl.setText(now.strftime("%A, %d %B"))

        hidden = stats.hidden_pairs(self.ctx.cfg)
        hrs, _sh = stats.hourly_scope(s, today.isoformat(), "all", hidden)
        total = sum(hrs)
        yh, _ysh = stats.hourly_scope(s, (today - timedelta(days=1)).isoformat(), "all", hidden)
        prev = sum(yh[:now.hour + 1])
        sub = "since midnight"
        if prev >= 300 and total >= 60 and total < prev * 3:
            pct = round((total - prev) / prev * 100)
            if pct:
                sub = f"{abs(pct)}% {'more' if pct > 0 else 'less'} than yesterday so far"
        self.c_time.set_data(fmt_dur(total) if total >= 60 else "0m", sub, self._series7(hidden))

        scope = SCOPES[self.kind_seg.index]
        items = stats.breakdown(s, today.isoformat(), today.isoformat(), scope, hidden)
        self.c_top.title = f"Most used {SCOPE_NOUN[scope]}"
        if items:
            self.c_top.set_data(items[0].label, f"{fmt_dur(items[0].seconds)} today")
        else:
            self.c_top.set_data("Nothing yet", "Use your computer and check back")

        nudges = s.event_count(today.isoformat(), "nudge")
        stopped = s.event_count(today.isoformat(), "stop")
        self.c_alerts.set_data(str(nudges), f"{stopped} stopped when asked" if nudges else "You are within your limits",
                               s.event_series(today, 7, "nudge"))

        hours = hrs
        self.chart.tips = [f"{h:02d}:00" for h in range(24)]
        self.chart.set_columns([(f"{h:02d}" if h % 3 == 0 else "", hours[h], h == now.hour) for h in range(24)])

        self.list_title.set_title(f"Where your time went  \u00b7  {'apps' if scope == 'apps' else 'websites'}")
        self.list.set_items(items[:8], force)
        self.update_status(getattr(self, "_last_snap", None))

    def update_status(self, snap: dict | None) -> None:
        if snap is None:
            return
        self._last_snap = snap
        st = snap["status"]
        if st == "paused":
            self.chip.set_state("Paused", "off")
        elif st == "idle":
            self.chip.set_state("Idle", "off")
        else:
            self.chip.set_state("Monitoring", "on")


# ======================================================================== ACTIVITY
class ActivityPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        self.mode = 0                          # 0 day, 1 week, 2 month
        self.anchor = date.today()
        self._back: tuple[int, date] | None = None
        v = scrolling_body(self)

        v.addWidget(mk_label("Activity", T.sans(32, T.QFont.Weight.Medium)))

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.mode_seg = Segmented(["Day", "Week", "Month"])
        self.prev_btn = PillButton("\u2039", "secondary", height=32)
        self.next_btn = PillButton("\u203a", "secondary", height=32)
        for b in (self.prev_btn, self.next_btn):
            b.setFixedWidth(38)
        self.period_lbl = mk_label("", T.sans(14, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignCenter)
        self.period_lbl.setMinimumWidth(190)
        self.today_btn = LinkButton("Today", size=13)
        self.back_btn = LinkButton("Back", size=13)
        self.scope_seg = Segmented(["Apps", "Websites"])
        bar.addWidget(self.mode_seg)
        bar.addSpacing(8)
        bar.addWidget(self.prev_btn)
        bar.addWidget(self.period_lbl)
        bar.addWidget(self.next_btn)
        bar.addWidget(self.today_btn)
        bar.addWidget(self.back_btn)
        bar.addStretch(1)
        bar.addWidget(self.scope_seg)
        v.addLayout(bar)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.c_total = StatCard("Total time")
        self.c_mid = StatCard("Daily average")
        self.c_top = StatCard("Most used")
        self.cards = (self.c_total, self.c_mid, self.c_top)
        for c in self.cards:
            cards.addWidget(c, 1)
        v.addLayout(cards)

        self.chart = BarChart()
        self.chart.setMinimumHeight(210)
        self.chart_title = SectionTitle("By hour")
        self.hint = mk_label("Click a bar to open that day", T.sans(12), T.GRAY)
        hint_row = QWidget()
        hl = QHBoxLayout(hint_row)
        hl.setContentsMargins(2, 0, 0, 0)
        hl.addWidget(self.hint)
        card = card_with(self.chart_title, self.chart)
        card.layout().addWidget(hint_row)
        v.addWidget(card)

        self.list_title = SectionTitle("Breakdown")
        self.list = ItemList("Nothing over a minute in this period.", *_hide_hooks(ctx, self))
        v.addWidget(card_with(self.list_title, self.list, margins=(12, 14, 12, 8)))
        v.addStretch(1)

        self.mode_seg.changed.connect(self._set_mode)
        self.scope_seg.changed.connect(lambda _: self.refresh(True))
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))
        self.today_btn.clicked.connect(self._go_today)
        self.back_btn.clicked.connect(self._go_back)
        self.chart.clicked.connect(self._open_day)

    # ---- navigation
    def _set_mode(self, i: int) -> None:
        self.mode, self._back = i, None
        self.refresh(True)

    def _step(self, steps: int) -> None:
        self.anchor = stats.shift(self.mode, self.anchor, steps)
        self._back = None
        self.refresh(True)

    def _go_today(self) -> None:
        self.anchor, self._back = date.today(), None
        self.refresh(True)

    def _open_day(self, index: int) -> None:
        """A bar in the week or month chart was clicked: open that day."""
        if self.mode == 0:
            return
        d0, _d1 = stats.period(self.mode, self.anchor)
        day = d0 + timedelta(days=index)
        if day > date.today():
            return
        self._back = (self.mode, self.anchor)
        self.mode, self.anchor = 0, day
        self.mode_seg.set_index(0)
        self.refresh(True)

    def _go_back(self) -> None:
        if self._back:
            self.mode, self.anchor = self._back
            self._back = None
            self.mode_seg.set_index(self.mode)
            self.refresh(True)

    def enter(self) -> None:
        for i, c in enumerate(self.cards):
            c.replay(i * 70)
        self.chart.replay()
        self.list.replay()

    # ---- data
    def refresh(self, force: bool = False) -> None:
        s = self.ctx.store
        self.ctx.engine.flush()
        today, now = date.today(), datetime.now()
        scope = SCOPES[self.scope_seg.index]
        d0, d1 = stats.period(self.mode, self.anchor)

        self.period_lbl.setText(stats.period_label(self.mode, self.anchor).title() if self.mode != 2 else d0.strftime("%B %Y"))
        self.next_btn.setEnabled(d1 < today)
        self.today_btn.setVisible(d0 > today or d1 < today)
        self.back_btn.setVisible(self._back is not None)
        if self._back:
            text = "\u2190 Back to " + ("week" if self._back[0] == 1 else "month")
            self.back_btn.setText(text)
            self.back_btn.setFixedWidth(QFontMetrics(T.sans(13)).horizontalAdvance(text) + 8)
        self.hint.setVisible(self.mode != 0)

        hidden = stats.hidden_pairs(self.ctx.cfg)
        items = stats.breakdown(s, d0.isoformat(), d1.isoformat(), scope, hidden)
        if self.mode == 0:
            hours, _sh = stats.hourly_scope(s, d0.isoformat(), scope, hidden)
            self.chart.tips = [f"{h:02d}:00" for h in range(24)]
            self.chart.clickable = False
            self.chart.set_columns([(f"{h:02d}" if h % 3 == 0 else "", hours[h], d0 == today and h == now.hour) for h in range(24)], force)
            total = sum(hours)
            self.chart_title.set_title("Activity by hour")
            self.c_mid.title = "Busiest hour"
            peak = max(range(24), key=lambda h: hours[h])
            self.c_mid.set_data(f"{peak:02d}:00" if total >= 60 else "\u2013", fmt_dur(hours[peak]) if total >= 60 else "No activity")
        else:
            tot, _shd = stats.daily_scope(s, d0, d1, scope, hidden)
            days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
            label = (lambda d: d.strftime("%a")) if self.mode == 1 else (lambda d: str(d.day) if d.day % 2 == 1 else "")
            self.chart.tips = [d.strftime("%a %d %b") for d in days]
            self.chart.clickable = True
            self.chart.set_columns([(label(d), tot.get(d.isoformat(), 0.0), d == today) for d in days], force)
            elapsed = [d for d in days if d <= today]
            total = sum(tot.get(d.isoformat(), 0.0) for d in elapsed)
            self.chart_title.set_title("Activity by day")
            self.c_mid.title = "Daily average"
            self.c_mid.set_data(fmt_dur(total / max(1, len(elapsed))) if total >= 60 else "0m", "per day")

        self.c_total.set_data(fmt_dur(total) if total >= 60 else "0m", stats.period_label(self.mode, self.anchor).title())
        noun = SCOPE_NOUN[scope]
        self.c_top.title = f"Most used {noun}"
        if items:
            self.c_top.set_data(items[0].label, fmt_dur(items[0].seconds))
        else:
            self.c_top.set_data("Nothing yet", "No " + noun + " over a minute")
        self.list_title.set_title("Breakdown")
        self.list.set_items(items[:12], force)
