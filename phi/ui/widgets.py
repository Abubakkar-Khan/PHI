"""Hand-painted controls and charts. Everything animates a little; nothing animates a lot.

Two rules keep the UI smooth:
- Data updates tween (numbers count, bars slide) instead of replaying their intro animation.
- Per-frame work lives in Tickers that sleep the moment a widget settles or is hidden.
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

from PySide6.QtCore import QEasingCurve, QPointF, QRect, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QVBoxLayout, QWidget

from . import theme as T
from .motion import Spring, Ticker, burst, clamp
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


def _lerp_list(a: Sequence[float], b: Sequence[float], t: float) -> list[float]:
    return [x + (y - x) * t for x, y in zip(a, b)]


# ---------------------------------------------------------------- panels
class Panel(QWidget):
    """A block of rows between two hairline rules."""

    def __init__(self, parent=None, radius: int = 14, fill: str | None = None, hoverable: bool = True):
        super().__init__(parent)
        self.radius, self.fill, self._hover = radius, fill or T.SURFACE, 0.0
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
        line = T.mix(T.LINE, T.GRAY, self._hover * 0.5)
        p.fillRect(QRectF(0, 0, self.width(), 1), line)
        p.fillRect(QRectF(0, self.height() - 1, self.width(), 1), line)


class Hairline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _):
        QPainter(self).fillRect(self.rect(), QColor(T.LINE))


# ---------------------------------------------------------------- buttons
class PillButton(QAbstractButton):
    """Squashes under the finger, springs back, and pops a few pixels when it fires."""

    def __init__(self, text: str, variant: str = "primary", icon: str | None = None, height: int = 44, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.variant, self.icon_name, self._h = variant, icon, height
        self._hover = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = animator(self, self._set_hover, 160)
        self._press = Spring(0.0, 420.0, 21.0)
        self._tk = Ticker(self._step)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(height)

    def _set_hover(self, v):
        self._hover = v
        self.update()

    def _step(self, dt: float) -> bool:
        self._press.target = 1.0 if self.isDown() else 0.0
        self._press.step(dt)
        self.update()
        return self.isVisible() and not (self._press.resting and not self.isDown())

    def sizeHint(self):
        fm = QFontMetrics(T.sans(13, T.QFont.Weight.Medium))
        w = fm.horizontalAdvance(self.text()) + 44 + (26 if self.icon_name else 0)
        return self.minimumSizeHint().expandedTo(QSize(w, self._h))

    def enterEvent(self, e):
        run(self._anim, self._hover, 1)

    def leaveEvent(self, e):
        run(self._anim, self._hover, 0)

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self._tk.wake()

    def mouseReleaseEvent(self, e):
        fires = self.isDown() and self.rect().contains(e.position().toPoint())
        if fires:                                   # before clicked() runs: a handler may close this window
            burst(self, "pop", e.position(), [T.INK, T.ORANGE] if self.variant == "primary" else [T.INK, T.BAR], 0.7)
        super().mouseReleaseEvent(e)
        self._tk.wake()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        press = clamp(self._press.x, -0.3, 1.2)
        c = r.center()
        p.translate(c.x(), c.y() - self._hover * 0.8 + press * 0.8)
        p.scale(1.0 - 0.035 * press, 1.0 - 0.035 * press)
        p.translate(-c.x(), -c.y())
        if self.variant == "primary":
            bg, fg, border = T.mix(T.INK, T.GRAY, self._hover * .3), T.PAPER, None
        else:
            bg, fg = T.mix(T.PAPER, T.SOFT, self._hover), T.INK
            border = T.mix(T.LINE, T.INK, self._hover * .6)
        if not self.isEnabled():
            bg, fg, border = T.mix(bg, T.SOFT, .6), T.mix(fg, T.GRAY, .7), QColor(T.LINE)
        p.setBrush(bg)
        p.setPen(QPen(border, 1) if border else Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

        font = T.mono(12)
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
    """The knob is on a spring: it overshoots, stretches while it travels, and sparks when switched on."""

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(40, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._k = Spring(1.0 if checked else 0.0, 330.0, 19.0)
        self._tk = Ticker(self._step)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, on: bool):
        self._k.target = 1.0 if on else 0.0
        self._tk.wake()
        if on:
            burst(self, "pop", QPointF(self.width() - 11, 11), [T.INK, T.ORANGE], 0.55)

    def _step(self, dt: float) -> bool:
        self._k.step(dt)
        self.update()
        return self.isVisible() and not self._k.resting

    def showEvent(self, e):
        self._k.snap(1.0 if self.isChecked() else 0.0)
        super().showEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = clamp(self._k.x)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(T.mix(T.EDGE, T.INK, t))
        p.drawRoundedRect(QRectF(0, 0, 40, 22), 11, 11)
        stretch = min(5.0, abs(self._k.v) * 0.8)
        w = 16.0 + stretch
        x = clamp(3 + self._k.x * 18 - stretch / 2, 2.0, 38.0 - w)
        p.setBrush(QColor(T.PAPER))
        p.drawRoundedRect(QRectF(x, 3, w, 16), 8, 8)
        if t > .9:                                    # the little signal light
            p.setBrush(QColor(T.RED))
            p.drawEllipse(QPointF(x + w / 2, 11), 1.7, 1.7)


class Stepper(QWidget):
    """- / + control. The number rolls up or down as it changes, and each press pops a spark."""
    changed = Signal(int)

    def __init__(self, value: int, lo: int, hi: int, step: int = 1, unit: str = "min", parent=None):
        super().__init__(parent)
        self.value, self.lo, self.hi, self.step, self.unit = value, lo, hi, step, unit
        self.setFixedSize(132, 30)
        self._hot, self._down = -1, -1
        self._roll = animator(self, self._set_roll, 230, QEasingCurve.Type.OutCubic)
        self._rk, self._prev, self._dir = 1.0, "", 0
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _text(self, v: int) -> str:
        return f"{v}" + (f" {self.unit}" if self.unit else "")

    def _set_roll(self, v: float):
        self._rk = v
        self.update()

    def setValue(self, v: int):
        self.value = max(self.lo, min(self.hi, v))
        self._rk = 1.0
        self.update()

    def _zone(self, x: float) -> int:
        return 0 if x < 30 else (2 if x > self.width() - 30 else 1)

    def mouseMoveEvent(self, e):
        z = self._zone(e.position().x())
        if z != self._hot:
            self._hot = z
            self.update()

    def leaveEvent(self, e):
        self._hot = self._down = -1
        self.update()

    def mouseReleaseEvent(self, e):
        self._down = -1
        self.update()

    def mousePressEvent(self, e):
        z = self._zone(e.position().x())
        if z == 1:
            return
        self._down = z
        nv = max(self.lo, min(self.hi, self.value + (-self.step if z == 0 else self.step)))
        if nv != self.value:
            self._prev, self._dir = self._text(self.value), (1 if nv > self.value else -1)
            self.value = nv
            run(self._roll, 0, 1)
            cx = 15 if z == 0 else self.width() - 15
            burst(self, "pop", QPointF(cx, 15), [T.INK, T.ORANGE], 0.4)
            self.changed.emit(nv)
        self.update()

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
                p.setBrush(QColor(T.LINE) if self._down == zone else QColor(T.SOFT))
                p.drawRoundedRect(QRectF(cx - 13, 3, 26, self.height() - 6), 6, 6)
            p.setPen(QPen(QColor(T.INK if on else T.GRAY), 1.5))
            p.drawLine(QPointF(cx - 4, 15), QPointF(cx + 4, 15))
            if sign > 0:
                p.drawLine(QPointF(cx, 11), QPointF(cx, 19))
        box = QRectF(30, 0, self.width() - 60, self.height())
        font = T.sans(13, T.QFont.Weight.Medium)
        if self._rk >= 1.0 or not self._prev:
            label_font_paint(p, box, self._text(self.value), font, T.INK, Qt.AlignmentFlag.AlignCenter)
            return
        p.setClipRect(box)                              # old number leaves, new one arrives from the other side
        k, d = self._rk, self._dir
        label_font_paint(p, box.translated(0, -d * k * 13), self._prev, font, T.qc(T.INK, 1.0 - k), Qt.AlignmentFlag.AlignCenter)
        label_font_paint(p, box.translated(0, d * (1.0 - k) * 13), self._text(self.value), font, T.qc(T.INK, k), Qt.AlignmentFlag.AlignCenter)


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
        self._anim = animator(self, self._move, 300)
        curve = QEasingCurve(QEasingCurve.Type.OutBack)  # the highlight slides a hair past, then settles
        curve.setOvershoot(0.9)
        self._anim.setEasingCurve(curve)
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
            sel = clamp(1 - abs((x + self._w[i] / 2) - (self._x + self._wd / 2)) / (self._w[i] / 2 + 1))
            label_font_paint(p, QRectF(x, 0, self._w[i], 32), o.upper(), T.mono(11, T.QFont.Weight.Medium, 0.8),
                             T.mix(T.GRAY, T.PAPER, sel), Qt.AlignmentFlag.AlignCenter)
            x += self._w[i]


# ---------------------------------------------------------------- status
class StatusChip(QWidget):
    """Pulsing dot + mono label. modes: on (ping), alert (red), off (hollow). Sleeps when off or hidden."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._text, self._mode, self._t, self._ph = "Starting", "on", 0.0, 0.0
        self.setFixedHeight(20)
        self._tk = Ticker(self._step)

    def _step(self, dt: float) -> bool:
        if self._mode == "off" or not self.isVisible():
            return False
        self._ph = (self._ph + dt / 1.8) % 1.0
        self._t = 1.0 - (1.0 - self._ph) ** 2
        self.update(0, 0, 20, self.height())          # only the dot and its ring
        return True

    def showEvent(self, e):
        self._tk.wake()
        super().showEvent(e)

    def hideEvent(self, e):
        self._tk.sleep()
        super().hideEvent(e)

    def set_state(self, text: str, mode: str):
        if (text, mode) != (self._text, self._mode):
            self._text, self._mode = text, mode
            fm = QFontMetrics(T.mono(10, spacing=1.2))
            self.setFixedWidth(fm.horizontalAdvance(text) + 26)
            if mode != "off" and self.isVisible():
                self._tk.wake()
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


# ---------------------------------------------------------------- dot-matrix display
_GLYPHS = {
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "11110", "00001", "00001", "10001", "01110"],
    "6": ["00110", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "01100"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    ":": ["0", "1", "0", "0", "0", "1", "0"],
    "-": ["000", "000", "000", "111", "000", "000", "000"],
    " ": ["000"] * 7,
    "_": ["00000"] * 6 + ["11111"],
}


class DotNumber(QWidget):
    """A number on a dot-matrix display. New text scans in from the left; a red cursor blinks after it."""

    def __init__(self, text: str = "", dot: float = 5.0, cursor: bool = True, parent=None):
        super().__init__(parent)
        self._dot, self._cursor = dot, cursor
        self._text = ""
        self._cells: list[tuple[int, int, bool]] = []     # (col, row, lit)
        self._cols = 1
        self._reveal = 1.0
        self._on = True
        self._anim = animator(self, self._set_reveal, 800, QEasingCurve.Type.InOutCubic)
        self._blink = QTimer(self)
        self._blink.setInterval(560)
        self._blink.timeout.connect(self._toggle)
        self.set_text(text)

    def _toggle(self):
        self._on = not self._on
        self.update()

    def _set_reveal(self, v):
        self._reveal = v
        self.update()

    def showEvent(self, e):
        if self._cursor:
            self._blink.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._blink.stop()
        super().hideEvent(e)

    def set_text(self, text: str, animate: bool = True) -> None:
        text = text.upper()
        if text == self._text:
            return
        self._text = text
        cells, col = [], 0
        for ch in text:
            g = _GLYPHS.get(ch, _GLYPHS[" "])
            for r, row in enumerate(g):
                for c, v in enumerate(row):
                    cells.append((col + c, r, v == "1"))
            col += len(g[0]) + 1
        self._cells = cells
        self._cols = max(1, col)
        step = self._dot * 2.1
        self.setFixedSize(int((self._cols + (6 if self._cursor else 0)) * step), int(7 * step))
        if animate:
            run(self._anim, 0, 1)
        else:
            self._reveal = 1.0
        self.update()

    def replay(self) -> None:
        run(self._anim, 0, 1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        step, rad = self._dot * 2.1, self._dot * 0.5
        edge = self._reveal * (self._cols + 3)
        for c, r, lit in self._cells:
            x, y = c * step + step / 2, r * step + step / 2
            if lit and c <= edge:
                p.setBrush(QColor(T.INK))
                near = edge - c
                size = rad * (1.0 if near > 2 else 0.55 + near * 0.22)
            else:
                p.setBrush(QColor(T.CELL))
                size = rad * 0.55
            p.drawEllipse(QPointF(x, y), size, size)
        if self._cursor and self._on:
            p.setBrush(QColor(T.RED))
            x0 = (self._cols + 0.5) * step
            for c in range(5):
                p.drawEllipse(QPointF(x0 + c * step + step / 2, 6 * step + step / 2), rad, rad)


class DotChart(QWidget):
    """Columns built from dots. Dark on hover, a red dot crowns the current one, clicking can open it."""
    clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cols: list[tuple[str, float, bool]] = []      # label, seconds, highlight
        self.tips: list[str] = []
        self.clickable = False
        self._hover = -1
        self._grow = 1.0
        self._anim = animator(self, self._set_grow, 900, QEasingCurve.Type.OutCubic)
        self.setMouseTracking(True)
        self.setMinimumHeight(170)

    def _set_grow(self, v):
        self._grow = v
        self.update()

    def set_columns(self, cols, replay: bool = False) -> None:
        fresh = replay or [c[0] for c in cols] != [c[0] for c in self.cols] or len(cols) != len(self.cols)
        self.cols = list(cols)
        if fresh:
            run(self._anim, 0, 1)
        self.update()

    def replay(self) -> None:
        run(self._anim, 0, 1)

    def _slot(self) -> float:
        return self.width() / max(1, len(self.cols))

    def mouseMoveEvent(self, e):
        i = int(e.position().x() // self._slot()) if self.cols else -1
        i = i if 0 <= i < len(self.cols) else -1
        if i != self._hover:
            self._hover = i
            self.setCursor(Qt.CursorShape.PointingHandCursor if (self.clickable and i >= 0) else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mouseReleaseEvent(self, e):
        if self.clickable and 0 <= self._hover < len(self.cols):
            self.clicked.emit(self._hover)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        slot = self._slot()
        label_h, top = 22, 28
        base = self.height() - label_h
        d = max(4.0, min(slot * 0.30, 8.0))              # dot diameter
        gap = d * 0.62
        step = d + gap
        max_dots = max(1, int((base - top) // step))
        mx = max([c[1] for c in self.cols] + [1.0])
        per_row = 2 if slot >= 20 else 1
        p.setPen(Qt.PenStyle.NoPen)
        for i, (label, secs, hi) in enumerate(self.cols):
            n = int(round(max_dots * secs / mx)) if secs > 0 else 0
            if secs > 0:
                n = max(1, n)
            shown = int(n * clamp(self._grow * 1.25 - i * 0.012))
            x0 = i * slot + (slot - (per_row * d + (per_row - 1) * gap)) / 2
            on = i == self._hover
            p.setPen(Qt.PenStyle.NoPen)                    # the label text below leaves its pen active
            for k in range(max(shown, 0)):
                y = base - d - k * step
                top_dot = k == n - 1
                col = QColor(T.INK) if (hi or on) else QColor(T.BAR)
                if hi and top_dot:
                    col = QColor(T.RED)
                p.setBrush(col)
                for c in range(per_row):
                    p.drawEllipse(QRectF(x0 + c * step, y, d, d))
            if n == 0:
                p.setBrush(QColor(T.CELL))
                for c in range(per_row):
                    p.drawEllipse(QRectF(x0 + c * step, base - d, d, d))
            if label:
                label_font_paint(p, QRectF(i * slot - 8, base + 6, slot + 16, 14), label, T.mono(9, spacing=.6),
                                 T.INK if hi else T.GRAY, Qt.AlignmentFlag.AlignCenter)
        if 0 <= self._hover < len(self.cols):
            i = self._hover
            tip = f"{self.tips[i]}  \u00b7  " if i < len(self.tips) and self.tips[i] else ""
            txt = tip + fmt_dur(self.cols[i][1])
            font = T.mono(10, T.QFont.Weight.Medium)
            w = QFontMetrics(font).horizontalAdvance(txt) + 18
            bx = clamp(i * slot + slot / 2 - w / 2, 0.0, self.width() - w)
            p.setBrush(QColor(T.INK))
            p.drawRoundedRect(QRectF(bx, 0, w, 22), 8, 8)
            label_font_paint(p, QRectF(bx, 0, w, 22), txt, font, T.PAPER, Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------- list row
class ItemRow(QWidget):
    """01  Name  ...dots...  1h 07m. The dots show the share; the last lit one is red."""

    def __init__(self, name: str, seconds: float, share: float, last: bool = False, delay: int = 0, index: int = 1, parent=None):
        super().__init__(parent)
        self.name, self.seconds, self.share, self.last, self.index = name, seconds, share, last, index
        self._from = (seconds, share)
        self._u, self._fill, self._hover = 1.0, 0.0, 0.0
        self.setFixedHeight(54)
        self._anim = animator(self, self._set_fill, 800, QEasingCurve.Type.OutCubic)
        self._upd = animator(self, self._set_u, 420)
        self._h = animator(self, self._set_hover, 140)
        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.timeout.connect(lambda: run(self._anim, 0, 1))
        self._delay.start(max(0, delay))

    def _set_fill(self, v):
        self._fill = v
        self.update()

    def _set_u(self, v):
        self._u = v
        self.update()

    def _set_hover(self, v):
        self._hover = v
        self.update()

    def replay(self, delay: int = 0) -> None:
        self._anim.stop()
        self._fill = 0.0
        self.update()
        self._delay.start(max(0, delay))

    def shown(self) -> tuple[float, float]:
        if self._u >= 1.0:
            return self.seconds, self.share
        return (self._from[0] + (self.seconds - self._from[0]) * self._u,
                self._from[1] + (self.share - self._from[1]) * self._u)

    def set_values(self, seconds: float, share: float) -> None:
        if (seconds, share) == (self.seconds, self.share):
            return
        self._from = self.shown()
        self.seconds, self.share, self._u = seconds, share, 0.0
        run(self._upd, 0, 1)

    def enterEvent(self, e):
        run(self._h, self._hover, 1)

    def leaveEvent(self, e):
        run(self._h, self._hover, 0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        seconds, share = self.shown()
        label_font_paint(p, QRectF(0, 0, 40, h), f"{self.index:02d}", T.mono(11, T.QFont.Weight.Medium),
                         T.mix(T.GRAY, T.RED, self._hover), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label_font_paint(p, QRectF(44, 0, w * 0.34, h), self.name, T.sans(16, T.QFont.Weight.Medium), T.INK)
        x0, x1 = 44 + w * 0.34 + 10, w - 130
        n = max(8, int((x1 - x0) // 9))
        lit = int(round(n * clamp(share) * self._fill))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            if i < lit:
                p.setBrush(QColor(T.RED if i == lit - 1 else T.INK))
                r = 2.6
            else:
                p.setBrush(QColor(T.CELL))
                r = 1.8
            p.drawEllipse(QPointF(x0 + i * ((x1 - x0) / n) + 3, h / 2), r, r)
        label_font_paint(p, QRectF(w - 120, 0, 120, h), fmt_dur(seconds), T.mono(14, T.QFont.Weight.Medium), T.INK,
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if not self.last:
            p.fillRect(QRectF(0, h - 1, w, 1), QColor(T.LINE))


# ---------------------------------------------------------------- section heading
class SectionHead(QWidget):
    """01  WHEN ............................ [optional control]"""

    def __init__(self, index: int, title: str, right: QWidget | None = None, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout, QLabel
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(12)
        labels = []
        for text, font, color in ((f"{index:02d}", T.mono(11, T.QFont.Weight.Bold), T.RED),
                                  (title.upper(), T.mono(11, T.QFont.Weight.Medium, 1.6), T.INK)):
            lb = QLabel(text)
            lb.setFont(font)
            lb.setStyleSheet(f"color:{color}; background:transparent;")
            lay.addWidget(lb)
            labels.append(lb)
        self.title_lbl = labels[1]
        lay.addStretch(1)
        if right is not None:
            lay.addWidget(right)

    def set_title(self, title: str) -> None:
        self.title_lbl.setText(title.upper())

    def paintEvent(self, _):
        QPainter(self).fillRect(QRectF(0, self.height() - 1, self.width(), 1), QColor(T.INK))
