"""Shared motion primitives: one frame clock, springs, smoothing and a pixel-spark layer.

Everything animated by hand (mascot, hover glows, sparks) runs off a single 60 Hz timer that only
exists while something is actually moving, so an idle PHI sitting in the tray costs nothing.
"""
from __future__ import annotations

import math
import random
import time
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from . import theme as T

FRAME_MS = 16


# ---------------------------------------------------------------- frame clock
class _Clock(QObject):
    """One precise timer shared by every animation. Starts with the first subscriber, stops with the last."""

    def __init__(self):
        super().__init__()
        self._subs: list[Callable[[float], None]] = []
        self._last = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self._tick)

    def subscribe(self, fn: Callable[[float], None]) -> None:
        if fn in self._subs:
            return
        self._subs.append(fn)
        if not self._timer.isActive():
            self._last = time.perf_counter()
            self._timer.start()

    def unsubscribe(self, fn: Callable[[float], None]) -> None:
        try:
            self._subs.remove(fn)
        except ValueError:
            return
        if not self._subs:
            self._timer.stop()

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(now - self._last, 0.05)      # a stall must not teleport anything
        self._last = now
        for fn in list(self._subs):
            try:
                fn(dt)
            except RuntimeError:              # the widget behind this callback is gone
                self.unsubscribe(fn)


_clock: _Clock | None = None


def clock() -> _Clock:
    global _clock
    if _clock is None:
        _clock = _Clock()
    return _clock


class Ticker:
    """Calls fn(dt) every frame while fn returns True; sleeps (no timer wakeups) once it returns False."""

    def __init__(self, fn: Callable[[float], bool]):
        self.fn, self.awake = fn, False

    def wake(self) -> None:
        if not self.awake:
            self.awake = True
            clock().subscribe(self._tick)

    def sleep(self) -> None:
        if self.awake:
            self.awake = False
            clock().unsubscribe(self._tick)

    def _tick(self, dt: float) -> None:
        if not self.fn(dt):
            self.sleep()


# ---------------------------------------------------------------- physics
class Spring:
    """Damped spring. Underdamped (d < 2*sqrt(k)) overshoots, which is where the bounce comes from."""
    __slots__ = ("x", "v", "target", "k", "d")

    def __init__(self, x: float = 0.0, k: float = 170.0, d: float = 15.0):
        self.x, self.v, self.target, self.k, self.d = x, 0.0, x, k, d

    def step(self, dt: float) -> float:
        n = int(dt / 0.006) + 1               # sub-step: stiff springs stay stable at any frame time
        h = dt / n
        for _ in range(n):
            self.v += (self.k * (self.target - self.x) - self.d * self.v) * h
            self.x += self.v * h
        return self.x

    def kick(self, velocity: float) -> None:
        self.v += velocity

    def snap(self, x: float) -> None:
        self.x = self.target = x
        self.v = 0.0

    @property
    def resting(self) -> bool:
        return abs(self.v) < 0.02 and abs(self.target - self.x) < 0.002


class Smooth:
    """Frame-rate independent exponential approach: the right feel for hover glows and fades."""
    __slots__ = ("x", "target", "rate")

    def __init__(self, x: float = 0.0, rate: float = 14.0):
        self.x, self.target, self.rate = x, x, rate

    def step(self, dt: float) -> float:
        self.x += (self.target - self.x) * (1.0 - math.exp(-self.rate * dt))
        return self.x

    def snap(self, x: float) -> None:
        self.x = self.target = x

    @property
    def resting(self) -> bool:
        return abs(self.target - self.x) < 0.002


def clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def out_back(t: float, s: float = 1.70158) -> float:
    t -= 1.0
    return t * t * ((s + 1.0) * t + s) + 1.0


# ---------------------------------------------------------------- sparks
class _Spark:
    __slots__ = ("x", "y", "vx", "vy", "age", "life", "size", "color", "grav", "drag", "shape", "text")

    def __init__(self, x, y, vx, vy, life, size, color, grav=0.0, drag=0.0, shape="sq", text=""):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.age, self.life, self.size = 0.0, life, size
        self.color, self.grav, self.drag, self.shape, self.text = QColor(color), grav, drag, shape, text


class ParticleLayer(QWidget):
    """Transparent, click-through overlay on a window. It is only visible (and only costs anything) while sparks fly."""

    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._sparks: list[_Spark] = []
        self._prev = QRect()
        self._font = T.mono(13, T.QFont.Weight.Bold)
        host.installEventFilter(self)
        self.setGeometry(host.rect())
        self.hide()

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.Resize:
            self.setGeometry(self.parentWidget().rect())
        return False

    def add(self, sparks: list[_Spark]) -> None:
        self._sparks.extend(sparks)
        if len(self._sparks) > 160:
            del self._sparks[:len(self._sparks) - 160]
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        clock().subscribe(self._step)

    def _step(self, dt: float) -> None:
        live: list[_Spark] = []
        box = QRect()
        for s in self._sparks:
            s.age += dt
            if s.age >= s.life:
                continue
            s.vy += s.grav * dt
            if s.drag:
                f = max(0.0, 1.0 - s.drag * dt)
                s.vx *= f
                s.vy *= f
            s.x += s.vx * dt
            s.y += s.vy * dt
            pad = int(s.size * 3) + 4 if s.shape != "text" else 60
            box = box.united(QRect(int(s.x) - pad, int(s.y) - pad, pad * 2, pad * 2))
            live.append(s)
        self._sparks = live
        dirty = box.united(self._prev) if not self._prev.isNull() else box
        self._prev = box
        if not live:
            clock().unsubscribe(self._step)
            self.hide()
            return
        self.update(dirty)

    def paintEvent(self, _):
        p = QPainter(self)
        for s in self._sparks:
            k = s.age / s.life
            alpha = 1.0 if k < 0.55 else max(0.0, 1.0 - (k - 0.55) / 0.45)
            c = QColor(s.color)
            c.setAlphaF(c.alphaF() * alpha)
            x, y = int(s.x), int(s.y)
            if s.shape == "text":
                p.setFont(self._font)
                p.setPen(c)
                fm = QFontMetrics(self._font)
                p.drawText(x - fm.horizontalAdvance(s.text) // 2, y, s.text)
                continue
            size = max(1, int(round(s.size * (1.0 - 0.45 * k))))
            if s.shape == "plus":
                for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                    p.fillRect(x + dx * size, y + dy * size, size, size, c)
            else:
                p.fillRect(x, y, size, size, c)


def layer_for(widget: QWidget) -> ParticleLayer:
    win = widget.window()
    layer = getattr(win, "_phi_fx", None)
    if layer is None:
        layer = ParticleLayer(win)
        win._phi_fx = layer
    return layer


def _origin(widget: QWidget, pos) -> QPointF:
    win = widget.window()
    if pos is None:
        pos = QPointF(widget.width() / 2, widget.height() / 2)
    p = widget.mapTo(win, QPoint(int(pos.x()), int(pos.y())))
    return QPointF(p)


def burst(widget: QWidget, kind: str = "pop", pos=None, colors: list[str] | None = None, scale: float = 1.0) -> None:
    """Spawn pixel sparks at `pos` (widget coordinates; default centre). Kinds: pop | ring | confetti | plus."""
    if not widget.isVisible():
        return
    o = _origin(widget, pos)
    rnd = random.random
    sparks: list[_Spark] = []
    if kind == "confetti":
        palette = colors or [T.INK, T.RED, T.ORANGE, T.ORANGE, "#B9B7B0"]
        for i in range(34):
            a = -math.pi / 2 + (rnd() - 0.5) * 2.3
            v = (240 + rnd() * 340) * scale
            sparks.append(_Spark(o.x(), o.y(), math.cos(a) * v, math.sin(a) * v, 1.1 + rnd() * 0.9,
                                 4 + int(rnd() * 3), random.choice(palette), grav=980, drag=1.4,
                                 shape="plus" if i % 9 == 0 else "sq"))
    elif kind == "plus":
        for i in range(3):
            sparks.append(_Spark(o.x() + (i - 1) * 14 * scale, o.y(), (i - 1) * 16, -(52 + rnd() * 30) * scale, 0.9 + rnd() * 0.3,
                                 2, T.ORANGE, grav=-10, drag=0.8, shape="plus"))
    elif kind == "ring":
        palette = colors or [T.INK, T.ORANGE]
        for i in range(14):
            a = 2 * math.pi * i / 14
            sparks.append(_Spark(o.x(), o.y(), math.cos(a) * 170 * scale, math.sin(a) * 170 * scale, 0.5, 3,
                                 palette[i % len(palette)], drag=5.0))
    else:  # pop
        palette = colors or [T.INK, T.RED, T.ORANGE]
        for i in range(9):
            a = 2 * math.pi * i / 9 + rnd() * 0.5
            v = (90 + rnd() * 110) * scale
            sparks.append(_Spark(o.x(), o.y(), math.cos(a) * v, math.sin(a) * v - 30, 0.42 + rnd() * 0.22, 3 + int(rnd() * 2),
                                 random.choice(palette), grav=320, drag=2.2))
    layer_for(widget).add(sparks)


def float_text(widget: QWidget, text: str, pos=None, color: str = T.ORANGE) -> None:
    """A short label that rises and fades, like a +1 popping out of a game character."""
    if not widget.isVisible():
        return
    o = _origin(widget, pos)
    layer_for(widget).add([_Spark(o.x(), o.y(), 0.0, -46, 1.1, 1, color, drag=1.6, shape="text", text=text)])
