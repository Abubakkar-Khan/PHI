"""Today and Activity: two quiet screens.

Today is a glance: how long you have been on the computer, when, and what took the time (apps first;
websites when you ask). Activity is the same thing for any day, week or month.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import stats
from ..stats import Item
from ..utils import fmt_dur
from . import theme as T
from .pages import Ctx, Page, mk_label
from .widgets import BarChart, ItemRow, LinkButton, Panel, PillButton, Segmented, StatusChip

SCOPES = ("apps", "sites")           # the list switch: apps first, websites only when asked


def scrolling_body(page: QWidget, margins=(36, 8, 36, 32), spacing: int = 22) -> QVBoxLayout:
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
    """A ranked list in one soft panel. Reuses its rows when the ranking is unchanged."""

    def __init__(self, empty_text: str):
        super().__init__()
        self.empty_text = empty_text
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.panel = Panel(hoverable=False)
        self._lay = QVBoxLayout(self.panel)
        self._lay.setContentsMargins(0, 6, 0, 6)
        self._lay.setSpacing(0)
        outer.addWidget(self.panel)
        self._keys: list | None = None
        self._rows: list[ItemRow] = []

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
            msg = mk_label(self.empty_text, T.sans(13), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(90)
            self._lay.addWidget(msg)
            return
        for idx, it in enumerate(items):
            row = ItemRow(it.label, it.seconds, it.seconds / top, last=idx == len(items) - 1, delay=40 * idx)
            self._rows.append(row)
            self._lay.addWidget(row)

    def replay(self) -> None:
        for i, row in enumerate(self._rows):
            row.replay(60 + 40 * i)


# ======================================================================== TODAY
class TodayPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        v = scrolling_body(self)

        head = QHBoxLayout()
        self.greet = mk_label("", T.sans(28, T.QFont.Weight.Medium))
        head.addWidget(self.greet, 1)
        self.chip = StatusChip()
        head.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        v.addLayout(head)

        big = QVBoxLayout()
        big.setSpacing(2)
        self.total_lbl = mk_label("0m", T.sans(60, T.QFont.Weight.Medium))
        self.caption = mk_label("on the computer today", T.sans(14), T.GRAY)
        big.addWidget(self.total_lbl)
        big.addWidget(self.caption)
        v.addLayout(big)

        self.chart = BarChart()
        self.chart.setMinimumHeight(160)
        v.addWidget(self.chart)

        bar = QHBoxLayout()
        self.kind_seg = Segmented(["Apps", "Websites"])
        bar.addWidget(self.kind_seg)
        bar.addStretch(1)
        v.addLayout(bar)

        self.list = ItemList("Nothing over a minute yet.")
        v.addWidget(self.list)
        v.addStretch(1)

        self.kind_seg.changed.connect(lambda _: self.refresh(True))

    def enter(self) -> None:
        self.chart.replay()
        self.list.replay()

    def refresh(self, force: bool = False) -> None:
        eng, s = self.ctx.engine, self.ctx.store
        eng.flush()
        now = datetime.now()
        today = date.today()
        name = self.ctx.cfg.get("name").strip()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        self.greet.setText(f"Good {part}, {name}." if name else f"Good {part}.")

        total = eng.today_seconds("total", "*")
        self.total_lbl.setText(fmt_dur(total))
        prev = s.total_until((today - timedelta(days=1)).isoformat(), "total", "*", now.hour)
        note = "on the computer today"
        if prev >= 300 and total >= 60 and total < prev * 3:
            pct = round((total - prev) / prev * 100)
            if pct:
                note += f"  ·  {abs(pct)}% {'more' if pct > 0 else 'less'} than yesterday so far"
        self.caption.setText(note)

        hours = s.hourly(today.isoformat(), "total", "*")
        self.chart.tips = [f"{h:02d}:00" for h in range(24)]
        self.chart.set_columns([(f"{h:02d}" if h % 6 == 0 else "", hours[h], h == now.hour) for h in range(24)])

        scope = SCOPES[self.kind_seg.index]
        items = stats.breakdown(s, today.isoformat(), today.isoformat(), scope)[:8]
        self.list.set_items(items, force)
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

        v.addWidget(mk_label("Activity", T.sans(28, T.QFont.Weight.Medium)))

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.mode_seg = Segmented(["Day", "Week", "Month"])
        self.prev_btn = PillButton("\u2039", "secondary", height=32)
        self.next_btn = PillButton("\u203a", "secondary", height=32)
        for b in (self.prev_btn, self.next_btn):
            b.setFixedWidth(38)
        self.period_lbl = mk_label("", T.sans(14, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignCenter)
        self.period_lbl.setMinimumWidth(170)
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

        big = QVBoxLayout()
        big.setSpacing(2)
        self.total_lbl = mk_label("0m", T.sans(48, T.QFont.Weight.Medium))
        self.caption = mk_label("", T.sans(14), T.GRAY)
        big.addWidget(self.total_lbl)
        big.addWidget(self.caption)
        v.addLayout(big)

        self.chart = BarChart()
        self.chart.setMinimumHeight(200)
        v.addWidget(self.chart)
        self.hint = mk_label("Click a bar to see that day.", T.sans(12), T.GRAY)
        v.addWidget(self.hint)

        self.list = ItemList("Nothing over a minute in this period.")
        v.addWidget(self.list)
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

        if self.mode == 0:
            hours, _sh = stats.hourly_scope(s, d0.isoformat(), scope)
            self.chart.tips = [f"{h:02d}:00" for h in range(24)]
            self.chart.clickable = False
            self.chart.set_columns([(f"{h:02d}" if h % 6 == 0 else "", hours[h], d0 == today and h == now.hour) for h in range(24)], force)
            total = sum(hours)
            self.total_lbl.setText(fmt_dur(total))
            self.caption.setText("in total" if total < 60 else f"in total  \u00b7  busiest at {max(range(24), key=lambda h: hours[h]):02d}:00")
        else:
            tot, _shd = stats.daily_scope(s, d0, d1, scope)
            days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
            label = (lambda d: d.strftime("%a")) if self.mode == 1 else (lambda d: str(d.day) if d.day % 2 == 1 else "")
            self.chart.tips = [d.strftime("%a %d %b") for d in days]
            self.chart.clickable = True
            self.chart.set_columns([(label(d), tot.get(d.isoformat(), 0.0), d == today) for d in days], force)
            elapsed = [d for d in days if d <= today]
            tsum = sum(tot.get(d.isoformat(), 0.0) for d in elapsed)
            self.total_lbl.setText(fmt_dur(tsum))
            self.caption.setText(f"in total  \u00b7  {fmt_dur(tsum / max(1, len(elapsed)))} a day on average")

        items = stats.breakdown(s, d0.isoformat(), d1.isoformat(), scope)[:12]
        self.list.set_items(items, force)
