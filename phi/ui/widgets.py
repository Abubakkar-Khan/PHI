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
    """A rounded card with a hairline border."""

    def __init__(self, parent=None, radius: int = 16, fill: str | None = None, hoverable: bool = True):
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
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(T.mix(T.LINE, T.GRAY, self._hover * 0.5), 1))
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
        fm = QFontMetrics(T.sans(13, T.QFont.Weight.Medium))
        self._w = [fm.horizontalAdvance(o) + 30 for o in self.options]
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
            label_font_paint(p, QRectF(x, 0, self._w[i], 32), o, T.sans(13, T.QFont.Weight.Medium),
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
            fm = QFontMetrics(T.sans(12))
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
        label_font_paint(p, QRectF(20, 0, self.width() - 20, self.height()), self._text, T.sans(12), T.GRAY)


# ---------------------------------------------------------------- bar chart
def _nice_max(seconds: float) -> float:
    """Round a maximum up to a tidy axis value (10m, 20m, 30m, 1h, 2h ...)."""
    mins = seconds / 60.0
    for n in (5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 300, 360, 480, 600, 720, 960, 1200):
        if mins <= n:
            return n * 60.0
    return float(int(mins / 600 + 1) * 600 * 60)


class BarChart(QWidget):
    """Rounded bars with two light gridlines and a readable axis. The current bar is dark; hover reads a value."""
    clicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cols: list[tuple[str, float, bool]] = []      # label, seconds, highlight
        self.tips: list[str] = []
        self.clickable = False
        self._hover = -1
        self._grow = 1.0
        self._anim = animator(self, self._set_grow, 750, QEasingCurve.Type.OutCubic)
        self.setMouseTracking(True)
        self.setMinimumHeight(190)

    LEFT, TOP, BOTTOM = 46, 14, 26

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
        return (self.width() - self.LEFT) / max(1, len(self.cols))

    def mouseMoveEvent(self, e):
        i = int((e.position().x() - self.LEFT) // self._slot()) if self.cols else -1
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
        base = self.height() - self.BOTTOM
        usable = max(10.0, base - self.TOP)
        peak = _nice_max(max([c[1] for c in self.cols] + [60.0]))
        # gridlines
        for frac in (0.5, 1.0):
            y = base - usable * frac
            p.setPen(QPen(QColor(T.LINE), 1))
            p.drawLine(QPointF(self.LEFT, y), QPointF(self.width(), y))
            label_font_paint(p, QRectF(0, y - 8, self.LEFT - 8, 16), fmt_dur(peak * frac), T.sans(11), T.GRAY,
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        p.setPen(QPen(QColor(T.EDGE), 1))
        p.drawLine(QPointF(self.LEFT, base), QPointF(self.width(), base))
        bw = max(4.0, min(slot * 0.58, 30.0))
        for i, (label, secs, hi) in enumerate(self.cols):
            h = usable * min(1.0, secs / peak) * self._grow
            x = self.LEFT + i * slot + (slot - bw) / 2
            p.setPen(Qt.PenStyle.NoPen)
            if secs > 0:
                p.setBrush(QColor(T.INK) if (hi or i == self._hover) else QColor(T.BAR))
                p.drawRoundedRect(QRectF(x, base - max(h, 3.0), bw, max(h, 3.0)), min(6.0, bw / 2), min(6.0, bw / 2))
            if label:
                label_font_paint(p, QRectF(self.LEFT + i * slot - 10, base + 6, slot + 20, 16), label, T.sans(11),
                                 T.INK if hi else T.GRAY, Qt.AlignmentFlag.AlignCenter)
        if 0 <= self._hover < len(self.cols):
            i = self._hover
            tip = f"{self.tips[i]}  \u00b7  " if i < len(self.tips) and self.tips[i] else ""
            txt = tip + fmt_dur(self.cols[i][1])
            font = T.sans(12, T.QFont.Weight.Medium)
            w = QFontMetrics(font).horizontalAdvance(txt) + 20
            bx = clamp(self.LEFT + i * slot + slot / 2 - w / 2, self.LEFT, self.width() - w)
            h = usable * min(1.0, self.cols[i][1] / peak) * self._grow
            by = max(0.0, base - max(h, 3.0) - 34)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.INK))
            p.drawRoundedRect(QRectF(bx, by, w, 26), 8, 8)
            label_font_paint(p, QRectF(bx, by, w, 26), txt, font, T.PAPER, Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------- stat card
class StatCard(Panel):
    """A small card: title, one big value, a caption, and optionally a 7-day mini chart."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent, hoverable=True)
        self.title, self.value, self.sub = title, "", ""
        self.sub_color: str | None = None
        self.series: list[float] = []
        self._grow = 1.0
        self.setMinimumHeight(128)
        self._anim = animator(self, self._set_grow, 700, QEasingCurve.Type.OutCubic)

    def _set_grow(self, v):
        self._grow = v
        self.update()

    def set_data(self, value: str, sub: str, series: list[float] | None = None, sub_color: str | None = None) -> None:
        changed = (value, sub, series or []) != (self.value, self.sub, self.series)
        self.value, self.sub, self.sub_color, self.series = value, sub, sub_color, list(series or [])
        if changed:
            self.update()

    def replay(self, delay: int = 0) -> None:
        QTimer.singleShot(max(0, delay), lambda: run(self._anim, 0, 1))

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        label_font_paint(p, QRectF(20, 16, w - 40, 18), self.title, T.sans(13, T.QFont.Weight.Medium), T.GRAY)
        room = w - 40 - (84 if self.series else 0)
        font = T.sans(34, T.QFont.Weight.Medium)
        fm = QFontMetrics(font)
        while fm.horizontalAdvance(self.value) > room and font.pixelSize() > 16:
            font.setPixelSize(font.pixelSize() - 2)
            fm = QFontMetrics(font)
        label_font_paint(p, QRectF(20, 40, room, 48), self.value, font, T.INK)
        label_font_paint(p, QRectF(20, h - 34, w - 40, 20), self.sub, T.sans(12), self.sub_color or T.GRAY)
        if self.series:
            mx = max(self.series) or 1.0
            bw, gap = 7, 4
            x0 = w - 20 - len(self.series) * (bw + gap) + gap
            base = h - 42
            p.setPen(Qt.PenStyle.NoPen)
            for i, v in enumerate(self.series):
                bh = max(3.0, 40 * (v / mx) * clamp(self._grow * 1.3 - i * 0.05))
                p.setBrush(QColor(T.INK) if i == len(self.series) - 1 else QColor(T.BAR))
                p.drawRoundedRect(QRectF(x0 + i * (bw + gap), base - bh, bw, bh), 2.5, 2.5)


# ---------------------------------------------------------------- list row
class ItemRow(QWidget):
    """Letter tile, name, a thin share bar, and the time. Hover shows a hide (eye) button."""

    hide_requested = Signal()

    def __init__(self, name: str, seconds: float, share: float, last: bool = False, delay: int = 0, index: int = 1, parent=None):
        super().__init__(parent)
        self.name, self.seconds, self.share, self.last = name, seconds, share, last
        self._from = (seconds, share)
        self._u, self._fill, self._hover = 1.0, 0.0, 0.0
        self._eye_hot = False
        self.setMouseTracking(True)
        self.setFixedHeight(62)
        self._anim = animator(self, self._set_fill, 700, QEasingCurve.Type.OutCubic)
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
        self._eye_hot = False
        self.setCursor(Qt.CursorShape.ArrowCursor)
        run(self._h, self._hover, 0)

    def _eye_rect(self) -> QRectF:
        return QRectF(self.width() - 172, 8, 28, 26)

    def mouseMoveEvent(self, e):
        hot = self._eye_rect().contains(e.position())
        if hot != self._eye_hot:
            self._eye_hot = hot
            self.setCursor(Qt.CursorShape.PointingHandCursor if hot else Qt.CursorShape.ArrowCursor)
            self.setToolTip("Hide from activity" if hot else "")
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._eye_rect().contains(e.position()):
            self.hide_requested.emit()

    def contextMenuEvent(self, e):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        act = menu.addAction(f"Hide \u201c{self.name}\u201d from activity")
        if menu.exec(e.globalPos()) is act:
            self.hide_requested.emit()

    def _paint_eye(self, p: QPainter) -> None:
        """A small crossed-out eye, drawn with paths so it follows the theme."""
        r = self._eye_rect()
        if self._eye_hot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.CELL))
            p.drawRoundedRect(r, 8, 8)
        c = r.center()
        col = QColor(T.INK if self._eye_hot else T.GRAY)
        col.setAlphaF(min(1.0, self._hover))
        p.setPen(QPen(col, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        eye = QPainterPath()
        eye.moveTo(c.x() - 8, c.y())
        eye.quadTo(c.x(), c.y() - 9, c.x() + 8, c.y())
        eye.quadTo(c.x(), c.y() + 9, c.x() - 8, c.y())
        p.drawPath(eye)
        p.drawEllipse(c, 2.2, 2.2)
        p.drawLine(QPointF(c.x() - 7, c.y() + 7), QPointF(c.x() + 7, c.y() - 7))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        seconds, share = self.shown()
        if self._hover > 0.01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.qc(T.SOFT, self._hover * .6))
            p.drawRoundedRect(QRectF(6, 3, w - 12, h - 6), 12, 12)
        tile = QRectF(20, (h - 38) / 2, 38, 38)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.SOFT))
        p.drawRoundedRect(tile, 11, 11)
        label_font_paint(p, tile, self.name[:1].upper(), T.sans(16, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignCenter)
        label_font_paint(p, QRectF(72, 9, w - 250, 24), self.name, T.sans(15, T.QFont.Weight.Medium), T.INK)
        if self._hover > 0.05:
            self._paint_eye(p)
        track = QRectF(72, 38, max(40.0, w - 72 - 130), 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.CELL))
        p.drawRoundedRect(track, 2.5, 2.5)
        p.setBrush(QColor(T.INK))
        p.drawRoundedRect(QRectF(track.left(), track.top(), max(5.0, track.width() * clamp(share) * self._fill), 5), 2.5, 2.5)
        label_font_paint(p, QRectF(w - 128, 0, 108, h), fmt_dur(seconds), T.sans(15, T.QFont.Weight.Medium), T.INK,
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if not self.last:
            p.fillRect(QRectF(72, h - 1, w - 92, 1), QColor(T.LINE))


# ---------------------------------------------------------------- section title
class SectionTitle(QWidget):
    """A plain heading with an optional control on the right."""

    def __init__(self, title: str, right: QWidget | None = None, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout, QLabel
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 0, 0)
        self.title_lbl = QLabel(title)
        self.title_lbl.setFont(T.sans(17, T.QFont.Weight.Medium))
        self.title_lbl.setStyleSheet(f"color:{T.INK}; background:transparent;")
        lay.addWidget(self.title_lbl)
        lay.addStretch(1)
        if right is not None:
            lay.addWidget(right)

    def set_title(self, title: str) -> None:
        self.title_lbl.setText(title)
