"""Today (the overview) and Activity (the full history) screens.

Today answers "how am I doing right now": four totals, when it happened, how close each limit is,
and what took the time. Activity answers "where did my time go": day, week or month, with every
bar clickable to open that day hour by hour.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget)

from .. import stats
from ..stats import Item
from ..utils import fmt_dur, pretty_app, pretty_site
from . import theme as T
from .pages import Ctx, Page, caps, mk_label
from .widgets import (LimitBar, LinkButton, Panel, PillButton, PixelChart, Segmented, StatCard, StatusChip, Timeline,
                      UsageRow)


def scrolling_body(page: QWidget, margins=(30, 6, 30, 26), spacing: int = 16) -> QVBoxLayout:
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


class TopRow(QWidget):
    """Icon tile, name, caption and time. Fades in; red tile for Shorts."""

    def __init__(self, item: Item, delay: int = 0):
        super().__init__()
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 0, 6, 0)
        tile = QLabel(item.label[:1].upper())
        tile.setFixedSize(28, 28)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setFont(T.mono(12, T.QFont.Weight.Bold))
        bg, fg, bd = (T.RED, T.PAPER, T.RED) if item.red else (T.PAPER, T.INK, T.LINE)
        tile.setStyleSheet(f"background:{bg}; color:{fg}; border:1px solid {bd}; border-radius:8px;")
        lay.addWidget(tile)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(mk_label(item.label, T.sans(13, T.QFont.Weight.Medium)))
        col.addWidget(mk_label(item.tag, T.mono(8, spacing=1.0), T.GRAY))
        lay.addLayout(col, 1)
        self.time_lbl = mk_label(fmt_dur(item.seconds), T.mono(12, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignRight)
        lay.addWidget(self.time_lbl)
        self._text = self.time_lbl.text()
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.timeout.connect(self._fade_in)
        self.replay(delay)

    def set_secs(self, secs: float) -> None:
        text = fmt_dur(secs)
        if text != self._text:
            self._text = text
            self.time_lbl.setText(text)

    def replay(self, delay: int = 0) -> None:
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


class RowList(QWidget):
    """A short ranked list that reuses its rows when the ranking has not changed."""

    def __init__(self, empty_text: str):
        super().__init__()
        self.empty_text = empty_text
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._keys: list | None = None
        self._rows: list[TopRow] = []

    def set_items(self, items: list[Item]) -> None:
        keys = [(i.kind, i.key) for i in items]
        if keys == self._keys:
            for row, it in zip(self._rows, items):
                row.set_secs(it.seconds)
            return
        self._keys, self._rows = keys, []
        while self._lay.count():
            w = self._lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        if not items:
            self._lay.addWidget(mk_label(self.empty_text, T.mono(11), T.GRAY, Qt.AlignmentFlag.AlignCenter))
            return
        for i, it in enumerate(items):
            row = TopRow(it, delay=i * 70)
            self._rows.append(row)
            self._lay.addWidget(row)

    def replay(self) -> None:
        for i, row in enumerate(self._rows):
            row.replay(180 + i * 70)


# ======================================================================== TODAY
class TodayPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        v = scrolling_body(self)

        head = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)
        self.greet = mk_label("", T.sans(30, T.QFont.Weight.Medium))
        left.addWidget(self.greet)
        self.insight = mk_label("", T.mono(11, spacing=1.0), T.GRAY)
        left.addWidget(self.insight)
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
        self.c_total = StatCard("Screen time")
        self.c_apps = StatCard("Apps")
        self.c_sites = StatCard("Websites")
        self.c_shorts = StatCard("YouTube Shorts")
        self.cards = (self.c_total, self.c_apps, self.c_sites, self.c_shorts)
        for c in self.cards:
            cards.addWidget(c, 1)
        v.addLayout(cards)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        tl_panel = Panel(hoverable=False)
        tl = QVBoxLayout(tl_panel)
        tl.setContentsMargins(20, 16, 20, 12)
        tl.addWidget(caps("When it happened"))
        self.timeline = Timeline()
        self.timeline.setMinimumHeight(190)
        tl.addWidget(self.timeline, 1)
        mid.addWidget(tl_panel, 5)

        lim_panel = Panel(hoverable=False)
        self.lim_lay = QVBoxLayout(lim_panel)
        self.lim_lay.setContentsMargins(20, 16, 20, 12)
        self.lim_lay.setSpacing(4)
        self.lim_lay.addWidget(caps("Limits today"))
        self.lim_rows = QVBoxLayout()
        self.lim_rows.setSpacing(2)
        self.lim_lay.addLayout(self.lim_rows)
        self.lim_lay.addStretch(1)
        mid.addWidget(lim_panel, 3)
        v.addLayout(mid)

        lists = QHBoxLayout()
        lists.setSpacing(14)
        self.top_apps = RowList("No apps yet_")
        self.top_sites = RowList("No websites yet_")
        for title, widget in (("Top apps", self.top_apps), ("Top websites", self.top_sites)):
            panel = Panel(hoverable=False)
            pl = QVBoxLayout(panel)
            pl.setContentsMargins(14, 16, 14, 12)
            t = caps(title)
            t.setContentsMargins(6, 0, 0, 6)
            pl.addWidget(t)
            pl.addWidget(widget)
            pl.addStretch(1)
            lists.addWidget(panel, 1)
        v.addLayout(lists)
        self._lim_keys: list | None = None
        self._lim_widgets: list[LimitBar] = []

    def enter(self) -> None:
        for i, c in enumerate(self.cards):
            c.replay(i * 70)
        self.timeline.replay()
        self.top_apps.replay()
        self.top_sites.replay()

    # ---- data
    def _series7(self, kinds: tuple[str, ...], name: str | None = None) -> list[float]:
        today = date.today()
        got = self.ctx.store.daily_kind_range((today - timedelta(days=6)).isoformat(), today.isoformat(), kinds, name)
        return [got.get((today - timedelta(days=6 - i)).isoformat(), 0.0) for i in range(7)]

    @staticmethod
    def _delta(cur: float, prev: float):
        if prev < 60:
            return "", 0
        pct = round((cur - prev) / prev * 100)
        if pct == 0:
            return "SAME AS YDAY", 0
        return f"{abs(pct)}% VS YDAY", 1 if pct > 0 else -1

    def refresh(self) -> None:
        eng, s = self.ctx.engine, self.ctx.store
        eng.flush()
        now = datetime.now()
        today = date.today()
        yday = (today - timedelta(days=1)).isoformat()
        name = self.ctx.cfg.get("name").strip()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        self.greet.setText(f"Good {part}, {name}." if name else f"Good {part}.")
        self.date_lbl.setText(now.strftime("%a  ·  %b %d %Y").upper())

        total = eng.today_seconds("total", "*")
        apps = eng.today_sum("app")
        sites = eng.today_sum("site")
        shorts = eng.today_seconds("shorts", "youtube")
        swipes = int(eng.today_seconds("swipes", "shorts"))
        items = stats.breakdown(s, today.isoformat(), today.isoformat(), "all")
        app_items = [i for i in items if i.kind == "app"]
        site_items = [i for i in items if i.kind != "app"]

        def until(kinds):
            return sum(s.hourly_kinds(yday, kinds)[: now.hour + 1])

        d, dr = self._delta(total, s.total_until(yday, "total", "*", now.hour))
        self.c_total.set_data(total, fmt_dur, "SINCE MIDNIGHT", d, dr, False, self._series7(("total",), "*"))
        d, dr = self._delta(apps, until(("app",)))
        self.c_apps.set_data(apps, fmt_dur, f"{len(app_items)} APPS USED" if app_items else "NO APPS YET", d, dr, False, self._series7(("app",)))
        d, dr = self._delta(sites, until(("site",)))
        self.c_sites.set_data(sites, fmt_dur, f"{len(site_items)} WEBSITES" if site_items else "NO WEBSITES YET", d, dr, False, self._series7(("site",)))
        d, dr = self._delta(shorts, s.total_until(yday, "shorts", "youtube", now.hour))
        sub = f"{swipes} WATCHED" if swipes else "NONE TODAY" if shorts < 60 else "KEEP AN EYE"
        self.c_shorts.set_data(shorts, fmt_dur, sub, d, dr, dr > 0, self._series7(("shorts",), "youtube"))

        hours = s.hourly(today.isoformat(), "total", "*")
        if total >= 60 and items:
            peak = max(range(24), key=lambda h: hours[h])
            share = round(shorts / total * 100) if total else 0
            self.insight.setText(f"PEAK {peak:02d}:00  ·  TOP {items[0].label.upper()} {fmt_dur(items[0].seconds)}  ·  SHORTS {share}% OF YOUR TIME")
        else:
            self.insight.setText("STAY INTENTIONAL. YOUR TIME MATTERS.")

        self.timeline.set_rows([
            ("Apps", s.hourly_kinds(today.isoformat(), ("app",)), False),
            ("Websites", s.hourly_kinds(today.isoformat(), ("site",)), False),
            ("YouTube Shorts", s.hourly(today.isoformat(), "shorts", "youtube"), True),
        ] if total > 0 else [])

        self._sync_limits()
        self.top_apps.set_items(app_items[:5])
        self.top_sites.set_items(site_items[:5])
        self.update_status(getattr(self, "_last_snap", None))

    def _limit_entries(self) -> list[tuple[str, str, str, float, float]]:
        """(key, name, caption, used seconds, limit seconds) for every limit that is switched on."""
        cfg, eng = self.ctx.cfg, self.ctx.engine
        out = []
        daily = cfg.get("shorts_daily_min")
        if daily:
            out.append(("shorts", "YouTube Shorts", "WEBSITE · DAILY BUDGET", eng.today_seconds("shorts", "youtube"), daily * 60.0))
        for e in cfg.get("watched_sites"):
            if e.get("enabled") and e.get("limit"):
                label = "YouTube" if e["domain"] == "youtube.com" else pretty_site(e["domain"])
                tag = "WEBSITE · WITHOUT SHORTS · DAILY" if e["domain"] == "youtube.com" else "WEBSITE · DAILY"
                out.append(("site:" + e["domain"], label, tag, eng.site_used(e["domain"]), e["limit"] * 60.0))
        for e in cfg.get("watched_apps"):
            if e.get("enabled") and e.get("limit"):
                out.append(("app:" + e["exe"].lower(), pretty_app(e["exe"]), "APP · DAILY", eng.today_seconds("app", e["exe"].lower()), e["limit"] * 60.0))
        return out

    def _sync_limits(self) -> None:
        entries = self._limit_entries()
        keys = [(e[0], e[4]) for e in entries]
        if keys == self._lim_keys:
            for w, e in zip(self._lim_widgets, entries):
                w.set_values(e[3], e[4])
            return
        self._lim_keys, self._lim_widgets = keys, []
        while self.lim_rows.count():
            w = self.lim_rows.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        if not entries:
            msg = mk_label("No limits set.\nAdd daily limits for apps and websites in Settings.", T.sans(12), T.GRAY)
            msg.setWordWrap(True)
            self.lim_rows.addWidget(msg)
            return
        for _key, name, tag, used, limit in entries:
            bar = LimitBar(name, tag, used, limit)
            self._lim_widgets.append(bar)
            self.lim_rows.addWidget(bar)

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
        self.link_lbl.setText("BROWSER LINK ● ONLINE" if snap["link"] else "BROWSER LINK ○ OFFLINE")


# ======================================================================== ACTIVITY
class ActivityPage(Page):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        self.mode = 0                          # 0 day, 1 week, 2 month
        self.anchor = date.today()
        self._back: tuple[int, date] | None = None
        v = scrolling_body(self)

        v.addWidget(mk_label("Activity", T.sans(26, T.QFont.Weight.Medium)))
        v.addWidget(mk_label("Everything PHI measured. Pick a day, a week or a month, then click a bar to open that day.", T.sans(13), T.GRAY))

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.mode_seg = Segmented(["Day", "Week", "Month"])
        self.prev_btn = PillButton("‹", "secondary", height=32)
        self.next_btn = PillButton("›", "secondary", height=32)
        for b in (self.prev_btn, self.next_btn):
            b.setFixedWidth(40)
        self.period_lbl = mk_label("", T.mono(12, T.QFont.Weight.Medium, 1.0), T.INK, Qt.AlignmentFlag.AlignCenter)
        self.period_lbl.setMinimumWidth(190)
        self.today_btn = LinkButton("today", size=12)
        self.back_btn = LinkButton("← back", size=12)
        self.scope_seg = Segmented(["All", "Apps", "Websites"])
        bar.addWidget(self.mode_seg)
        bar.addSpacing(6)
        bar.addWidget(self.prev_btn)
        bar.addWidget(self.period_lbl)
        bar.addWidget(self.next_btn)
        bar.addWidget(self.today_btn)
        bar.addWidget(self.back_btn)
        bar.addStretch(1)
        bar.addWidget(self.scope_seg)
        v.addLayout(bar)

        self.summary = mk_label("", T.mono(11, spacing=.8), T.GRAY)
        v.addWidget(self.summary)

        chart_panel = Panel(hoverable=False)
        cl = QVBoxLayout(chart_panel)
        cl.setContentsMargins(20, 14, 20, 10)
        legend = QHBoxLayout()
        self.chart_title = caps("Active time")
        legend.addWidget(self.chart_title)
        legend.addStretch(1)
        legend.addWidget(mk_label("■ ACTIVE   ", T.mono(9, spacing=1), T.INK))
        legend.addWidget(mk_label("■ SHORTS", T.mono(9, spacing=1), T.RED))
        cl.addLayout(legend)
        self.chart = PixelChart()
        self.chart.setMinimumHeight(210)
        cl.addWidget(self.chart)
        v.addWidget(chart_panel)

        self.span_panel = Panel(hoverable=False)
        sl = QVBoxLayout(self.span_panel)
        sl.setContentsMargins(20, 14, 20, 12)
        sl.addWidget(caps("Hour by hour"))
        self.timeline = Timeline()
        sl.addWidget(self.timeline)
        v.addWidget(self.span_panel)

        list_panel = Panel(hoverable=False)
        ll = QVBoxLayout(list_panel)
        ll.setContentsMargins(10, 12, 10, 10)
        ll.setSpacing(0)
        self.list_title = caps("Breakdown")
        self.list_title.setContentsMargins(10, 0, 0, 4)
        ll.addWidget(self.list_title)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(0)
        ll.addLayout(self.rows)
        v.addWidget(list_panel)
        v.addStretch(1)

        self.mode_seg.changed.connect(self._set_mode)
        self.scope_seg.changed.connect(lambda _: self.refresh(True))
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))
        self.today_btn.clicked.connect(self._go_today)
        self.back_btn.clicked.connect(self._go_back)
        self.chart.clickable = True
        self.chart.clicked.connect(self._open_day)
        self._keys: list | None = None
        self._rows_w: list[UsageRow] = []

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
        """A bar in the week or month chart was clicked: open that day, hour by hour."""
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
        self.timeline.replay()
        for i, row in enumerate(self._rows_w):
            row.replay(60 + 40 * i)

    # ---- data
    def refresh(self, force: bool = False) -> None:
        s = self.ctx.store
        self.ctx.engine.flush()
        today = date.today()
        now = datetime.now()
        scope = stats.SCOPES[self.scope_seg.index]
        d0, d1 = stats.period(self.mode, self.anchor)

        self.period_lbl.setText(stats.period_label(self.mode, self.anchor))
        self.next_btn.setEnabled(d1 < today)
        self.today_btn.setVisible(d0 > today or d1 < today)
        self.back_btn.setVisible(self._back is not None)
        if self._back:
            text = "← back to " + ("week" if self._back[0] == 1 else "month")
            self.back_btn.setText(text)
            self.back_btn.setFixedWidth(QFontMetrics(T.sans(12)).horizontalAdvance(text) + 8)   # LinkButton sized itself once
        self.span_panel.setVisible(self.mode == 0)

        if self.mode == 0:
            total, sh = stats.hourly_scope(s, d0.isoformat(), scope)
            cols = [(f"{h:02d}" if h % 3 == 0 else "", total[h], sh[h], d0 == today and h == now.hour) for h in range(24)]
            self.chart.tips = [f"{h:02d}:00" for h in range(24)]
            self.chart.clickable = False
            self.chart_title.setText("ACTIVE TIME BY HOUR")
            self.summary.setText(f"TOTAL {fmt_dur(sum(total))}" + (f"  ·  SHORTS {fmt_dur(sum(sh))}" if sum(sh) >= 1 else "")
                                 + (f"  ·  PEAK {max(range(24), key=lambda h: total[h]):02d}:00" if sum(total) >= 60 else ""))
        else:
            tot, shd = stats.daily_scope(s, d0, d1, scope)
            days = [d0 + timedelta(days=i) for i in range((d1 - d0).days + 1)]
            label = (lambda d: d.strftime("%a").upper()) if self.mode == 1 else (lambda d: str(d.day))
            cols = [(label(d), tot.get(d.isoformat(), 0.0), shd.get(d.isoformat(), 0.0), d == today) for d in days]
            self.chart.tips = [d.strftime("%a %d %b").upper() for d in days]
            self.chart.clickable = True
            self.chart_title.setText("ACTIVE TIME BY DAY  ·  CLICK A BAR TO OPEN THE DAY")
            elapsed = [d for d in days if d <= today]
            tsum = sum(tot.get(d.isoformat(), 0.0) for d in elapsed)
            busiest = max(elapsed, key=lambda d: tot.get(d.isoformat(), 0.0)) if elapsed else None
            parts = [f"TOTAL {fmt_dur(tsum)}", f"AVG {fmt_dur(tsum / max(1, len(elapsed)))}/DAY"]
            if busiest and tot.get(busiest.isoformat(), 0.0) >= 60:
                parts.append(f"BUSIEST {busiest.strftime('%a %d %b').upper()} {fmt_dur(tot[busiest.isoformat()])}")
            ssum = sum(shd.values())
            if ssum >= 60:
                parts.append(f"SHORTS {fmt_dur(ssum)}")
            self.summary.setText("  ·  ".join(parts))
        self.chart.set_columns(cols, replay=force)

        items = stats.breakdown(s, d0.isoformat(), d1.isoformat(), scope)
        if self.mode == 0:
            top = items[:8]
            self.timeline.show_now = d0 == today
            self.timeline.setFixedHeight(max(150, 36 * max(3, len(top)) + 26))
            self.timeline.set_rows([(it.label, stats.hourly_for(s, d0.isoformat(), it), it.red) for it in top])
        self.list_title.setText(("BREAKDOWN  ·  " + stats.period_label(self.mode, self.anchor)))
        self._sync_rows(items, force)

    def _sync_rows(self, items: list[Item], force: bool) -> None:
        denom = max(sum(i.seconds for i in items if i.kind != "shorts") or sum(i.seconds for i in items), 1.0)
        keys = [(i.kind, i.key) for i in items]
        if keys == self._keys and not force:
            for row, it in zip(self._rows_w, items):
                row.set_values(it.seconds, min(1.0, it.seconds / denom))
            return
        self._keys, self._rows_w = keys, []
        while self.rows.count():
            w = self.rows.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        if not items:
            self.rows.addWidget(mk_label("Nothing recorded for this period_", T.mono(11), T.GRAY, Qt.AlignmentFlag.AlignCenter))
            return
        for idx, it in enumerate(items):
            row = UsageRow(it.label, it.tag, it.seconds, min(1.0, it.seconds / denom), it.red, 40 * (idx + 1))
            self._rows_w.append(row)
            self.rows.addWidget(row)
