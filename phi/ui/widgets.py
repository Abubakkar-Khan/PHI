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
    """Rounded paper card with a hairline border that darkens slightly on hover."""

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
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(T.mix(T.LINE, T.GRAY, self._hover), 1))
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
        if t > .9:  # tiny signal light when on
            p.setBrush(QColor(T.RED))
            p.drawEllipse(QPointF(x + w / 2, 11), 1.6, 1.6)


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
        font = T.mono(12)
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
        self._text, self._mode, self._t, self._ph = "STARTING", "on", 0.0, 0.0
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


# ---------------------------------------------------------------- stat card
class StatCard(Panel):
    """Big number + 7-day bars. New data tweens in; only replay() plays the intro. A rising value pops."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title, self._fmt = title, lambda v: f"{v:.0f}"
        self._value, self._shown = 0.0, 0.0
        self._sub, self._delta, self._bad, self._dir = "", "", False, 0
        self._series: list[float] = []
        self._series_from: list[float] | None = None
        self._blend, self._grow, self._seen = 1.0, 1.0, False
        self.setMinimumHeight(122)
        self._count = animator(self, self._set_shown, 600)
        self._bars = animator(self, self._set_grow, 800)
        self._slide = animator(self, self._set_blend, 520)
        self._pulse = Spring(0.0, 320.0, 13.0)
        self._pk = Ticker(self._pulse_step)
        self._rt = QTimer(self)
        self._rt.setSingleShot(True)
        self._rt.timeout.connect(self._do_replay)

    def _set_shown(self, v):
        self._shown = v
        self.update()

    def _set_grow(self, v):
        self._grow = v
        self.update()

    def _set_blend(self, v):
        self._blend = v
        self.update()

    def _pulse_step(self, dt: float) -> bool:
        self._pulse.step(dt)
        self.update(QRect(14, 30, max(60, self.width() - 100), 56))
        return self.isVisible() and not self._pulse.resting

    def _display_series(self) -> list[float]:
        if self._series_from is None or self._blend >= 1.0 or len(self._series_from) != len(self._series):
            return self._series
        return _lerp_list(self._series_from, self._series, self._blend)

    def replay(self, delay: int = 0) -> None:
        """The entrance: count up from zero and grow the bars (optionally staggered)."""
        self._series_from = None
        self._shown, self._grow = 0.0, 0.0
        self._count.stop()
        self._bars.stop()
        self.update()
        self._rt.start(max(0, delay))

    def _do_replay(self) -> None:
        run(self._count, 0, self._value)
        run(self._bars, 0, 1)

    def set_data(self, value: float, fmt: Callable[[float], str], sub: str, delta: str, direction: int, bad: bool, series: list[float]):
        self._fmt, self._sub, self._delta, self._dir, self._bad = fmt, sub, delta, direction, bad
        series = list(series)
        if not self._seen:                              # first data: show it, no animation (replay() is the entrance)
            self._seen = True
            self._value, self._shown, self._series = value, value, series
        else:
            if value != self._value:
                if value > self._value:
                    self._pulse.kick(4.5)
                    self._pk.wake()
                run(self._count, self._shown, value)
            if series != self._series:
                self._series_from = self._display_series()
                self._series, self._blend = series, 0.0
                run(self._slide, 0, 1)
            self._value = value
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        label_font_paint(p, QRectF(20, 16, 200, 14), self.title.upper(), T.mono(10, spacing=1.4), T.GRAY)
        p.save()
        s = 1.0 + 0.045 * self._pulse.x
        p.translate(20, 58)
        p.scale(s, s)
        p.translate(-20, -58)
        label_font_paint(p, QRectF(20, 36, 220, 44), self._fmt(self._shown), T.sans(32, T.QFont.Weight.Medium), T.INK)
        p.restore()
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
        series = self._display_series()
        if series:
            mx = max(series) or 1.0
            bw, gap = 5, 3
            n = len(series)
            x0 = self.width() - 20 - n * (bw + gap) + gap
            base = self.height() - 22
            for i, v in enumerate(series):
                stagger = clamp(self._grow * (1 + n * .15) - i * .15)
                h = max(2.0, 38 * (v / mx) * stagger)
                last = i == n - 1
                col = QColor(T.RED if (last and self._bad) else T.INK) if last else QColor(T.BAR)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(QRectF(x0 + i * (bw + gap), base - h, bw, h), 1.5, 1.5)


# ---------------------------------------------------------------- timeline
class Timeline(QWidget):
    """Rows x 24h dot-matrix. Each row: (label, [24 seconds], is_red). Hover a cell to read it."""

    LABEL_W = 96
    AXIS_H = 22

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[str, list[float], bool]] = []
        self._reveal = 1.0
        self._anim = animator(self, self._set, 900, QEasingCurve.Type.InOutCubic)
        self._from: list[list[float]] | None = None
        self._blend = 1.0
        self._tween = animator(self, self._set_blend, 520)
        self._hc: tuple[int, int] | None = None
        self.show_now = True                  # the red "now" tick only makes sense for today
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self._now = QTimer(self)
        self._now.timeout.connect(self.update)
        self._now.start(30000)

    def _set(self, v):
        self._reveal = v
        self.update()

    def _set_blend(self, v):
        self._blend = v
        self.update()

    def _hours(self, ri: int) -> list[float]:
        hours = self.rows[ri][1]
        if self._from is None or self._blend >= 1.0 or ri >= len(self._from):
            return hours
        return _lerp_list(self._from[ri], hours, self._blend)

    def set_rows(self, rows):
        if not rows and not self.rows:
            return
        same = bool(self.rows) and [r[0] for r in rows] == [r[0] for r in self.rows]
        if same:
            if [r[1] for r in rows] != [r[1] for r in self.rows]:
                self._from = [self._hours(i) for i in range(len(self.rows))]
                self.rows, self._blend = rows, 0.0
                run(self._tween, 0, 1)
            else:
                self.rows = rows
        else:
            self._from, self.rows, self._blend = None, rows, 1.0
            run(self._anim, 0, 1)
        self.update()

    def replay(self) -> None:
        run(self._anim, 0, 1)

    def _geom(self):
        n = max(1, len(self.rows))
        row_h = (self.height() - self.AXIS_H) / max(n, 4)
        cw = (self.width() - self.LABEL_W) / 24.0
        return row_h, cw

    def mouseMoveEvent(self, e):
        row_h, cw = self._geom()
        x, y = e.position().x() - self.LABEL_W, e.position().y()
        cell = None
        if x >= 0 and y >= 0:
            ri, h = int(y // row_h), int(x // cw)
            if ri < len(self.rows) and 0 <= h < 24:
                cell = (ri, h)
        if cell != self._hc:
            self._hc = cell
            self.update()

    def leaveEvent(self, e):
        self._hc = None
        self.update()

    def paintEvent(self, _):
        from datetime import datetime
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        row_h, cw = self._geom()
        grid_x = self.LABEL_W
        hour_now = datetime.now().hour
        for h in range(0, 24, 3):                                   # axis
            label_font_paint(p, QRectF(grid_x + h * cw - 4, self.height() - self.AXIS_H + 6, cw * 3, 14), f"{h:02d}", T.mono(9, spacing=.6), T.GRAY)
        p.setPen(Qt.PenStyle.NoPen)                                 # "now" tick
        p.setBrush(QColor(T.RED))
        if self.show_now:
            p.drawRoundedRect(QRectF(grid_x + hour_now * cw + cw / 2 - 3, self.height() - self.AXIS_H + 2, 6, 2), 1, 1)
        tag = None
        for ri, (name, _hrs, red) in enumerate(self.rows):
            hours = self._hours(ri)
            y = ri * row_h
            label_font_paint(p, QRectF(0, y, self.LABEL_W - 8, row_h), name, T.sans(12), T.INK if not red else T.RED)
            mx = 1800.0  # half an hour of use fills a cell
            base = T.RED if red else T.INK
            for h in range(24):
                visible = clamp(self._reveal * 28 - h)
                rect = QRectF(grid_x + h * cw + 1.5, y + row_h * .22, cw - 3, row_h * .56)
                v = min(1.0, hours[h] / mx) * visible
                hot = self._hc == (ri, h)
                if hot:
                    rect = rect.adjusted(0, -1.5, 0, 0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(T.CELL) if v <= 0.02 else T.mix(T.CELL, base, .25 + .75 * v))
                p.drawRoundedRect(rect, 2.5, 2.5)
                if hot:
                    p.setPen(QPen(QColor(T.INK), 1.2))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(rect.adjusted(-.5, -.5, .5, .5), 3, 3)
                    tag = (rect, f"{h:02d}:00  ·  {fmt_dur(self.rows[ri][1][h])}")
        if not self.rows:
            label_font_paint(p, QRectF(0, 0, self.width(), self.height() - self.AXIS_H), "no activity logged yet_", T.mono(11), T.GRAY, Qt.AlignmentFlag.AlignCenter)
        if tag:
            rect, txt = tag
            font = T.mono(10, T.QFont.Weight.Medium)
            w = QFontMetrics(font).horizontalAdvance(txt) + 16
            bx = clamp(rect.center().x() - w / 2, 0.0, self.width() - w)
            by = max(0.0, rect.top() - 26)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.INK))
            p.drawRoundedRect(QRectF(bx, by, w, 20), 6, 6)
            label_font_paint(p, QRectF(bx, by, w, 20), txt, font, T.PAPER, Qt.AlignmentFlag.AlignCenter)


# ---------------------------------------------------------------- bar chart
class PixelChart(QWidget):
    """Columns built from small squares: ink for active time, red for Shorts. Same labels = tween, new labels = grow."""

    clicked = Signal(int)                      # column index (when clickable)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tips: list[str] = []              # optional hover prefix per column, e.g. "TUE 20 OCT"
        self.clickable = False
        self.cols: list[tuple[str, float, float, bool]] = []   # label, total_s, shorts_s, highlight
        self.unit_s = 600.0
        self._grow = 1.0
        self._hover = -1
        self._from: list[tuple[float, float]] | None = None
        self._blend = 1.0
        self.setMouseTracking(True)
        self.setMinimumHeight(190)
        self._anim = animator(self, self._set, 900)
        self._tween = animator(self, self._set_blend, 520)

    def _set(self, v):
        self._grow = v
        self.update()

    def _set_blend(self, v):
        self._blend = v
        self.update()

    def _disp(self) -> list[tuple[float, float]]:
        if self._from is None or self._blend >= 1.0 or len(self._from) != len(self.cols):
            return [(c[1], c[2]) for c in self.cols]
        b = self._blend
        return [(f[0] + (c[1] - f[0]) * b, f[1] + (c[2] - f[1]) * b) for f, c in zip(self._from, self.cols)]

    def set_columns(self, cols, animate=True, replay=False):
        same = bool(self.cols) and not replay and [c[0] for c in cols] == [c[0] for c in self.cols]
        if same:
            if [c[1:3] for c in cols] != [c[1:3] for c in self.cols]:
                self._from = self._disp()
                self.cols, self._blend = cols, 0.0
                run(self._tween, 0, 1)
            else:
                self.cols = cols
        else:
            self._from, self.cols, self._blend = None, cols, 1.0
            if animate:
                run(self._anim, 0, 1)
            else:
                self._grow = 1.0
        self.update()

    def replay(self) -> None:
        self._from, self._blend = None, 1.0
        run(self._anim, 0, 1)

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
            self.setCursor(Qt.CursorShape.PointingHandCursor if (self.clickable and i >= 0) else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        if self.clickable and 0 <= self._hover < len(self.cols):
            self.clicked.emit(self._hover)

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        n, cw, top, base = self._geom()
        disp = self._disp()
        mx = max([d[0] for d in disp] + [1.0])
        sq = 7 if cw > 22 else 5
        gap = 2
        max_cells = max(1, int((base - top) // (sq + gap)))
        sq_w = min(sq + 3, int(cw * .5))
        for i, ((label, _t, _s, hi), (total, shorts)) in enumerate(zip(self.cols, disp)):
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
                    col = QColor(T.BAR)
                p.fillRect(QRectF(x, y, sq_w, sq), col)
            if total == 0:
                p.fillRect(QRectF(x, base - 2, sq_w, 2), QColor(T.CELL))
            p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            label_font_paint(p, QRectF(i * cw, base + 6, cw, 14), label, T.mono(9, spacing=.4), T.INK if hi else T.GRAY, Qt.AlignmentFlag.AlignCenter)
            if hovered:
                tip = f"{self.tips[i]}  ·  " if i < len(self.tips) and self.tips[i] else ""
                txt = tip + fmt_dur(total) + (f"  ·  {fmt_dur(shorts)} shorts" if shorts >= 60 else "")
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
    """One line of the breakdown. set_values() slides the bar and number to new data without rebuilding the row."""

    def __init__(self, name: str, tag: str, seconds: float, share: float, red: bool = False, delay: int = 0, parent=None):
        super().__init__(parent)
        self.name, self.tag, self.seconds, self.share, self.red = name, tag, seconds, share, red
        self._from = (seconds, share)
        self._u = 1.0
        self._fill, self._hover = 0.0, 0.0
        self.setFixedHeight(50)
        self._anim = animator(self, self._set_fill, 700)
        self._upd = animator(self, self._set_u, 450)
        self._h = animator(self, self._set_hover, 150)
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
        # dotted share bar; the leading dot of a growing bar glows
        bx, bw = 250, max(60, w - 250 - 150)
        n = int(bw // 7)
        lit_f = n * share * self._fill
        lit = int(round(lit_f))
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            on = i < lit
            col = QColor(T.RED if (self.red and on) else (T.INK if on else T.CELL))
            p.setBrush(col)
            p.drawRoundedRect(QRectF(bx + i * 7, h / 2 - 3, 4, 6), 1, 1)
        if 0.02 < self._fill < 0.98 and lit > 0:
            p.setBrush(QColor(T.ORANGE))
            p.drawRoundedRect(QRectF(bx + (lit - 1) * 7, h / 2 - 3, 4, 6), 1, 1)
        label_font_paint(p, QRectF(w - 130, 0, 70, h), fmt_dur(seconds), T.mono(12, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_font_paint(p, QRectF(w - 56, 0, 46, h), f"{round(share * 100)}%", T.mono(10), T.GRAY, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


# ---------------------------------------------------------------- limit bars
class LimitBar(QWidget):
    """One budget line: name, 'used / limit' and a bar that turns red as the limit nears."""

    def __init__(self, name: str, tag: str, used: float, limit: float, parent=None):
        super().__init__(parent)
        self.name, self.tag, self.used, self.limit = name, tag, used, limit
        self._shown = used
        self.setFixedHeight(46)
        self._anim = animator(self, self._set, 500)

    def _set(self, v):
        self._shown = v
        self.update()

    def set_values(self, used: float, limit: float) -> None:
        if (used, limit) == (self.used, self.limit):
            return
        self.limit = limit
        start = self._shown
        self.used = used
        self._anim.stop()
        self._anim.valueChanged.disconnect()
        self._anim.valueChanged.connect(lambda v, a=start, b=used: self._set(a + (b - a) * float(v)))
        run(self._anim, 0, 1)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        frac = clamp(self._shown / self.limit) if self.limit else 0.0
        hot = frac >= 0.85
        label_font_paint(p, QRectF(0, 2, w - 150, 18), self.name, T.sans(13, T.QFont.Weight.Medium), T.INK)
        label_font_paint(p, QRectF(w - 150, 2, 150, 18), f"{fmt_dur(self._shown)} / {fmt_dur(self.limit)}",
                         T.mono(11, T.QFont.Weight.Medium), T.RED if hot else T.INK,
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label_font_paint(p, QRectF(0, 20, w, 12), self.tag.upper(), T.mono(8, spacing=1.0), T.GRAY)
        n = max(10, int((w) // 7))
        lit = int(round(n * frac))
        p.setPen(Qt.PenStyle.NoPen)
        step = w / n
        for i in range(n):
            p.setBrush(QColor(T.RED if (hot and i < lit) else (T.INK if i < lit else T.CELL)))
            p.drawRoundedRect(QRectF(i * step, 34, max(2.0, step - 3), 6), 1.5, 1.5)
