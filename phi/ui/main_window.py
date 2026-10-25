"""Main window: frameless paper panel, animated sidebar, three pages."""
from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QSizeGrip, QStackedWidget, QVBoxLayout, QWidget

from . import theme as T
from .mascot import Mascot, WordMark, ghost_icon
from .motion import Spring, Ticker, burst, float_text
from .dashboard import ActivityPage, TodayPage
from .pages import Ctx, Page, SettingsPage, mk_label
from .widgets import animator, label_font_paint, run


def _grain() -> QPixmap:
    rng = random.Random(7)
    img = QImage(160, 160, QImage.Format.Format_ARGB32)
    for y in range(160):
        for x in range(160):
            a = rng.randint(0, 14)
            img.setPixelColor(x, y, QColor(0, 0, 0, a) if rng.random() < .5 else QColor(255, 255, 255, a))
    return QPixmap.fromImage(img)


# ------------------------------------------------------------------ sidebar
def _icon(p: QPainter, kind: str, cx: float, cy: float, c: QColor):
    p.setPen(QPen(c, 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "today":
        p.drawEllipse(QPointF(cx, cy), 6.5, 6.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(cx, cy), 2.4, 2.4)
    elif kind == "apps":
        for dx in (-5, 1):
            for dy in (-5, 1):
                p.drawRoundedRect(QRectF(cx + dx, cy + dy, 4.5, 4.5), 1, 1)
    else:
        for i, dy in enumerate((-4.5, 0, 4.5)):
            p.drawLine(QPointF(cx - 6.5, cy + dy), QPointF(cx + 6.5, cy + dy))
            p.setBrush(c)
            p.drawEllipse(QPointF(cx - 2.5 + i * 3, cy + dy), 1.9, 1.9)
            p.setBrush(Qt.BrushStyle.NoBrush)


class Sidebar(QWidget):
    ITEMS = [("today", "Today"), ("apps", "Activity"), ("settings", "Settings")]
    ROW_H, GAP, TOP = 40, 4, 92

    def __init__(self, on_select):
        super().__init__()
        self.setFixedWidth(212)
        self.on_select = on_select
        self.index = 0
        self._ys = Spring(float(self.TOP), 260.0, 21.0)      # the selection pill rides a spring
        self._hover = [0.0] * len(self.ITEMS)
        self._hover_idx = -1
        self.setMouseTracking(True)
        self._hv = animator(self, self._tick_hover, 140)
        self._tk = Ticker(self._spring_step)

        self.wordmark = WordMark(3.0, parent=self)
        self.wordmark.move(22, 26)
        self.panel = _MascotPanel(self)
        self.mascot = self.panel.mascot

    def resizeEvent(self, e):
        h = _MascotPanel.HEIGHT
        self.panel.setGeometry(14, self.height() - h - 14, self.width() - 28, h)

    def _row_y(self, i):
        return self.TOP + i * (self.ROW_H + self.GAP)

    @property
    def _y(self) -> float:
        return self._ys.x

    def _spring_step(self, dt: float) -> bool:
        self._ys.step(dt)
        self.update(0, 0, self.width(), self._row_y(len(self.ITEMS)) + 8)
        return self.isVisible() and not self._ys.resting

    def _tick_hover(self, v):
        for i in range(len(self._hover)):
            target = 1.0 if i == self._hover_idx else 0.0
            self._hover[i] += (target - self._hover[i]) * max(v, .15)
        self.update()

    def select(self, i: int, emit: bool = True):
        if i == self.index:
            return
        self.index = i
        self._ys.target = float(self._row_y(i))
        self._tk.wake()
        if emit:
            self.on_select(i)

    def _hit(self, pos) -> int:
        for i in range(len(self.ITEMS)):
            y = self._row_y(i)
            if 14 <= pos.x() <= self.width() - 14 and y <= pos.y() <= y + self.ROW_H:
                return i
        return -1

    def mouseMoveEvent(self, e):
        i = self._hit(e.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if i >= 0 else Qt.CursorShape.ArrowCursor)
        if i != self._hover_idx:
            self._hover_idx = i
            run(self._hv, 0, 1)

    def leaveEvent(self, e):
        self._hover_idx = -1
        run(self._hv, 0, 1)

    def mousePressEvent(self, e):
        i = self._hit(e.position())
        if i >= 0:
            self.select(i)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # hover plates
        for i in range(len(self.ITEMS)):
            if self._hover[i] > .02 and i != self.index:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(T.qc(T.SOFT, self._hover[i]))
                p.drawRoundedRect(QRectF(14, self._row_y(i), self.width() - 28, self.ROW_H), 11, 11)
        # selected pill: springs between rows and stretches a little while it travels
        stretch = min(7.0, abs(self._ys.v) * 0.012)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.INK))
        p.drawRoundedRect(QRectF(14, self._y - stretch / 2, self.width() - 28, self.ROW_H + stretch), 11, 11)
        for i, (kind, text) in enumerate(self.ITEMS):
            y = self._row_y(i)
            near = max(0.0, 1 - abs(y - self._y) / (self.ROW_H + self.GAP))
            col = T.mix(T.INK, T.PAPER, near)
            _icon(p, kind, 38, y + self.ROW_H / 2, col)
            label_font_paint(p, QRectF(58, y, 140, self.ROW_H), text, T.sans(14, T.QFont.Weight.Medium if near > .5 else T.QFont.Weight.Normal), col)
        # selected marker: tiny red LED
        p.setBrush(QColor(T.RED))
        p.drawEllipse(QPointF(self.width() - 28, self._y + self.ROW_H / 2), 2.4, 2.4)


class _MascotPanel(QWidget):
    """Home of the sidebar mascot. The card is painted once into a pixmap, so 60 fps mascot frames stay cheap."""
    HEIGHT = 204

    def __init__(self, parent):
        super().__init__(parent)
        self.mascot = Mascot(px=4, mood="monitoring", fill=T.PAPER, parent=self)
        self._bg: QPixmap | None = None
        self._bg_key = None

    def resizeEvent(self, e):
        self.mascot.move((self.width() - self.mascot.width()) // 2, 6)

    def _background(self) -> QPixmap:
        dpr = self.devicePixelRatioF()
        key = (self.width(), self.height(), dpr)
        if self._bg_key != key:
            pm = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.setPen(QPen(QColor(T.LINE), 1))
            p.setBrush(QColor(T.SURFACE))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 14, 14)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.qc(T.INK, .10))
            for y in range(10, self.height() - 6, 10):
                for x in range(10, self.width() - 6, 10):
                    p.drawEllipse(QPointF(x, y), .9, .9)
            label_font_paint(p, QRectF(0, self.height() - 44, self.width(), 14), "SMALL SCROLLS", T.mono(9, spacing=1.6), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            label_font_paint(p, QRectF(0, self.height() - 30, self.width(), 14), "BIG LOSSES_", T.mono(9, T.QFont.Weight.Medium, 1.6), T.INK, Qt.AlignmentFlag.AlignCenter)
            p.end()
            self._bg, self._bg_key = pm, key
        return self._bg

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setClipRegion(ev.region())
        p.drawPixmap(0, 0, self._background())


# ------------------------------------------------------------------ title bar
class CaptionButton(QWidget):
    def __init__(self, kind: str, action):
        super().__init__()
        self.kind, self.action, self._hover = kind, action, 0.0
        self.setFixedSize(36, 28)
        self._a = animator(self, self._set, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _set(self, v):
        self._hover = v
        self.update()

    def enterEvent(self, e):
        run(self._a, self._hover, 1)

    def leaveEvent(self, e):
        run(self._a, self._hover, 0)

    def mousePressEvent(self, e):
        self.action()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        close = self.kind == "close"
        if self._hover > .01:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(T.qc(T.RED if close else T.SOFT, self._hover))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(3, 2, -3, -2), 7, 7)
        c = T.mix(T.GRAY, T.PAPER if close else T.INK, self._hover)
        p.setPen(QPen(c, 1.3))
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "min":
            p.drawLine(QPointF(cx - 4.5, cy), QPointF(cx + 4.5, cy))
        elif self.kind == "max":
            p.drawRect(QRectF(cx - 4.5, cy - 4.5, 9, 9))
        else:
            p.drawLine(QPointF(cx - 4.5, cy - 4.5), QPointF(cx + 4.5, cy + 4.5))
            p.drawLine(QPointF(cx - 4.5, cy + 4.5), QPointF(cx + 4.5, cy - 4.5))


class TitleBar(QWidget):
    def __init__(self, win: "MainWindow"):
        super().__init__()
        self.win = win
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 6, 10, 0)
        lay.setSpacing(0)
        lay.addWidget(mk_label("•••", T.mono(11, spacing=2), T.GRAY))
        lay.addStretch(1)
        lay.addWidget(CaptionButton("min", win.showMinimized))
        lay.addWidget(CaptionButton("max", win.toggle_max))
        lay.addWidget(CaptionButton("close", win.hide))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.win.windowHandle():
            self.win.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e):
        self.win.toggle_max()


# ------------------------------------------------------------------ window
class MainWindow(QWidget):
    def __init__(self, ctx: Ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("PHI")
        self.setWindowIcon(ghost_icon())
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(900, 640)
        self.resize(1060, 720)
        self._grain = _grain()
        self._shown_once = self._was_hidden = False

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)
        self._build()

        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._refresh)
        ctx.engine.snapshot.connect(self.on_snapshot)
        self._celebrating = False
        ctx.engine.celebrated.connect(self._celebrate)
        self._refresh()

    # ---- construction (also re-run when the theme changes)
    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)
        self.sidebar = Sidebar(self._go)
        root.addWidget(self.sidebar)
        right = QVBoxLayout()
        right.setSpacing(0)
        self.titlebar = TitleBar(self)
        right.addWidget(self.titlebar)
        self.stack = QStackedWidget()
        self.pages: list[Page] = [TodayPage(self.ctx), ActivityPage(self.ctx), SettingsPage(self.ctx)]
        for pg in self.pages:
            self.stack.addWidget(pg)
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)
        self._grip.raise_()

    def retheme(self) -> None:
        """Rebuild every widget with the new colours, staying on the same page."""
        idx = self.stack.currentIndex()
        def clear(layout) -> None:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().hide()
                    item.widget().deleteLater()
                elif item.layout():
                    clear(item.layout())

        old = self.layout()
        clear(old)
        QWidget().setLayout(old)                      # detach the emptied layout so a fresh one can be installed
        self._build()
        self.stack.setCurrentIndex(idx)
        self.sidebar.select(idx, emit=False)
        for w in (self.sidebar, self.titlebar, self.stack):
            w.show()
        self._refresh()
        self.pages[idx].enter()
        self.update()

    # ---- behaviour
    def toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def showEvent(self, e):
        first = not self._shown_once
        self._shown_once = True
        self._timer.start()
        self._refresh()
        self.sidebar.mascot.resume()
        super().showEvent(e)
        if first or self._was_hidden:
            QTimer.singleShot(0, self.pages[self.stack.currentIndex()].enter)
        self._was_hidden = False

    def hideEvent(self, e):
        self._timer.stop()
        self.sidebar.mascot.pause()                 # nothing animates while PHI sits in the tray
        self._was_hidden = True
        super().hideEvent(e)

    def _refresh(self):
        self.pages[self.stack.currentIndex()].refresh()

    def _go(self, i: int):
        """Switch pages instantly, then let the page animate itself in.

        The old cross-fade re-rendered the whole page every frame (about 20 ms), which dropped frames; staggering
        the contents in costs almost nothing and reads as more alive.
        """
        self.stack.setCurrentIndex(i)
        page = self.stack.currentWidget()
        page.refresh()
        page.enter()

    def _celebrate(self):
        self._celebrating = True
        self.sidebar.mascot.set_mood("celebrate")
        mp = self.sidebar.panel
        burst(mp, "confetti", QPointF(mp.width() / 2, 70))
        float_text(mp, "+1 STOPPED", QPointF(mp.width() / 2, 30))
        QTimer.singleShot(3000, self._end_celebrate)

    def _end_celebrate(self):
        self._celebrating = False

    def on_snapshot(self, snap: dict):
        if not self._celebrating:
            self.sidebar.mascot.set_mood("monitoring" if snap["mood"] == "monitoring" else snap["mood"])
        if self.isVisible():
            self.pages[0].update_status(snap)

    # ---- painting
    def resizeEvent(self, e):
        self._grip.move(self.width() - 18, self.height() - 18)
        super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = 0 if self.isMaximized() else 16
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), radius, radius)
        p.fillPath(path, QColor(T.BG))
        p.save()
        p.setClipPath(path)
        p.drawTiledPixmap(self.rect(), self._grain)
        # sidebar hairline
        p.fillRect(QRectF(212, 0, 1, self.height()), QColor(T.LINE))
        p.restore()
        p.setPen(QPen(QColor(T.EDGE), 1))
        p.drawPath(path)
