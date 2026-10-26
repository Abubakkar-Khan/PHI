"""Today and Activity.

Swiss grid, numbered sections, a dot-matrix readout: the number first, then when it happened, then what took
the time. Apps come first; websites only when asked.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import stats
from ..stats import Item
from . import theme as T
from .pages import Ctx, Page, mk_label
from .widgets import DotChart, DotNumber, ItemRow, LinkButton, Panel, PillButton, SectionHead, Segmented, StatusChip

SCOPES = ("apps", "sites")           # the list switch: apps first, websites only when asked


def dot_dur(seconds: float) -> str:
    """5H 05M / 47M, for the dot-matrix display."""
    m = int(seconds // 60)
    h, m = divmod(m, 60)
    return f"{h}H {m:02d}M" if h else f"{m}M"


def scrolling_body(page: QWidget, margins=(40, 10, 40, 36), spacing: int = 18) -> QVBoxLayout:
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
    """A ranked list between two rules. Reuses its rows when the ranking is unchanged."""

    def __init__(self, empty_text: str):
        super().__init__()
        self.empty_text = empty_text
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.panel = Panel(hoverable=False)
        self._lay = QVBoxLayout(self.panel)
        self._lay.setContentsMargins(0, 1, 0, 1)
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
            msg = mk_label(self.empty_text, T.mono(11, spacing=1.0), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(96)
            self._lay.addWidget(msg)
            return
        for idx, it in enumerate(items):
            row = ItemRow(it.label, it.seconds, it.seconds / top, last=idx == len(items) - 1, delay=50 * idx, index=idx + 1)
            self._rows.append(row)
            self._lay.addWidget(row)

    def replay(self) -> None:
        for i, row in enumerate(self._rows):
            row.replay(80 + 50 * i)


# ======================================================================== TODAY
class TodayPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        v = scrolling_body(self)

        top = QHBoxLayout()
        self.date_lbl = mk_label("", T.mono(11, spacing=1.6), T.GRAY)
        top.addWidget(self.date_lbl, 1)
        self.chip = StatusChip()
        top.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignRight)
        v.addLayout(top)

        self.greet = mk_label("", T.sans(32, T.QFont.Weight.Medium))
        v.addWidget(self.greet)

        self.number = DotNumber("0M", dot=5.6)
        v.addWidget(self.number)
        self.caption = mk_label("ON THE COMPUTER TODAY", T.mono(11, spacing=1.6), T.GRAY)
        v.addWidget(self.caption)
        v.addSpacing(10)

        v.addWidget(SectionHead(1, "When"))
        self.chart = DotChart()
        self.chart.setMinimumHeight(170)
        v.addWidget(self.chart)
        v.addSpacing(8)

        self.kind_seg = Segmented(["Apps", "Websites"])
        v.addWidget(SectionHead(2, "What", self.kind_seg))
        self.list = ItemList("NOTHING OVER A MINUTE YET_")
        v.addWidget(self.list)
        v.addStretch(1)

        self.kind_seg.changed.connect(lambda _: self.refresh(True))

    def enter(self) -> None:
        self.number.replay()
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
        self.date_lbl.setText(now.strftime("%a  ·  %d %b %Y").upper())

        total = eng.today_seconds("total", "*")
        self.number.set_text(dot_dur(total))
        prev = s.total_until((today - timedelta(days=1)).isoformat(), "total", "*", now.hour)
        note = "ON THE COMPUTER TODAY"
        if prev >= 300 and total >= 60 and total < prev * 3:
            pct = round((total - prev) / prev * 100)
            if pct:
                note += f"  ·  {abs(pct)}% {'MORE' if pct > 0 else 'LESS'} THAN YESTERDAY SO FAR"
        self.caption.setText(note)

        hours = s.hourly(today.isoformat(), "total", "*")
        self.chart.tips = [f"{h:02d}:00" for h in range(24)]
        self.chart.set_columns([(f"{h:02d}" if h % 3 == 0 else "", hours[h], h == now.hour) for h in range(24)])

        scope = SCOPES[self.kind_seg.index]
        self.list.set_items(stats.breakdown(s, today.isoformat(), today.isoformat(), scope)[:8], force)
        self.update_status(getattr(self, "_last_snap", None))

    def update_status(self, snap: dict | None) -> None:
        if snap is None:
            return
        self._last_snap = snap
        st = snap["status"]
        if st == "paused":
            self.chip.set_state("PAUSED", "off")
        elif st == "idle":
            self.chip.set_state("IDLE", "off")
        else:
            self.chip.set_state("MONITORING", "on")


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
        self.period_lbl = mk_label("", T.mono(12, T.QFont.Weight.Medium, 1.0), T.INK, Qt.AlignmentFlag.AlignCenter)
        self.period_lbl.setMinimumWidth(190)
        self.today_btn = LinkButton("Today", size=12)
        self.back_btn = LinkButton("Back", size=12)
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
        v.addSpacing(6)

        self.number = DotNumber("0M", dot=5.0)
        v.addWidget(self.number)
        self.caption = mk_label("", T.mono(11, spacing=1.6), T.GRAY)
        v.addWidget(self.caption)
        v.addSpacing(10)

        self.chart_head = SectionHead(1, "By hour")
        v.addWidget(self.chart_head)
        self.chart = DotChart()
        self.chart.setMinimumHeight(190)
        v.addWidget(self.chart)
        self.hint = mk_label("CLICK A DOT COLUMN TO OPEN THAT DAY", T.mono(10, spacing=1.4), T.GRAY)
        v.addWidget(self.hint)
        v.addSpacing(8)

        v.addWidget(SectionHead(2, "Breakdown"))
        self.list = ItemList("NOTHING OVER A MINUTE IN THIS PERIOD_")
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
        """A column in the week or month chart was clicked: open that day."""
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
        self.number.replay()
        self.chart.replay()
        self.list.replay()

    # ---- data
    def refresh(self, force: bool = False) -> None:
        s = self.ctx.store
        self.ctx.engine.flush()
        today, now = date.today(), datetime.now()
        scope = SCOPES[self.scope_seg.index]
        d0, d1 = stats.period(self.mode, self.anchor)

        self.period_lbl.setText(stats.period_label(self.mode, self.anchor))
        self.next_btn.setEnabled(d1 < today)
        self.today_btn.setVisible(d0 > today or d1 < today)
        self.back_btn.setVisible(self._back is not None)
        if self._back:
            text = "\u2190 Back to " + ("week" if self._back[0] == 1 else "month")
            self.back_btn.setText(text)
            self.back_btn.setFixedWidth(QFontMetrics(T.sans(12)).horizontalAdvance(text) + 8)
        self.hint.setVisible(self.mode != 0)

        if self.mode == 0:
            hours, _sh = stats.hourly_scope(s, d0.isoformat(), scope)
            self.chart.tips = [f"{h:02d}:00" for h in range(24)]
            self.chart.clickable = False
            self.chart.set_columns([(f"{h:02d}" if h % 3 == 0 else "", hours[h], d0 == today and h == now.hour) for h in range(24)], force)
            total = sum(hours)
            self.caption.setText("IN TOTAL" if total < 60 else f"IN TOTAL  ·  BUSIEST AT {max(range(24), key=lambda h: hours[h]):02d}:00")
        else:
            tot, _shd = stats.daily_scope(s, d0, d1, scope)
            days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
            label = (lambda d: d.strftime("%a").upper()) if self.mode == 1 else (lambda d: str(d.day) if d.day % 2 == 1 else "")
            self.chart.tips = [d.strftime("%a %d %b").upper() for d in days]
            self.chart.clickable = True
            self.chart.set_columns([(label(d), tot.get(d.isoformat(), 0.0), d == today) for d in days], force)
            elapsed = [d for d in days if d <= today]
            total = sum(tot.get(d.isoformat(), 0.0) for d in elapsed)
            self.caption.setText(f"IN TOTAL  ·  {dot_dur(total / max(1, len(elapsed)))} A DAY ON AVERAGE")
        self.number.set_text(dot_dur(total))

        self.chart_head.set_title(("By hour", "By day", "By day")[self.mode])
        self.list.set_items(stats.breakdown(s, d0.isoformat(), d1.isoformat(), scope)[:12], force)
