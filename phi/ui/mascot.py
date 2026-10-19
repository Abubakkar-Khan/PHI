"""PHI's companion: a tiny dithered-pixel ghost with headphones, plus the dot-matrix wordmark."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme as T

# ---- sprite data -------------------------------------------------------------
BODY = [
    "....########....",
    "..############..",
    ".##############.",
] + ["################"] * 9
FEET = {"A": "##.####..####.##"[:16], "B": "#.####.##.####.#"[:16]}
BODY_OFFSET = (1, 2)

HEADPHONES = [
    ".....HHHHHHHH.....",
    "...HHH......HHH...",
    "..HH..........HH..",
    "..H............H..",
    ".HH............HH.",
    "HH..............HH",
    "HH..............HH",
    "HH..............HH",
    "HH..............HH",
]

GRID_W, GRID_H = 24, 19
SPRITE_OFFSET = (3, 3)

_cell_cache: dict[str, tuple[list, list]] = {}


def _body_cells(feet: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    if feet in _cell_cache:
        return _cell_cache[feet]
    rows = BODY + [FEET[feet]]
    filled = {(x + BODY_OFFSET[0], y + BODY_OFFSET[1])
              for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == "#"}
    outline, inside = [], []
    for (x, y) in filled:
        edge = any((x + dx, y + dy) not in filled for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        (outline if edge else inside).append((x, y))
    _cell_cache[feet] = (outline, inside)
    return outline, inside


_HP = [(x, y) for y, row in enumerate(HEADPHONES) for x, ch in enumerate(row) if ch == "H"]
_Z = [(0, 0), (1, 0), (2, 0), (1, 1), (0, 2), (1, 2), (2, 2)]


def build_cells(mood: str, n: int, fill: str = T.PAPER) -> list[tuple[float, float, QColor]]:
    """Return (gridX, gridY, colour) for one animation frame. Pure function: easy to test."""
    ink, red = QColor(T.INK), QColor(T.RED)
    out: list[tuple[float, float, QColor]] = []
    ox, oy = SPRITE_OFFSET

    bob = dx = 0
    look = 0
    feet = "A"
    if mood == "idle":
        bob = -1 if (n // 10) % 2 else 0
    elif mood == "monitoring":
        bob = -1 if (n // 12) % 2 else 0
        look = [0, 0, 1, 1, 1, 0, 0, -1, -1, -1][(n // 5) % 10]
    elif mood == "alert":
        dx = 1 if (n // 2) % 2 else 0
        feet = "A" if (n // 3) % 2 else "B"
    elif mood == "celebrate":
        bob = [0, -2, -4, -5, -4, -2, 0, 0][n % 8]
        feet = "A" if (n // 2) % 2 else "B"
    elif mood == "sleep":
        bob = 1 if (n // 16) % 2 else 0

    sx, sy = ox + dx, oy + bob

    # dithered ground shadow
    lift = -bob if bob < 0 else 0
    half = 5 - (1 if lift > 2 else 0)
    for x in range(12 - half, 12 + half):
        if x % 2 == 0:
            out.append((x, GRID_H - 1, T.qc(T.INK, 0.28)))

    outline, inside = _body_cells(feet)
    fill_c = QColor(fill)
    out += [(sx + x, sy + y, fill_c) for x, y in inside]
    out += [(sx + x, sy + y, ink) for x, y in outline]
    out += [(sx + x, sy + y, ink) for x, y in _HP]

    # headphone LED: the tiny red detail
    if mood != "sleep" and (n // 6) % 2 == 0:
        out.append((sx + 17, sy + 6, red))

    # face (sprite coords: eyes y=7..8, left x=6, right x=10)
    blink = mood in ("idle", "monitoring") and n % 52 in (50, 51)
    ex = look
    if mood == "celebrate":
        for x0 in (5, 10):
            for cx, cy in ((x0, 8), (x0 + 1, 7), (x0 + 2, 8)):
                out.append((sx + cx, sy + cy, ink))
        for cx, cy in ((6, 10), (7, 11), (8, 11), (9, 11), (10, 11), (11, 10)):
            out.append((sx + cx, sy + cy, ink))
    elif mood == "sleep":
        for x0 in (6, 10):
            out += [(sx + x0, sy + 8, ink), (sx + x0 + 1, sy + 8, ink)]
        out += [(sx + 8, sy + 10, ink), (sx + 9, sy + 10, ink)]
    elif mood == "alert":
        for x0 in (6, 10):
            for cy in (6, 7, 8):
                out += [(sx + x0, sy + cy, ink), (sx + x0 + 1, sy + cy, ink)]
        for cx, cy in ((8, 10), (9, 10), (8, 11), (9, 11)):
            out.append((sx + cx, sy + cy, ink))
    else:
        rows = (8,) if blink else (7, 8)
        for x0 in (6, 10):
            for cy in rows:
                out += [(sx + x0 + ex, sy + cy, ink), (sx + x0 + 1 + ex, sy + cy, ink)]
        if mood == "monitoring":
            out += [(sx + 8, sy + 10, ink), (sx + 9, sy + 10, ink)]
        else:
            for cx, cy in ((7, 10), (8, 11), (9, 11), (10, 10)):
                out.append((sx + cx, sy + cy, ink))

    if mood == "alert" and (n // 5) % 3 != 2:
        for cy in (0, 1, 2, 3, 5):
            out.append((ox + 19 + dx, oy + cy, red))

    if mood == "celebrate":
        for i in range(12):
            x = (i * 37 + 5) % GRID_W
            y = int((n * 0.7 + i * 5) % (GRID_H - 1))
            out.append((x, y, red if i % 3 == 0 else ink))

    if mood == "sleep":
        zy = 7 - (n // 8) % 4
        for cx, cy in _Z:
            out.append((20 + cx, zy + cy, T.qc(T.GRAY, 0.9)))
    return out


# ---- widgets -------------------------------------------------------------------
class Mascot(QWidget):
    """Animated pixel companion. mood: idle | monitoring | alert | celebrate | sleep."""

    FPS_MS = 80

    def __init__(self, px: int = 6, mood: str = "idle", fill: str = T.PAPER, parent=None):
        super().__init__(parent)
        self._px, self._mood, self._fill, self._n = px, mood, fill, 0
        self.setFixedSize(GRID_W * px, GRID_H * px)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._timer = QTimer(self)
        self._timer.setInterval(self.FPS_MS)
        self._timer.timeout.connect(self._advance)

    @property
    def mood(self) -> str:
        return self._mood

    def set_mood(self, mood: str) -> None:
        if mood != self._mood:
            self._mood, self._n = mood, 0
            self.update()

    def _advance(self) -> None:
        self._n += 1
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        px = self._px
        for x, y, c in build_cells(self._mood, self._n, self._fill):
            p.fillRect(QRectF(x * px, y * px, px, px), c)


class RingMascot(QWidget):
    """The mascot inside a slowly rotating dotted ring (used by the popup)."""

    def __init__(self, size: int = 230, px: int = 6, mood: str = "alert", parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._phase = 0.0
        self._mood = mood
        self.mascot = Mascot(px=px, mood=mood, parent=self)
        self.mascot.move((size - self.mascot.width()) // 2, (size - self.mascot.height()) // 2 + 6)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._spin)

    def set_mood(self, mood: str) -> None:
        self._mood = mood
        self.mascot.set_mood(mood)

    def _spin(self) -> None:
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.width() / 2 - 6
        n = 72
        for i in range(n):
            a = 2 * math.pi * i / n - math.pi / 2
            lead = ((i / n) - self._phase) % 1.0   # 0 = head of the sweep
            tail = 1.0 - lead
            glow = max(0.0, 1.0 - tail * 5.0) if tail < 0.2 else 0.0
            col = T.mix(T.qc(T.INK, 0.42), T.qc(T.INK, 1.0), glow)
            size = 1.2 + glow * 1.5
            if self._mood == "alert" and i == 0:
                col, size = QColor(T.RED), 3.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawEllipse(QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a)), size, size)


GLYPHS = {
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"],
    "_": [".....", ".....", ".....", ".....", ".....", ".....", "#####"],
}


class WordMark(QWidget):
    """PHI_ in dot-matrix letters, with a blinking red cursor."""

    def __init__(self, dot: float = 3.0, text: str = "PHI_", parent=None):
        super().__init__(parent)
        self._dot, self._text = dot, text
        self._on = True
        step = dot * 2.2
        self.setFixedSize(int(len(text) * 6 * step), int(7 * step) + 2)
        self._timer = QTimer(self)
        self._timer.setInterval(560)
        self._timer.timeout.connect(self._blink)

    def _blink(self):
        self._on = not self._on
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        step = self._dot * 2.2
        for gi, ch in enumerate(self._text):
            glyph = GLYPHS[ch]
            for y, row in enumerate(glyph):
                for x, v in enumerate(row):
                    if v != "#":
                        continue
                    cursor = ch == "_"
                    if cursor and not self._on:
                        continue
                    p.setBrush(QColor(T.RED if cursor else T.INK))
                    p.drawEllipse(QPointF((gi * 6 + x) * step + step / 2, y * step + step / 2 + 1), self._dot * 0.8, self._dot * 0.8)


def ghost_icon(mood: str = "idle", size: int = 64) -> QIcon:
    """Static render of the ghost for the tray and window icon."""
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    cells = build_cells(mood, 0, T.PAPER)
    cells = [c for c in cells if c[1] < GRID_H - 1]  # drop shadow row
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    x0, y0 = min(xs), min(ys)
    w, h = max(xs) - x0 + 1, max(ys) - y0 + 1
    px = max(1, int(size // max(w, h)))
    offx, offy = (size - w * px) // 2, (size - h * px) // 2
    for x, y, c in cells:
        if mood == "sleep" and c.red() == 0xE5 and c.green() == 0x39:
            continue
        p.fillRect(QRectF(offx + (x - x0) * px, offy + (y - y0) * px, px, px), c)
    p.end()
    return QIcon(pm)
