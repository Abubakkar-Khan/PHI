"""The signature PHI moment: a takeover you cannot miss, without strobing or stealing the keyboard.

Strategy
- Dim the whole screen (smooth scrim) so the Short stops being the loudest thing visible.
- The card drops in with a thud, an alarm tone plays, and a hazard stripe marches across its top.
- Concrete numbers (live session clock, today's total, how many Shorts) replace vague wording.
- Friction: "more time" is locked for a few seconds and the lock grows each time PHI has to ask again.
"""
from __future__ import annotations

import random
import sys
import threading

from PySide6.QtCore import (Property, QEasingCurve, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation, QRectF, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .. import winapi
from ..utils import fmt_clock, fmt_dur, minutes_text
from . import theme as T
from .mascot import RingMascot
from .motion import burst, float_text
from .pages import mk_label
from .lockscreen import LockScreen
from .widgets import LinkButton, PillButton

SHADOW = 24
CARD_W, CARD_H = 480, 664
CLOSE_HIT = 34


def _alarm() -> None:
    """Three falling tones, played off the UI thread."""
    if sys.platform != "win32":
        return

    def play():
        try:
            import winsound
            for freq, ms in ((932, 110), (740, 110), (523, 260)):
                winsound.Beep(freq, ms)
        except Exception:
            pass
    threading.Thread(target=play, daemon=True).start()


class Scrim(QWidget):
    """Full-screen dim layer. Eats mouse clicks (no accidental swipes) but never takes keyboard focus."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(QGuiApplication.primaryScreen().virtualGeometry())
        self._alpha = 0.0
        self._anim = QPropertyAnimation(self, b"alpha", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_alpha(self) -> float:
        return self._alpha

    def set_alpha(self, v: float) -> None:
        self._alpha = v
        self.update()

    alpha = Property(float, get_alpha, set_alpha)

    def fade(self, to: float, ms: int) -> None:
        self._anim.stop()
        self._anim.setDuration(ms)
        self._anim.setStartValue(self._alpha)
        self._anim.setEndValue(to)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(12, 10, 10, int(255 * self._alpha)))


class _CloseX(QWidget):
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(CLOSE_HIT, CLOSE_HIT)
        self._h = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._h = True
        self.update()

    def leaveEvent(self, e):
        self._h = False
        self.update()

    def mousePressEvent(self, e):
        self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._h:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.SOFT))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 8, 8)
        p.setPen(QPen(QColor(T.INK if self._h else T.GRAY), 1.4))
        c = CLOSE_HIT / 2
        p.drawLine(QPointF(c - 4.5, c - 4.5), QPointF(c + 4.5, c + 4.5))
        p.drawLine(QPointF(c - 4.5, c + 4.5), QPointF(c + 4.5, c - 4.5))


class NudgePopup(QWidget):
    action = Signal(str)   # stop | more | pause | bypass | dismiss

    HEADLINES = {
        "shorts": [["STOP SCROLLING.", "ENOUGH SHORTS."], ["AGAIN? REALLY?"], ["YOU KNOW THE DRILL."]],
        "daily": [["BUDGET BLOWN.", "THAT'S ENOUGH TODAY."], ["STILL HERE?"], ["NO MORE TODAY."]],
        "site": [["LIMIT HIT.", "TIME'S UP."], ["AGAIN?"], ["GO DO SOMETHING."]],
    }

    def __init__(self, payload: dict, extend_min: int, pause_min: int):
        super().__init__()
        self.payload = payload
        self.kind = payload["kind"]
        self._done = False
        self._seconds = payload["seconds"]
        self._typed = 0
        self._stripe = 0.0
        self._extend_min = extend_min
        self.repeat = max(1, int(payload.get("repeat", 1)))
        self._lock = min(12, 3 * self.repeat)           # seconds "more time" stays locked
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
                            | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(CARD_W + SHADOW * 2, CARD_H + SHADOW * 2)

        label = payload["label"]
        tiers = self.HEADLINES[self.kind]
        self.headline = random.choice(tiers[min(self.repeat, len(tiers)) - 1])
        if self.kind == "shorts":
            self.sub = ("Shorts is open. You set a limit for a reason." if self._seconds < 60
                        else f"You've been watching Shorts for {minutes_text(self._seconds)}.")
            stop_text = "I'm done — close Shorts"
        elif self.kind == "daily":
            self.sub = f"That's {minutes_text(self._seconds)} of Shorts today."
            stop_text = "I'm done — close Shorts"
        else:
            self.sub = f"{minutes_text(self._seconds)} on {label} today."
            stop_text = f"I'm done — close {label}"
        self.status = {"shorts": "DISTRACTION DETECTED", "daily": "DAILY BUDGET REACHED", "site": "SITE LIMIT REACHED"}[self.kind]

        root = QVBoxLayout(self)
        root.setContentsMargins(SHADOW + 28, SHADOW + 22, SHADOW + 28, SHADOW + 24)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.addWidget(mk_label("PHI_", T.mono(12, T.QFont.Weight.Medium, 2), T.GRAY))
        top.addSpacing(10)
        top.addWidget(mk_label("● " + self.status, T.mono(10, T.QFont.Weight.Medium, 1.4), T.RED))
        top.addStretch(1)
        x = _CloseX()
        x.clicked.connect(lambda: self._finish("dismiss"))
        top.addWidget(x)
        root.addLayout(top)

        self.ring = RingMascot(188, 3, "alert")
        root.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)

        self.big = mk_label("", T.mono(54, T.QFont.Weight.Bold), T.RED, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.big)
        self.title = mk_label("", T.sans(27, T.QFont.Weight.Bold), T.INK, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.title)
        self.subtitle = mk_label(self.sub, T.sans(14), T.GRAY, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.subtitle)
        root.addSpacing(8)
        self.facts = mk_label(self._facts(), T.mono(10, T.QFont.Weight.Medium, 1.2), T.INK, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.facts)
        root.addSpacing(16)

        btns = QVBoxLayout()
        btns.setSpacing(10)
        self.b_stop = PillButton(stop_text, "primary", "stop", height=52)
        self.b_more = PillButton("", "secondary", "clock", height=46)
        self.b_stop.clicked.connect(lambda: self._finish("stop"))
        self.b_more.clicked.connect(lambda: self._finish("more"))
        btns.addWidget(self.b_stop)
        btns.addWidget(self.b_more)
        root.addLayout(btns)
        self._update_more()
        root.addSpacing(10)

        links = QHBoxLayout()
        links.addStretch(1)
        hours = pause_min % 60 == 0 and pause_min >= 60
        pause = LinkButton(f"Pause reminders for {pause_min // 60 if hours else pause_min}{'h' if hours else 'm'}")
        pause.clicked.connect(lambda: self._finish("pause"))
        byp = LinkButton("I'm using it for something important")
        byp.clicked.connect(lambda: self._finish("bypass"))
        links.addWidget(pause)
        links.addSpacing(16)
        links.addWidget(byp)
        links.addStretch(1)
        root.addLayout(links)

        self._type_timer = QTimer(self)
        self._type_timer.setInterval(24)
        self._type_timer.timeout.connect(self._type)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)
        self._stripe_timer = QTimer(self)
        self._stripe_timer.setInterval(60)
        self._stripe_timer.timeout.connect(self._march)
        self.scrim: Scrim | None = None

    # ---- text helpers
    def _facts(self) -> str:
        parts = [f"TODAY {fmt_dur(self.payload.get('today_s', self._seconds))}"]
        if self.payload.get("count"):
            parts.append(f"{self.payload['count']} SHORTS WATCHED")
        parts.append(f"NUDGE #{self.repeat}")
        return "   ·   ".join(parts)

    def _big_text(self) -> str:
        return fmt_clock(self._seconds) if self.kind == "shorts" else fmt_dur(self._seconds).replace(" ", "")

    def _update_more(self) -> None:
        if self._lock > 0:
            self.b_more.setText(f"Give me {self._extend_min} more minutes  ·  {self._lock}s")
            self.b_more.setEnabled(False)
        else:
            self.b_more.setText(f"Give me {self._extend_min} more minutes")
            self.b_more.setEnabled(True)

    # ---- lifecycle
    def present(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self._home = QPoint(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)
        self.scrim = Scrim()
        self.scrim.show()
        self.scrim.fade(0.66, 260)
        self.move(self._home + QPoint(0, -140))
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(140)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        drop = QPropertyAnimation(self, b"pos", self)       # falls in and lands with a bounce: a thud
        drop.setDuration(560)
        drop.setStartValue(self._home + QPoint(0, -140))
        drop.setEndValue(self._home)
        drop.setEasingCurve(QEasingCurve.Type.OutBounce)
        self._in = QParallelAnimationGroup(self)
        self._in.addAnimation(fade)
        self._in.addAnimation(drop)
        self._in.start()
        _alarm()
        QTimer.singleShot(200, self._type_timer.start)
        self._tick_timer.start()
        self._stripe_timer.start()
        self._tick()

    def update_seconds(self, seconds: float):
        self._seconds = seconds
        self._tick(count=False)

    def _tick(self, count: bool = True):
        if self._done:
            return
        self.big.setText(self._big_text())
        if count and self._lock > 0:
            self._lock -= 1
            self._update_more()

    def _march(self):
        self._stripe = (self._stripe + 1.6) % 28
        self.update(QRectF(SHADOW, SHADOW, CARD_W, 16).toRect())

    def _type(self):
        text = self.headline
        if self._typed < len(text):
            self._typed += 1
            self.title.setText(text[:self._typed] + "▌")
        else:
            self.title.setText(text)
            self._type_timer.stop()

    def _finish(self, action: str):
        if self._done:
            return
        if action == "more" and self._lock > 0:
            return
        self._done = True
        self._type_timer.stop()
        self._tick_timer.stop()
        for b in (self.b_stop, self.b_more):
            b.setEnabled(False)
        if action == "stop":
            self.ring.set_mood("celebrate")
            burst(self.ring, "confetti", None, scale=1.1)
            burst(self.ring, "ring", None, [T.RED, T.ORANGE], 0.9)
            float_text(self.ring, "+1 STOPPED", None)
            self.big.setText("✓")
            self.big.setStyleSheet(f"color:{T.INK}; background:transparent;")
            self.title.setText("Nice. Back to it.")
            self.subtitle.setText("Good call. Closing it for you.")
            self.facts.setText("")
            hold = 1500
        else:
            hold = 0
        self.action.emit(action)
        QTimer.singleShot(hold, self._fade_out)

    def _fade_out(self):
        if self.scrim:
            self.scrim.fade(0.0, 260)
        out = QPropertyAnimation(self, b"windowOpacity", self)
        out.setDuration(240)
        out.setStartValue(self.windowOpacity())
        out.setEndValue(0.0)
        out.finished.connect(self.close)
        out.start()
        self._out = out

    def closeEvent(self, e):
        self._stripe_timer.stop()
        if self.scrim:
            self.scrim.close()
            self.scrim = None
        if not self._done:
            self._done = True
            self.action.emit("dismiss")
        super().closeEvent(e)

    # ---- painting: shadow, paper card, marching hazard stripe
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(SHADOW, SHADOW, CARD_W, CARD_H)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(SHADOW):
            p.setBrush(QColor(0, 0, 0, int(4.2 * (1 - i / SHADOW) ** 2 + 0.5)))
            p.drawRoundedRect(card.adjusted(-i, -i + 8, i, i + 8), 24 + i, 24 + i)
        path = QPainterPath()
        path.addRoundedRect(card, 24, 24)
        p.fillPath(path, QColor(T.BG))
        p.save()
        p.setClipPath(path)
        stripe_h, w = 14, 14
        p.fillRect(QRectF(card.left(), card.top(), card.width(), stripe_h), QColor(T.INK))
        p.setBrush(QColor(T.RED))
        x = card.left() - 40 + self._stripe
        while x < card.right() + 40:
            poly = QPainterPath()
            poly.moveTo(x, card.top() + stripe_h)
            poly.lineTo(x + w, card.top() + stripe_h)
            poly.lineTo(x + w + stripe_h, card.top())
            poly.lineTo(x + stripe_h, card.top())
            poly.closeSubpath()
            p.fillPath(poly, QColor(T.RED))
            x += w * 2
        p.restore()
        p.setPen(QPen(QColor("#CFCDC6"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(card, 24, 24)


class PopupController:
    """Owns the live popup; forwards the user's choice to the engine."""

    def __init__(self, engine, cfg):
        self.engine, self.cfg = engine, cfg
        self.current: NudgePopup | None = None
        engine.nudge.connect(self.show)
        engine.snapshot.connect(self._snap)

    def _snap(self, snap: dict):
        if self.current and snap["status"] == "shorts" and self.current.kind == "shorts":
            self.current.update_seconds(snap["session"])

    def show(self, payload: dict):
        if self.cfg.get("lockdown"):
            popup = LockScreen(payload, self.cfg.get("extend_min"), self.cfg.get("lockdown_seconds"))
        else:
            popup = NudgePopup(payload, self.cfg.get("extend_min"), self.cfg.get("pause_min"))
        pausing = bool(self.cfg.get("pause_video"))
        popup.action.connect(lambda a, pl=payload: self._on_action(a, pl, pausing))
        popup.destroyed.connect(lambda: setattr(self, "current", None) if self.current is popup else None)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.current = popup
        if pausing:
            winapi.media_play_pause()      # silence the Short behind the lock right away
        popup.present()

    def _on_action(self, action: str, payload: dict, paused: bool) -> None:
        if paused and action != "stop":    # staying on the page: let the video carry on
            QTimer.singleShot(500, winapi.media_play_pause)
        self.engine.resolve(payload, action)
