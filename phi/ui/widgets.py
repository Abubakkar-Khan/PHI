"""Hand-painted controls and charts. Everything animates a little; nothing animates a lot."""
from __future__ import annotations

import math
from typing import Callable, Sequence

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QVBoxLayout, QWidget

from . import theme as T
from ..utils import fmt_dur


def animator(parent, cb: Callable[[float], None], dur: int = 300,
             ease: QEasingCurve.Type = QEasingCurve.Type.OutCubic) -> QVariantAnimation:
    a = QVariantAnimation(parent)
    a.setDuration(dur)
    a.setEasingCurve(ease)
    a.valueChanged.connect(lambda v: cb(float(v)))
    return a


def run(a: QVariantAnimation, start: float, end: float) -> None:
    a.stop()
    a.setStartValue(float(start))
    a.setEndValue(float(end))
    a.start()


def label_font_paint(p: QPainter, rect: QRectF, text: str, font, color, align=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter):
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(rect, int(align), text)


# ---------------------------------------------------------------- panels
class Panel(QWidget):
    """Rounded paper card with a hairline border that darkens slightly on hover."""

    def __init__(self, parent=None, radius: int = 14, fill: str = T.SURFACE, hoverable: bool = True):
        super().__init__(parent)
        self.radius, self.fill, self._hover = radius, fill, 0.0
        self._hoverable = hoverable
        self._anim = animator(self, self._set_hover, 180)

    def _set_hover(self, v: float):
        self._hover = v
        self.update()

    def enterEvent(self, e):
        if self._hoverable:
            run(self._anim, self._hover, 1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self._hoverable:
            run(self._anim, self._hover, 0)
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(T.mix(T.LINE, "#9d9b94", self._hover), 1))
        p.setBrush(QColor(self.fill))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), self.radius, self.radius)


class Hairline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _):
        QPainter(self).fillRect(self.rect(), QColor(T.LINE))


# ---------------------------------------------------------------- buttons
class PillButton(QAbstractButton):
    def __init__(self, text: str, variant: str = "primary", icon: str | None = None, height: int = 44, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.variant, self.icon_name, self._h = variant, icon, height
        self._hover = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = animator(self, self._set_hover, 160)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(height)

    def _set_hover(self, v):
        self._hover = v
        self.update()

    def sizeHint(self):
        fm = QFontMetrics(T.sans(13, T.QFont.Weight.Medium))
        w = fm.horizontalAdvance(self.text()) + 44 + (26 if self.icon_name else 0)
        return self.minimumSizeHint().expandedTo(QSize(w, self._h))

    def enterEvent(self, e):
        run(self._anim, self._hover, 1)

    def leaveEvent(self, e):
        run(self._anim, self._hover, 0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        if self.isDown():
            r.translate(0, 1)
        if self.variant == "primary":
            bg, fg, border = T.mix(T.INK, "#3b3b3b", self._hover), T.PAPER, None
        else:
            bg, fg = T.mix(T.PAPER, T.SOFT, self._hover), T.INK
            border = T.mix(T.LINE, T.INK, self._hover * .6)
        p.setBrush(bg)
        p.setPen(QPen(border, 1) if border else Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        font = T.sans(13, T.QFont.Weight.Medium)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(self.text())
        iw = 26 if self.icon_name else 0
        x = r.center().x() - (tw + iw) / 2
        cy = r.center().y()
        if self.icon_name:
            self._draw_icon(p, x + 7, cy, QColor(fg))
        p.setFont(font)
        p.setPen(QColor(fg))
        p.drawText(QRectF(x + iw, r.top(), tw + 4, r.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())

    def _draw_icon(self, p: QPainter, cx: float, cy: float, c: QColor):
        p.setPen(Qt.PenStyle.NoPen)
        if self.icon_name == "stop":
            p.setBrush(c)
            p.drawRect(QRectF(cx - 5, cy - 5, 10, 10))
        elif self.icon_name == "clock":
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(c, 1.4))
            p.drawEllipse(QPointF(cx, cy), 6.5, 6.5)
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy - 4))
            p.drawLine(QPointF(cx, cy), QPointF(cx + 3, cy + 1))
        elif self.icon_name == "plus":
            p.setPen(QPen(c, 1.6))
            p.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
            p.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5))


class LinkButton(QAbstractButton):
    def __init__(self, text: str, parent=None, size: int = 12):
        super().__init__(parent)
        self.setText(text)
        self._size, self._hover = size, 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = animator(self, self._set, 140)
        fm = QFontMetrics(T.sans(size))
        self.setFixedSize(fm.horizontalAdvance(text) + 4, fm.height() + 6)

    def _set(self, v):
        self._hover = v
        self.update()

    def enterEvent(self, e):
        run(self._anim, self._hover, 1)

    def leaveEvent(self, e):
        run(self._anim, self._hover, 0)

    def paintEvent(self, _):
        p = QPainter(self)
        f = T.sans(self._size)
        f.setUnderline(True)
        p.setFont(f)
        p.setPen(T.mix(T.GRAY, T.INK, self._hover))
        p.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self.text())


class Toggle(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = 1.0 if checked else 0.0
        self._anim = animator(self, self._set, 180, QEasingCurve.Type.OutBack)
        self.toggled.connect(lambda on: run(self._anim, self._t, 1.0 if on else 0.0))

    def _set(self, v):
        self._t = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = max(0.0, min(1.0, self._t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(T.mix("#CFCDC6", T.INK, t))
        p.drawRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        x = 3 + self._t * 18
        p.setBrush(QColor(T.PAPER))
        p.drawEllipse(QRectF(x, 3, 16, 16))
        if t > .9:  # tiny signal light when on
            p.setBrush(QColor(T.RED))
            p.drawEllipse(QPointF(x + 8, 11), 1.6, 1.6)


class Stepper(QWidget):
    changed = Signal(int)

    def __init__(self, value: int, lo: int, hi: int, step: int = 1, unit: str = "min", parent=None):
        super().__init__(parent)
        self.value, self.lo, self.hi, self.step, self.unit = value, lo, hi, step, unit
        self.setFixedSize(132, 30)
        self._hot = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setValue(self, v: int):
        self.value = max(self.lo, min(self.hi, v))
        self.update()

    def _zone(self, x: float) -> int:
        return 0 if x < 30 else (2 if x > self.width() - 30 else 1)

    def mouseMoveEvent(self, e):
        z = self._zone(e.position().x())
        if z != self._hot:
            self._hot = z
            self.update()

    def leaveEvent(self, e):
        self._hot = -1
        self.update()

    def mousePressEvent(self, e):
        z = self._zone(e.position().x())
        if z == 1:
            return
        nv = max(self.lo, min(self.hi, self.value + (-self.step if z == 0 else self.step)))
        if nv != self.value:
            self.value = nv
            self.update()
            self.changed.emit(nv)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(T.LINE), 1))
        p.setBrush(QColor(T.PAPER))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 8, 8)
        for zone, cx, sign in ((0, 15, -1), (2, self.width() - 15, 1)):
            on = self._hot == zone
            if on:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(T.SOFT))
                p.drawRoundedRect(QRectF(cx - 13, 3, 26, self.height() - 6), 6, 6)
            p.setPen(QPen(QColor(T.INK if on else T.GRAY), 1.5))
            p.drawLine(QPointF(cx - 4, 15), QPointF(cx + 4, 15))
            if sign > 0:
                p.drawLine(QPointF(cx, 11), QPointF(cx, 19))
        text = f"{self.value}" + (f" {self.unit}" if self.unit else "")
        label_font_paint(p, QRectF(30, 0, self.width() - 60, self.height()), text, T.mono(12), T.INK, Qt.AlignmentFlag.AlignCenter)


class Segmented(QWidget):
    changed = Signal(int)

    def __init__(self, options: Sequence[str], parent=None):
        super().__init__(parent)
        self.options, self.index = list(options), 0
        fm = QFontMetrics(T.mono(11, T.QFont.Weight.Medium, 0.8))
        self._w = [fm.horizontalAdvance(o.upper()) + 26 for o in self.options]
        self.setFixedSize(sum(self._w) + 6, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._x, self._wd = 3.0, float(self._w[0])
        self._anim = animator(self, self._move, 240)
        self._from = (3.0, float(self._w[0]))

    def _target(self, i: int):
        return 3.0 + sum(self._w[:i]), float(self._w[i])

    def _move(self, v: float):
        (x0, w0), (x1, w1) = self._from, self._target(self.index)
        self._x, self._wd = x0 + (x1 - x0) * v, w0 + (w1 - w0) * v
        self.update()

    def set_index(self, i: int, emit: bool = False):
        if i == self.index:
            return
        self._from = (self._x, self._wd)
        self.index = i
        run(self._anim, 0, 1)
        if emit:
            self.changed.emit(i)

    def mousePressEvent(self, e):
        x, acc = e.position().x() - 3, 0
        for i, w in enumerate(self._w):
            acc += w
            if x < acc:
                self.set_index(i, True)
                return

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(T.LINE), 1))
        p.setBrush(QColor(T.SURFACE))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 16, 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.INK))
        p.drawRoundedRect(QRectF(self._x, 3, self._wd, 26), 13, 13)
        x = 3.0
        for i, o in enumerate(self.options):
            sel = max(0.0, 1 - abs((x + self._w[i] / 2) - (self._x + self._wd / 2)) / (self._w[i] / 2 + 1))
            label_font_paint(p, QRectF(x, 0, self._w[i], 32), o.upper(), T.mono(11, T.QFont.Weight.Medium, 0.8),
                             T.mix(T.GRAY, T.PAPER, sel), Qt.AlignmentFlag.AlignCenter)
            x += self._w[i]


# ---------------------------------------------------------------- status
class StatusChip(QWidget):
    """Pulsing dot + mono label. modes: on (ping), alert (red), off (hollow)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text, self._mode, self._t = "STARTING", "on", 0.0
        self.setFixedHeight(20)
        self._anim = animator(self, self._pulse, 1800, QEasingCurve.Type.OutQuad)
        self._anim.setLoopCount(-1)
        run(self._anim, 0, 1)
        self._anim.setLoopCount(-1)

    def _pulse(self, v):
        self._t = v
        self.update()

    def set_state(self, text: str, mode: str):
        if (text, mode) != (self._text, self._mode):
            self._text, self._mode = text, mode
            fm = QFontMetrics(T.mono(10, spacing=1.2))
            self.setFixedWidth(fm.horizontalAdvance(text) + 26)
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(7, self.height() / 2)
        color = QColor(T.RED if self._mode == "alert" else T.INK)
        if self._mode == "off":
            p.setPen(QPen(QColor(T.GRAY), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 3, 3)
        else:
            ring = T.qc(color.name(), (1 - self._t) * .5)
            p.setPen(QPen(ring, 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 3 + self._t * 5, 3 + self._t * 5)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawEllipse(c, 3, 3)
        label_font_paint(p, QRectF(20, 0, self.width() - 20, self.height()), self._text, T.mono(10, spacing=1.2), T.GRAY)


# ---------------------------------------------------------------- stat card
class StatCard(Panel):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title, self._fmt = title, lambda v: f"{v:.0f}"
        self._value, self._shown = 0.0, 0.0
        self._sub, self._delta, self._bad, self._dir = "", "", False, 0
        self._series: list[float] = []
        self._grow = 1.0
        self.setMinimumHeight(122)
        self._count = animator(self, self._set_shown, 700)
        self._bars = animator(self, self._set_grow, 800)

    def _set_shown(self, v):
        self._shown = v
        self.update()

    def _set_grow(self, v):
        self._grow = v
        self.update()

    def set_data(self, value: float, fmt: Callable[[float], str], sub: str, delta: str, direction: int, bad: bool, series: list[float]):
        first = self._value != value or self._series != series
        self._fmt, self._sub, self._delta, self._dir, self._bad = fmt, sub, delta, direction, bad
        if first:
            run(self._count, self._shown, value)
            if self._series != series:
                run(self._bars, 0, 1)
        self._value, self._series = value, list(series)
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        label_font_paint(p, QRectF(20, 16, 200, 14), self.title.upper(), T.mono(10, spacing=1.4), T.GRAY)
        label_font_paint(p, QRectF(20, 36, 220, 44), self._fmt(self._shown), T.sans(32, T.QFont.Weight.Medium), T.INK)
        # delta with a drawn triangle
        y = self.height() - (40 if self._sub else 26)
        x = 20.0
        color = QColor(T.RED if self._bad else T.INK)
        if self._dir != 0:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            tri = QPainterPath()
            if self._dir > 0:
                tri.moveTo(x, y + 12); tri.lineTo(x + 8, y + 12); tri.lineTo(x + 8, y + 4)
            else:
                tri.moveTo(x, y + 4); tri.lineTo(x + 8, y + 12); tri.lineTo(x, y + 12)
            tri.closeSubpath()
            p.drawPath(tri)
            x += 14
        label_font_paint(p, QRectF(x, y, self.width() - x - 80, 16), self._delta, T.mono(10, T.QFont.Weight.Medium, .6), color)
        if self._sub:
            label_font_paint(p, QRectF(20, y + 17, self.width() - 100, 14), self._sub, T.mono(9, spacing=.6), T.GRAY)
        # 7-day pixel bars
        if self._series:
            mx = max(self._series) or 1.0
            bw, gap = 5, 3
            n = len(self._series)
            x0 = self.width() - 20 - n * (bw + gap) + gap
            base = self.height() - 22
            for i, v in enumerate(self._series):
                stagger = max(0.0, min(1.0, self._grow * (1 + n * .15) - i * .15))
                h = max(2.0, 38 * (v / mx) * stagger)
                last = i == n - 1
                col = QColor(T.RED if (last and self._bad) else T.INK) if last else QColor("#CBC9C2")
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(QRectF(x0 + i * (bw + gap), base - h, bw, h), 1.5, 1.5)


# ---------------------------------------------------------------- timeline
class Timeline(QWidget):
    """Rows x 24h dot-matrix. Each row: (label, [24 seconds], is_red)."""

    LABEL_W = 96

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[str, list[float], bool]] = []
        self._reveal = 1.0
        self._anim = animator(self, self._set, 900, QEasingCurve.Type.InOutCubic)
        self.setMinimumHeight(170)
        self._now = QTimer(self)
        self._now.timeout.connect(self.update)
        self._now.start(30000)

    def _set(self, v):
        self._reveal = v
        self.update()

    def set_rows(self, rows):
        changed = [r[1] for r in rows] != [r[1] for r in self.rows]
        self.rows = rows
        if changed:
            run(self._anim, 0, 1)
        self.update()

    def paintEvent(self, _):
        from datetime import datetime
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = max(1, len(self.rows))
        axis_h = 22
        row_h = (self.height() - axis_h) / max(n, 4)
        grid_x = self.LABEL_W
        cw = (self.width() - grid_x) / 24.0
        hour_now = datetime.now().hour
        # axis
        for h in range(0, 24, 3):
            txt = f"{h:02d}"
            label_font_paint(p, QRectF(grid_x + h * cw - 4, self.height() - axis_h + 6, cw * 3, 14), txt, T.mono(9, spacing=.6), T.GRAY)
        # now tick
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.RED))
        p.drawRoundedRect(QRectF(grid_x + hour_now * cw + cw / 2 - 3, self.height() - axis_h + 2, 6, 2), 1, 1)
        for ri, (name, hours, red) in enumerate(self.rows):
            y = ri * row_h
            label_font_paint(p, QRectF(0, y, self.LABEL_W - 8, row_h), name, T.sans(12), T.INK if not red else T.RED)
            mx = 1800.0  # half an hour of use fills a cell
            for h in range(24):
                visible = max(0.0, min(1.0, self._reveal * 28 - h))
                x = grid_x + h * cw
                rect = QRectF(x + 1.5, y + row_h * .22, cw - 3, row_h * .56)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#E9E7E1"))
                p.drawRoundedRect(rect, 2.5, 2.5)
                v = min(1.0, hours[h] / mx) * visible
                if v > 0.02:
                    base = T.RED if red else T.INK
                    p.setBrush(T.mix("#E9E7E1", base, .25 + .75 * v))
                    p.drawRoundedRect(rect, 2.5, 2.5)
        if not self.rows:
            label_font_paint(p, QRectF(0, 0, self.width(), self.height() - axis_h), "no activity logged yet_", T.mono(11), T.GRAY, Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------- bar chart
class PixelChart(QWidget):
    """Columns built from small squares: ink for active time, red for Shorts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cols: list[tuple[str, float, float, bool]] = []   # label, total_s, shorts_s, highlight
        self.unit_s = 600.0
        self._grow = 1.0
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(190)
        self._anim = animator(self, self._set, 900)

    def _set(self, v):
        self._grow = v
        self.update()

    def set_columns(self, cols, animate=True):
        changed = [c[1:3] for c in cols] != [c[1:3] for c in self.cols]
        self.cols = cols
        if changed and animate:
            run(self._anim, 0, 1)
        self.update()

    def _geom(self):
        n = max(1, len(self.cols))
        top, bottom = 22, 24
        return n, (self.width() / n), top, self.height() - bottom

    def mouseMoveEvent(self, e):
        n, cw, *_ = self._geom()
        i = int(e.position().x() // cw) if self.cols else -1
        i = i if 0 <= i < len(self.cols) else -1
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        n, cw, top, base = self._geom()
        mx = max([c[1] for c in self.cols] + [1.0])
        sq = 7 if cw > 22 else 5
        gap = 2
        max_cells = max(1, int((base - top) // (sq + gap)))
        sq_w = min(sq + 3, int(cw * .5))
        for i, (label, total, shorts, hi) in enumerate(self.cols):
            cells = int(round(max_cells * total / mx * self._grow))
            if total > 0:
                cells = max(1, cells)
            red_cells = int(round(cells * (shorts / total))) if total else 0
            if shorts > 0 and red_cells == 0 and cells:
                red_cells = 1
            x = i * cw + (cw - sq_w) / 2
            hovered = i == self._hover
            for k in range(cells):
                y = base - (k + 1) * (sq + gap) + gap
                is_red = k >= cells - red_cells
                if is_red:
                    col = QColor(T.RED)
                elif hi or hovered:
                    col = QColor(T.INK)
                else:
                    col = QColor("#2f2f2f") if hi else QColor("#B9B7B0")
                p.fillRect(QRectF(x, y, sq_w, sq), col)
            if total == 0:
                p.fillRect(QRectF(x, base - 2, sq_w, 2), QColor("#D9D7D0"))
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            label_font_paint(p, QRectF(i * cw, base + 6, cw, 14), label, T.mono(9, spacing=.4), T.INK if hi else T.GRAY, Qt.AlignmentFlag.AlignCenter)
            if hovered:
                txt = fmt_dur(total) + (f"  ·  {fmt_dur(shorts)} shorts" if shorts >= 60 else "")
                fm = QFontMetrics(T.mono(10, T.QFont.Weight.Medium))
                w = fm.horizontalAdvance(txt) + 16
                bx = max(0, min(self.width() - w, i * cw + cw / 2 - w / 2))
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(T.INK))
                p.drawRoundedRect(QRectF(bx, 0, w, 20), 6, 6)
                label_font_paint(p, QRectF(bx, 0, w, 20), txt, T.mono(10, T.QFont.Weight.Medium), T.PAPER, Qt.AlignmentFlag.AlignCenter)
                p.setRenderHint(QPainter.RenderHint.Antialiasing, False)


# ---------------------------------------------------------------- usage rows
class UsageRow(QWidget):
    def __init__(self, name: str, tag: str, seconds: float, share: float, red: bool = False, delay: int = 0, parent=None):
        super().__init__(parent)
        self.name, self.tag, self.seconds, self.share, self.red = name, tag, seconds, share, red
        self._fill, self._hover = 0.0, 0.0
        self.setFixedHeight(50)
        self._anim = animator(self, self._set_fill, 700)
        self._h = animator(self, self._set_hover, 150)
        QTimer.singleShot(delay, lambda: run(self._anim, 0, 1))

    def _set_fill(self, v):
        self._fill = v
        self.update()

    def _set_hover(self, v):
        self._hover = v
        self.update()

    def enterEvent(self, e):
        run(self._h, self._hover, 1)

    def leaveEvent(self, e):
        run(self._h, self._hover, 0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if self._hover > 0.01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.qc(T.SOFT, self._hover * .7))
            p.drawRoundedRect(QRectF(0, 2, w, h - 4), 10, 10)
        # monogram tile
        tile = QRectF(10, (h - 30) / 2, 30, 30)
        p.setPen(QPen(QColor(T.RED if self.red else T.LINE), 1))
        p.setBrush(QColor(T.RED if self.red else T.PAPER))
        p.drawRoundedRect(tile, 8, 8)
        label_font_paint(p, tile, self.name[:1].upper(), T.mono(13, T.QFont.Weight.Bold), T.PAPER if self.red else T.INK, Qt.AlignmentFlag.AlignCenter)
        label_font_paint(p, QRectF(52, 6, 220, 20), self.name, T.sans(13, T.QFont.Weight.Medium), T.INK)
        label_font_paint(p, QRectF(52, 25, 120, 16), self.tag.upper(), T.mono(9, spacing=1.2), T.GRAY)
        # dotted share bar
        bx, bw = 250, max(60, w - 250 - 150)
        n = int(bw // 7)
        lit = int(round(n * self.share * self._fill))
        for i in range(n):
            on = i < lit
            col = QColor(T.RED if (self.red and on) else (T.INK if on else "#DEDCD6"))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(bx + i * 7, h / 2 - 3, 4, 6), 1, 1)
        label_font_paint(p, QRectF(w - 130, 0, 70, h), fmt_dur(self.seconds), T.mono(12, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_font_paint(p, QRectF(w - 56, 0, 46, h), f"{round(self.share * 100)}%", T.mono(10), T.GRAY, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
