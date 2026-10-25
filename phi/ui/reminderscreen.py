"""Full-screen reminder / alarm. Calm compared with the Shorts lock: themed, easy to answer, hard to miss."""
from __future__ import annotations

import sys
import threading
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget

from . import theme as T
from .lockscreen import Cover, SolidButton
from .mascot import RingMascot
from .pages import mk_label


def chime() -> None:
    """Two soft rising tones, off the UI thread."""
    if sys.platform != "win32":
        return

    def play():
        try:
            import winsound
            winsound.Beep(659, 160)
            winsound.Beep(880, 280)
        except Exception:
            pass
    threading.Thread(target=play, daemon=True).start()


class GhostButton(QWidget):
    clicked = Signal()

    def __init__(self, text: str):
        super().__init__()
        self.text, self._hover, self._down = text, False, False
        self.setFixedSize(300, 64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mousePressEvent(self, e):
        self._down = True

    def mouseReleaseEvent(self, e):
        if self._down and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        self._down = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self._down:
            r.translate(0, 1)
        p.setPen(QPen(QColor(T.INK if self._hover else T.EDGE), 1.5))
        p.setBrush(QColor(T.SOFT) if self._hover else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setFont(T.sans(16, T.QFont.Weight.Bold))
        p.setPen(QColor(T.INK))
        p.drawText(r, int(Qt.AlignmentFlag.AlignCenter), self.text)


class ReminderScreen(QWidget):
    answered = Signal(str)     # done | snooze

    def __init__(self, item: dict, snooze_min: int):
        super().__init__()
        self.item = item
        self._snooze = snooze_min
        self._done = False
        self._allow_close = False
        self.covers: list[Cover] = []
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._screen = screen
        self.setGeometry(screen.geometry())

        k = min(1.0, screen.geometry().height() / 1000)
        message = (item.get("message") or "Take a break").strip()
        size = 96 if len(message) <= 18 else 72 if len(message) <= 36 else 52
        root = QVBoxLayout(self)
        root.setContentsMargins(int(120 * k), int(60 * k), int(120 * k), int(60 * k))
        root.addStretch(1)

        def center(widget, after=0):
            root.addWidget(widget, 0, Qt.AlignmentFlag.AlignHCenter)
            if after:
                root.addSpacing(after)

        center(mk_label("● PHI_ REMINDER", T.mono(13, T.QFont.Weight.Bold, 3), T.RED, Qt.AlignmentFlag.AlignHCenter), 10)
        self.ring = RingMascot(int(230 * k), 4 if k > .9 else 3, "monitoring", dark=True)
        center(self.ring, 10)
        self.title = mk_label(message, T.sans(int(size * k), T.QFont.Weight.Black), T.INK, Qt.AlignmentFlag.AlignHCenter)
        self.title.setWordWrap(True)
        width = min(screen.geometry().width() - int(240 * k), 1500)
        needed = QFontMetrics(self.title.font()).boundingRect(0, 0, width, 4000, int(Qt.TextFlag.TextWordWrap), message)
        self.title.setFixedSize(width, needed.height() + 24)      # a wrapped label otherwise gets clipped
        root.addWidget(self.title, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addSpacing(10)
        when = (f"EVERY {item.get('every_min', 30)} MIN" if item.get("mode") != "daily" else f"DAILY AT {item.get('time', '')}")
        center(mk_label(f"{datetime.now().strftime('%H:%M')}   ·   {when}", T.mono(15, T.QFont.Weight.Medium, 3), T.GRAY,
                        Qt.AlignmentFlag.AlignHCenter), int(40 * k))

        row = QHBoxLayout()
        row.setSpacing(18)
        row.addStretch(1)
        done = SolidButton("DONE")
        done.arm(True)
        done.clicked.connect(lambda: self._finish("done"))
        snooze = GhostButton(f"SNOOZE {snooze_min} MIN")
        snooze.clicked.connect(lambda: self._finish("snooze"))
        row.addWidget(done)
        row.addWidget(snooze)
        row.addStretch(1)
        root.addLayout(row)
        root.addSpacing(14)
        root.addWidget(mk_label("ESC = DONE", T.mono(11, T.QFont.Weight.Medium, 2), T.GRAY, Qt.AlignmentFlag.AlignHCenter))
        root.addStretch(1)

        self._keep = QTimer(self)
        self._keep.setInterval(500)
        self._keep.timeout.connect(self._claim)

    def present(self) -> None:
        for s in QGuiApplication.screens():
            if s is not self._screen:
                c = Cover(s.geometry())
                c.show()
                self.covers.append(c)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        if self.item.get("sound", True):
            chime()
        self._keep.start()

    def _claim(self) -> None:
        if not self.isActiveWindow():
            self.raise_()
            self.activateWindow()

    def _finish(self, action: str) -> None:
        if self._done:
            return
        self._done = True
        self._keep.stop()
        self.answered.emit(action)
        self._allow_close = True
        for c in self.covers:
            c.close()
        self.close()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish("done")
        e.accept()

    def closeEvent(self, e):
        if not self._allow_close:
            e.ignore()
            return
        super().closeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T.BG))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(T.qc(T.INK, .06))
        for y in range(40, self.height() - 20, 28):
            for x in range(14, self.width(), 28):
                p.drawEllipse(x, y, 2, 2)
        p.fillRect(QRectF(0, 0, self.width(), 8), QColor(T.RED))
        p.fillRect(QRectF(0, self.height() - 8, self.width(), 8), QColor(T.RED))


class ReminderController:
    def __init__(self, scheduler, cfg):
        self.scheduler, self.cfg = scheduler, cfg
        self.current: ReminderScreen | None = None
        scheduler.due.connect(self.show)

    def show(self, item: dict) -> None:
        snooze = int(self.cfg.get("reminder_snooze_min"))
        screen = ReminderScreen(item, snooze)
        screen.answered.connect(lambda a, it=item: self.scheduler.finish(it, snooze if a == "snooze" else 0))
        screen.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.current = screen
        screen.present()
