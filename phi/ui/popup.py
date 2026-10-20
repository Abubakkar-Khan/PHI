"""The signature PHI moment: a compact, gentle, never-focus-stealing nudge."""
from __future__ import annotations

import random

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..utils import fmt_clock, minutes_text
from . import theme as T
from .mascot import RingMascot
from .pages import mk_label
from .widgets import LinkButton, PillButton

SHADOW = 22
CLOSE_HIT = 34


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
        p.drawLine(c - 4.5, c - 4.5, c + 4.5, c + 4.5)
        p.drawLine(c - 4.5, c + 4.5, c + 4.5, c - 4.5)


class NudgePopup(QWidget):
    action = Signal(str)   # stop | more | pause | bypass | dismiss

    HEADLINES = {
        "shorts": ["Still scrolling?", "Quick check-in.", "Surface for air?"],
        "daily": ["That's today's budget.", "Budget reached."],
        "site": ["Time check.", "Still here?"],
    }

    def __init__(self, payload: dict, extend_min: int, pause_min: int):
        super().__init__()
        self.payload = payload
        self.kind = payload["kind"]
        self._done = False
        self._seconds = payload["seconds"]
        self._typed = 0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
                            | Qt.WindowType.NoDropShadowWindowHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(460 + SHADOW * 2, 560 + SHADOW * 2)

        label = payload["label"]
        self.headline = random.choice(self.HEADLINES[self.kind])
        if self.kind == "shorts":
            self.sub = f"You've been watching Shorts for {minutes_text(self._seconds)}."
            stop_text = "I'm done — close Shorts"
        elif self.kind == "daily":
            self.sub = f"That's {minutes_text(self._seconds)} of Shorts today."
            stop_text = "I'm done — close Shorts"
        else:
            self.sub = f"{minutes_text(self._seconds)} on {label} today."
            stop_text = f"I'm done — close {label}"
        self.status = {"shorts": "01 DISTRACTION\nDETECTED.", "daily": "01 BUDGET\nREACHED.", "site": "01 LIMIT\nREACHED."}[self.kind]

        root = QVBoxLayout(self)
        root.setContentsMargins(SHADOW + 26, SHADOW + 14, SHADOW + 26, SHADOW + 24)
        root.setSpacing(0)

        top = QHBoxLayout()
        top.addWidget(mk_label("PHI_", T.mono(12, T.QFont.Weight.Medium, 2), T.GRAY))
        top.addStretch(1)
        x = _CloseX()
        x.clicked.connect(lambda: self._finish("dismiss"))
        top.addWidget(x)
        root.addLayout(top)

        mid = QHBoxLayout()
        mid.addWidget(mk_label(self.status, T.mono(9, spacing=1.2), T.GRAY), 0, Qt.AlignmentFlag.AlignTop)
        mid.addStretch(1)
        mid.addWidget(mk_label("ATTENTION\nIS A\nCHOICE_", T.mono(9, spacing=1.2), T.GRAY, Qt.AlignmentFlag.AlignRight), 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(mid)
        root.addSpacing(-34)

        self.ring = RingMascot(230, 6, "alert")
        root.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(6)

        self.title = mk_label("", T.sans(32, T.QFont.Weight.Medium), T.INK, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.title)
        self.subtitle = mk_label(self.sub, T.sans(14), T.GRAY, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.subtitle)
        self.clock = mk_label("", T.mono(11, spacing=1.4), T.GRAY, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.clock)
        root.addSpacing(18)

        btns = QVBoxLayout()
        btns.setSpacing(10)
        self.b_stop = PillButton(stop_text, "primary", "stop", height=48)
        self.b_more = PillButton(f"Give me {extend_min} more minutes", "secondary", "clock", height=48)
        self.b_stop.clicked.connect(lambda: self._finish("stop"))
        self.b_more.clicked.connect(lambda: self._finish("more"))
        btns.addWidget(self.b_stop)
        btns.addWidget(self.b_more)
        root.addLayout(btns)
        root.addSpacing(10)

        links = QHBoxLayout()
        links.addStretch(1)
        pause = LinkButton(f"Pause reminders for {pause_min // 60 if pause_min % 60 == 0 and pause_min >= 60 else pause_min}{'h' if pause_min % 60 == 0 and pause_min >= 60 else 'm'}")
        pause.clicked.connect(lambda: self._finish("pause"))
        byp = LinkButton("I'm using it for something important")
        byp.clicked.connect(lambda: self._finish("bypass"))
        links.addWidget(pause)
        links.addSpacing(16)
        links.addWidget(byp)
        links.addStretch(1)
        root.addLayout(links)

        # typewriter + live clock
        self._type_timer = QTimer(self)
        self._type_timer.setInterval(45)
        self._type_timer.timeout.connect(self._type)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._tick)
        self._cursor_on = True

    # ---- lifecycle
    def present(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self._home = QPoint(screen.center().x() - self.width() // 2, screen.center().y() - self.height() // 2)
        self.move(self._home + QPoint(0, 24))
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(320)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        rise = QPropertyAnimation(self, b"pos", self)
        rise.setDuration(420)
        rise.setStartValue(self._home + QPoint(0, 24))
        rise.setEndValue(self._home)
        rise.setEasingCurve(QEasingCurve.Type.OutBack)
        self._in = QParallelAnimationGroup(self)
        self._in.addAnimation(fade)
        self._in.addAnimation(rise)
        self._in.start()
        QTimer.singleShot(250, self._type_timer.start)
        self._tick_timer.start()
        self._tick()

    def update_seconds(self, seconds: float):
        self._seconds = seconds
        self._tick()

    def _tick(self):
        if self._done:
            return
        self.clock.setText(f"SESSION {fmt_clock(self._seconds)}" if self.kind == "shorts" else "")

    def _type(self):
        text = self.headline
        if self._typed < len(text):
            self._typed += 1
            self.title.setText(text[:self._typed] + "_")
        else:
            self._cursor_on = not self._cursor_on
            self.title.setText(text + ("_" if self._cursor_on else " "))

    def _finish(self, action: str):
        if self._done:
            return
        self._done = True
        self._type_timer.stop()
        self._tick_timer.stop()
        for b in (self.b_stop, self.b_more):
            b.setEnabled(False)
        if action == "stop":
            self.ring.set_mood("celebrate")
            self.title.setText("Nice. Back to it.")
            self.subtitle.setText("Good call. Closing it for you.")
            self.clock.setText("")
            hold = 1700
        else:
            hold = 0
        self.action.emit(action)
        QTimer.singleShot(hold, self._fade_out)

    def _fade_out(self):
        out = QPropertyAnimation(self, b"windowOpacity", self)
        out.setDuration(220)
        out.setStartValue(self.windowOpacity())
        out.setEndValue(0.0)
        out.finished.connect(self.close)
        out.start()
        self._out = out

    def closeEvent(self, e):
        if not self._done:
            self._done = True
            self.action.emit("dismiss")
        super().closeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._finish("dismiss")

    # ---- painting: soft shadow + paper card
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(SHADOW, SHADOW, self.width() - SHADOW * 2, self.height() - SHADOW * 2)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(SHADOW):
            p.setBrush(QColor(0, 0, 0, int(3.2 * (1 - i / SHADOW) ** 2 + 0.4)))
            p.drawRoundedRect(card.adjusted(-i, -i + 6, i, i + 6), 24 + i, 24 + i)
        p.setPen(QPen(QColor("#CFCDC6"), 1))
        p.setBrush(QColor(T.BG))
        p.drawRoundedRect(card, 24, 24)
        # faint dot grid in the corners
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(T.qc(T.INK, .08))
        for y in range(int(card.top()) + 70, int(card.bottom()) - 10, 12):
            for x in (int(card.left()) + 14, int(card.right()) - 14):
                p.drawEllipse(x, y, 2, 2)


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
        popup = NudgePopup(payload, self.cfg.get("extend_min"), self.cfg.get("pause_min"))
        popup.action.connect(lambda a, pl=payload: self.engine.resolve(pl, a))
        popup.destroyed.connect(lambda: setattr(self, "current", None) if self.current is popup else None)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.current = popup
        popup.present()
