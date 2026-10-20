"""Lockdown: a full-screen takeover that cannot be clicked away.

- Appears the moment Shorts is detected (hard cut, siren, marching hazard bands, decoding headline).
- Covers every monitor, swallows mouse and keyboard, re-claims focus if it is lost, ignores Alt+F4/Esc.
- No close button. A countdown closes Shorts for you when it ends, so the lock can never become permanent.
- The only way to buy time is to HOLD a button for several seconds (longer each time PHI has to ask again).
"""
from __future__ import annotations

import random
import sys
import threading

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ..utils import fmt_clock, fmt_dur, minutes_text
from . import theme as T
from .mascot import RingMascot
from .pages import mk_label

DARK = QColor(14, 13, 13)
ARM_SECONDS = 2          # buttons are dead for this long after the lock appears
GLYPHS = "#%&@$▓░▒/\\<>"


def siren() -> None:
    if sys.platform != "win32":
        return

    def play():
        try:
            import winsound
            for _ in range(3):
                winsound.Beep(1046, 140)
                winsound.Beep(698, 140)
            winsound.Beep(523, 320)
        except Exception:
            pass
    threading.Thread(target=play, daemon=True).start()


def _hazard(p: QPainter, rect: QRectF, offset: float) -> None:
    p.save()
    p.setClipRect(rect)
    p.fillRect(rect, QColor(T.INK))
    h, w = rect.height(), rect.height()
    x = rect.left() - 2 * w + offset
    while x < rect.right() + w:
        poly = QPainterPath()
        poly.moveTo(x, rect.bottom())
        poly.lineTo(x + w, rect.bottom())
        poly.lineTo(x + w + h, rect.top())
        poly.lineTo(x + h, rect.top())
        poly.closeSubpath()
        p.fillPath(poly, QColor(T.RED))
        x += w * 2
    p.restore()


class Cover(QWidget):
    """Plain black blocker for the other monitors."""

    def __init__(self, geometry):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setGeometry(geometry)
        self._off = 0.0

    def march(self, off: float) -> None:
        self._off = off
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), DARK)
        _hazard(p, QRectF(0, 0, self.width(), 34), self._off)
        _hazard(p, QRectF(0, self.height() - 34, self.width(), 34), -self._off)


class HoldButton(QWidget):
    """Must be pressed and held; letting go drains the progress."""
    confirmed = Signal()

    def __init__(self, text: str, seconds: float):
        super().__init__()
        self.label, self.seconds = text, seconds
        self.setFixedSize(340, 58)
        self._p, self._holding, self._armed, self._fired = 0.0, False, False, False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._t = QTimer(self)
        self._t.setInterval(16)
        self._t.timeout.connect(self._step)

    def arm(self, on: bool) -> None:
        self._armed = on
        self.update()

    def mousePressEvent(self, e):
        if self._armed and not self._fired:
            self._holding = True
            self._t.start()

    def mouseReleaseEvent(self, e):
        self._holding = False

    def _step(self):
        self._p += (0.016 / self.seconds) if self._holding else -0.06
        if self._p >= 1.0 and not self._fired:
            self._fired = True
            self._t.stop()
            self.confirmed.emit()
        elif self._p <= 0:
            self._p = 0.0
            if not self._holding:
                self._t.stop()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, QColor(30, 28, 28))
        p.save()
        p.setClipPath(path)
        p.fillRect(QRectF(r.left(), r.top(), r.width() * min(1.0, self._p), r.height()), QColor(T.RED))
        p.restore()
        p.setPen(QPen(QColor(90, 86, 84) if not self._armed else QColor(T.GRAY), 1.2))
        p.drawPath(path)
        left = max(0.0, self.seconds * (1 - self._p))
        text = self.label if self._p <= 0.01 else f"KEEP HOLDING  {left:.1f}s"
        p.setFont(T.mono(12, T.QFont.Weight.Bold, 1.2))
        p.setPen(QColor(T.PAPER) if self._armed else QColor(110, 106, 104))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), text)


class SolidButton(QWidget):
    clicked = Signal()

    def __init__(self, text: str):
        super().__init__()
        self.text = text
        self.setFixedSize(340, 64)
        self._armed, self._hover, self._down = False, False, False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def arm(self, on: bool) -> None:
        self._armed = on
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        self._down = self._armed

    def mouseReleaseEvent(self, e):
        if self._down and self._armed and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        self._down = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self._down:
            r.translate(0, 1)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.PAPER) if self._armed else QColor(48, 45, 44))
        if self._armed and self._hover:
            p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setFont(T.sans(16, T.QFont.Weight.Bold))
        p.setPen(QColor(T.INK) if self._armed else QColor(110, 106, 104))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), self.text)


class LockScreen(QWidget):
    action = Signal(str)   # stop | more

    TITLES = {
        "shorts": [["SHORTS: LOCKED.", "NOT NOW."], ["AGAIN?!", "NO."], ["YOU KNOW THE DRILL."]],
        "daily": [["DAILY LIMIT HIT.", "THAT'S ENOUGH."], ["STILL HERE?!"], ["NO MORE TODAY."]],
        "site": [["LIMIT HIT.", "TIME'S UP."], ["AGAIN?!"], ["GO DO SOMETHING."]],
    }

    def __init__(self, payload: dict, extend_min: int, lock_seconds: int):
        super().__init__()
        self.payload = payload
        self.kind = payload["kind"]
        self.repeat = max(1, int(payload.get("repeat", 1)))
        self._seconds = payload["seconds"]
        self._remaining = min(40, lock_seconds + 5 * (self.repeat - 1))
        self._hold = min(15, 5 + 3 * (self.repeat - 1))
        self._elapsed = 0.0
        self._off = 0.0
        self._done = False
        self._allow_close = False
        self._typed = 0
        self.covers: list[Cover] = []

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._screen = screen
        self.setGeometry(screen.geometry())

        tiers = self.TITLES[self.kind]
        self.headline = random.choice(tiers[min(self.repeat, len(tiers)) - 1])
        label = payload["label"]
        if self.kind == "shorts":
            self.sub = ("Shorts opened. You set this limit yourself." if self._seconds < 60
                        else f"{minutes_text(self._seconds)} of Shorts. You set this limit yourself.")
            stop_text = "CLOSE SHORTS NOW"
        elif self.kind == "daily":
            self.sub = f"{minutes_text(self._seconds)} of Shorts today. You set this limit yourself."
            stop_text = "CLOSE SHORTS NOW"
        else:
            self.sub = f"{minutes_text(self._seconds)} on {label} today. You set this limit yourself."
            stop_text = f"CLOSE {label.upper()} NOW"
        facts = [f"TODAY {fmt_dur(payload.get('today_s', self._seconds))}"]
        if payload.get("count"):
            facts.append(f"{payload['count']} SHORTS WATCHED")
        facts.append(f"LOCK #{self.repeat}")
        self.facts_text = "   ·   ".join(facts)

        k = min(1.0, screen.geometry().height() / 1000)   # shrink on small screens
        root = QVBoxLayout(self)
        root.setContentsMargins(0, int(70 * k), 0, int(60 * k))
        root.setSpacing(0)
        root.addStretch(1)

        def center(widget, space_after=0):
            root.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
            if space_after:
                root.addSpacing(space_after)

        status = mk_label("● PHI_ LOCKDOWN", T.mono(13, T.QFont.Weight.Bold, 3), T.RED, Qt.AlignmentFlag.AlignHCenter)
        center(status, 10)
        self.ring = RingMascot(int(250 * k), 4 if k > .9 else 3, "alert", dark=True)
        center(self.ring, 6)
        self.title = mk_label("", T.sans(int(78 * k), T.QFont.Weight.Black), T.PAPER, Qt.AlignmentFlag.AlignHCenter)
        center(self.title, 0)
        center(mk_label(self.sub, T.sans(19), "#A9A5A2", Qt.AlignmentFlag.AlignHCenter), 8)
        center(mk_label(self.facts_text, T.mono(12, T.QFont.Weight.Medium, 1.6), "#D8D4D0", Qt.AlignmentFlag.AlignHCenter), 22)
        center(mk_label("CLOSING FOR YOU IN", T.mono(12, T.QFont.Weight.Bold, 3), "#8C8884", Qt.AlignmentFlag.AlignHCenter), 0)
        self.count = mk_label("", T.mono(int(120 * k), T.QFont.Weight.Black), T.RED, Qt.AlignmentFlag.AlignHCenter)
        center(self.count, 14)

        row = QHBoxLayout()
        row.setSpacing(18)
        row.addStretch(1)
        self.b_stop = SolidButton(stop_text)
        self.b_more = HoldButton(f"HOLD {self._hold}s  ·  {extend_min} MORE MIN", self._hold)
        self.b_stop.clicked.connect(lambda: self._finish("stop"))
        self.b_more.confirmed.connect(lambda: self._finish("more"))
        row.addWidget(self.b_stop)
        row.addWidget(self.b_more)
        row.addStretch(1)
        root.addLayout(row)
        self.arm_note = mk_label("", T.mono(11, T.QFont.Weight.Medium, 2), "#8C8884", Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(10)
        root.addWidget(self.arm_note)
        root.addStretch(1)

        self._decode = QTimer(self)
        self._decode.setInterval(30)
        self._decode.timeout.connect(self._decode_step)
        self._second = QTimer(self)
        self._second.setInterval(1000)
        self._second.timeout.connect(self._tick_second)
        self._frame = QTimer(self)
        self._frame.setInterval(50)
        self._frame.timeout.connect(self._tick_frame)

    # ---- lifecycle ---------------------------------------------------------
    def present(self) -> None:
        for s in QGuiApplication.screens():
            if s is not self._screen:
                c = Cover(s.geometry())
                c.show()
                self.covers.append(c)
        self.b_stop.arm(False)
        self.b_more.arm(False)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        siren()
        self._decode.start()
        self._second.start()
        self._frame.start()
        self._refresh_text()

    def update_seconds(self, seconds: float) -> None:
        self._seconds = seconds

    def _refresh_text(self) -> None:
        self.count.setText(f"{self._remaining:02d}" if self._remaining >= 10 else f"{self._remaining}")
        if self._elapsed < ARM_SECONDS:
            self.arm_note.setText(f"ARMING...  {max(1, int(ARM_SECONDS - self._elapsed + 0.99))}")
        else:
            self.arm_note.setText("NOTHING ELSE ON THIS SCREEN IS CLICKABLE")

    def _decode_step(self) -> None:
        n = len(self.headline)
        self._typed += 1
        shown = self.headline[:self._typed // 1]
        rest = "".join(random.choice(GLYPHS) if ch != " " else " " for ch in self.headline[len(shown):])
        self.title.setText(shown + rest)
        if self._typed >= n:
            self.title.setText(self.headline)
            self._decode.stop()

    def _tick_second(self) -> None:
        if self._done:
            return
        self._elapsed += 1
        self._remaining -= 1
        if self._elapsed >= ARM_SECONDS:
            self.b_stop.arm(True)
            self.b_more.arm(True)
        if self._remaining <= 0:
            self._finish("stop")
            return
        self._refresh_text()

    def _tick_frame(self) -> None:
        """Marching hazard bands + keep the lock on top and focused."""
        self._off = (self._off + 3.0) % 120
        self.update()
        for c in self.covers:
            c.march(self._off)
        if not self.isActiveWindow():
            self.raise_()
            self.activateWindow()

    def _finish(self, action: str) -> None:
        if self._done:
            return
        self._done = True
        for t in (self._decode, self._second, self._frame):
            t.stop()
        self.action.emit(action)
        self._allow_close = True
        for c in self.covers:
            c.close()
        self.close()

    # ---- input is swallowed ---------------------------------------------------
    def keyPressEvent(self, e):
        e.accept()

    def keyReleaseEvent(self, e):
        e.accept()

    def closeEvent(self, e):
        if not self._allow_close:
            e.ignore()      # Alt+F4 and friends do nothing
            return
        super().closeEvent(e)

    def mousePressEvent(self, e):
        e.accept()

    def contextMenuEvent(self, e):
        e.accept()

    # ---- painting ---------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), DARK)
        # faint dot grid + a red glow rising from the bottom
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 14))
        for y in range(60, self.height() - 40, 28):
            for x in range(14, self.width(), 28):
                p.drawEllipse(QPointF(x, y), 1.0, 1.0)
        _hazard(p, QRectF(0, 0, self.width(), 40), self._off)
        _hazard(p, QRectF(0, self.height() - 40, self.width(), 40), -self._off)
