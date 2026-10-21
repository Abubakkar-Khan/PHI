"""PHI's companion: a pixel-art nerd with wild hair, big square glasses and one orange plus.

How it stays smooth and cheap
- The sprite is five layers (skin, outline, hair, glasses, antennae) pre-rendered once per scale, then
  blitted at whole device pixels, so edges stay crisp while motion is smooth.
- Motion is physical: springs for squash, hair, antennae and glasses; a tiny hop simulation; eased eyes.
- A frame is only repainted when the quantised pose actually changed, so a calm mascot costs almost nothing.
- Everything runs off the shared clock in motion.py and stops completely while the widget is hidden.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from . import theme as T
from .motion import Smooth, Spring, Ticker, clamp, float_text

MOODS = ("idle", "monitoring", "alert", "celebrate", "sleep")

# ---- sprite geometry (cells) --------------------------------------------------------------------
SW, SH = 32, 30            # the sprite itself
OX, OY = 3, 6              # sprite origin inside the canvas (headroom for hops, room right for sparks)
GRID_W, GRID_H = SW + 2 * OX, OY + SH + 1   # the last row is the ground shadow

EYE_L, EYE_R = 11.0, 21.0  # lens centres
EYE_BOTTOM = 23.0
HI = "#3A3A3A"             # hair highlight
GLINT = "#8E8C86"
SWEAT = "#8FB8DE"
HOP_G = 62.0               # gravity for hops, in cells/s^2


# ---- sprite data (built once from spans; verified against the reference art) ---------------------
def _grid() -> list[list[str]]:
    return [["."] * SW for _ in range(SH)]


def _span(g, row: int, *runs: tuple[int, int], ch: str = "#") -> None:
    for a, b in runs:
        for c in range(a, b + 1):
            g[row][c] = ch


def _build() -> dict[str, list[list[str]]]:
    skin = _grid()
    for r in range(8, 19):
        _span(skin, r, (6, 26))
    for r in range(19, 25):
        _span(skin, r, (7, 24))
    for r in (21, 22, 23):
        _span(skin, r, (5, 6), (25, 26))
    _span(skin, 25, (8, 23))
    _span(skin, 26, (9, 22))
    _span(skin, 27, (9, 22))
    _span(skin, 28, (10, 21))

    line = _grid()                      # ears and chin outline
    _span(line, 20, (5, 6), (25, 26))
    _span(line, 24, (5, 6), (25, 26))
    for r in (21, 22, 23):
        line[r][4] = line[r][27] = "#"
    for r, (a, b) in {25: (8, 23), 26: (9, 22), 27: (9, 22), 28: (10, 21)}.items():
        line[r][a] = line[r][b] = "#"
    _span(line, 29, (11, 20))

    hair = _grid()
    rows = {
        3: [(11, 19)], 4: [(11, 19)],
        5: [(7, 22)], 6: [(6, 24)], 7: [(5, 25)], 8: [(4, 26)], 9: [(3, 27)],
        10: [(1, 1), (2, 28)], 11: [(2, 29)],
        12: [(3, 17), (24, 29)],
        13: [(1, 16), (24, 28), (30, 30)],
        14: [(2, 15), (25, 29), (31, 31)],
        15: [(3, 15), (25, 28)],
        16: [(4, 15), (26, 28)],
        17: [(5, 8), (13, 15), (26, 27)],
    }
    for r, runs in rows.items():
        _span(hair, r, *runs)
    for r, c in ((9, 2), (12, 2), (15, 2), (11, 30), (16, 29), (7, 4), (8, 27)):   # loose tufts
        hair[r][c] = "#"
    for r, c in ((5, 8), (5, 21), (6, 7), (4, 11)):                               # nicks in the edge
        hair[r][c] = "."
    for r, (a, b) in {5: (14, 17), 6: (15, 17), 10: (6, 9), 11: (7, 9), 12: (6, 7), 13: (4, 6),
                      14: (4, 5), 15: (4, 5)}.items():
        for c in range(a, b + 1):
            if hair[r][c] == "#":
                hair[r][c] = "g"
    for r in (13, 14):
        for c in (25, 26):
            if hair[r][c] == "#":
                hair[r][c] = "g"
    for r in range(13, 17):
        if hair[r][13] == "#":
            hair[r][13] = "g"

    glasses = _grid()
    for x0 in (7, 17):
        _span(glasses, 18, (x0, x0 + 7))
        _span(glasses, 24, (x0, x0 + 7))
        for r in range(19, 24):
            glasses[r][x0] = glasses[r][x0 + 7] = "#"
    _span(glasses, 19, (15, 16))
    return {"skin": skin, "line": line, "hair": hair, "glasses": glasses}


_SPRITE = _build()

# antennae are drawn cell by cell so they can bend: (row, col)
_STRANDS = [(0, 17), (0, 18), (1, 18), (1, 19), (2, 19), (2, 20), (3, 20), (3, 21), (4, 21), (4, 22), (5, 22), (5, 23),
            (6, 24), (5, 25), (4, 26), (3, 27), (3, 28), (2, 28), (2, 29)]


@lru_cache(maxsize=24)
def _layers(cell_dev: int, ratio: float, fill: str) -> dict[str, QPixmap]:
    """Pre-render each layer at an integer number of device pixels per cell (so cell edges never blur)."""
    plan = (("skin", {"#": fill}), ("line", {"#": T.INK}), ("hair", {"#": T.INK, "g": HI}), ("glasses", {"#": T.INK}))
    out: dict[str, QPixmap] = {}
    for name, colors in plan:
        img = QImage(SW * cell_dev, SH * cell_dev, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        for r, row in enumerate(_SPRITE[name]):
            c = 0
            while c < SW:
                ch = row[c]
                if ch in colors:
                    c0 = c
                    while c < SW and row[c] == ch:
                        c += 1
                    q.fillRect(c0 * cell_dev, r * cell_dev, (c - c0) * cell_dev, cell_dev, QColor(colors[ch]))
                else:
                    c += 1
        q.end()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(ratio)
        out[name] = pm
    return out


# ---- pose: everything that is drawn in one frame ------------------------------------------------
@dataclass(frozen=True)
class Pose:
    dx: float = 0.0            # body offset, cells
    dy: float = 0.0
    sx: float = 1.0            # squash and stretch about the feet
    sy: float = 1.0
    hair_dx: float = 0.0
    hair_dy: float = 0.0
    glass_dy: float = 0.0
    shear: float = 0.0         # antenna bend
    eyes: str = "open"         # open | happy | closed | x
    eye_w: float = 2.0
    eye_h: float = 3.0
    eye_bottom: float = EYE_BOTTOM
    lx: float = 0.0            # where the eyes are looking, cells
    ly: float = 0.0
    mouth: str = "flat"        # flat | smile | grin | o | worried | yawn | snore
    blush: float = 0.0
    plus_k: float = 1.0
    plus_color: str = T.ORANGE
    plus_dy: float = 0.0
    bang: float = 0.0          # the red "!"
    sweat: float = -1.0        # falling sweat drop progress, -1 = hidden
    glint: float = -99.0       # x of the sparkle sweeping across the glasses
    shadow: float = 12.0
    fx: tuple = ()             # in front of the body: (kind, x, y, size, colour, alpha), canvas cells
    back: tuple = ()           # behind the body (confetti), same layout

    @staticmethod
    def static(mood: str) -> "Pose":
        if mood == "alert":
            return Pose(eye_w=2.6, eye_h=3.8, eye_bottom=23.4, mouth="o", plus_color=T.RED, bang=1.0, hair_dy=-0.8, shear=-0.05)
        if mood == "celebrate":
            return Pose(eyes="happy", mouth="grin", blush=1.0, plus_k=1.3)
        if mood == "sleep":
            return Pose(eyes="closed", mouth="snore", plus_color="#B9B7B0", plus_k=0.8, dy=0.9, glass_dy=0.5)
        if mood == "idle":
            return Pose(eye_h=2.0)
        return Pose()


def paint_pose(p: QPainter, pose: Pose, px: float, dpr: float, fill: str) -> None:
    cell_dev = max(1, round(px * dpr))
    L = _layers(cell_dev, cell_dev / px, fill)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    ink = QColor(T.INK)

    def canvas(x, y, w, h, color):
        p.fillRect(QRectF(x * px, y * px, w * px, h * px), color)

    def rect(x, y, w, h, color):                       # sprite-space cells
        canvas(OX + x, OY + y, w, h, color)

    # dithered ground shadow (stays on the ground while the body hops)
    if pose.shadow > 1:
        shade = T.qc(T.INK, 0.26)
        x0 = OX + SW / 2 - pose.shadow / 2
        for i in range(int(pose.shadow)):
            if i % 2 == 0:
                canvas(x0 + i, GRID_H - 1, 1, 1, shade)

    _paint_fx(p, pose.back, px)

    cx, fy = (OX + SW / 2) * px, (OY + SH) * px
    p.save()
    p.translate(cx + pose.dx * px, fy + pose.dy * px)
    p.scale(pose.sx, pose.sy)
    p.translate(-cx, -fy)

    origin = QPointF(OX * px, OY * px)
    p.drawPixmap(origin, L["skin"])
    p.drawPixmap(origin, L["line"])
    p.drawPixmap(origin + QPointF(pose.hair_dx * px, pose.hair_dy * px), L["hair"])
    p.drawPixmap(origin + QPointF(0, pose.glass_dy * px), L["glasses"])

    # sparkle sweeping over the top of the glasses
    if pose.glint > -50:
        gy = 18 + pose.glass_dy
        for x in list(range(7, 15)) + list(range(17, 25)):
            k = max(0.0, 1.0 - abs(x + 0.5 - pose.glint) / 2.4)
            if k > 0.05:
                rect(x, gy, 1, 1, T.mix(T.INK, GLINT, k))

    # eyes
    for c0 in (EYE_L, EYE_R):
        ex = c0 + pose.lx
        if pose.eyes == "open":
            rect(ex - pose.eye_w / 2, pose.eye_bottom + pose.ly - pose.eye_h, pose.eye_w, pose.eye_h, ink)
        elif pose.eyes == "happy":
            rect(c0 - 1.0, 20.6, 2.0, 1.0, ink)
            rect(c0 - 2.0, 21.6, 1.0, 1.0, ink)
            rect(c0 + 1.0, 21.6, 1.0, 1.0, ink)
        elif pose.eyes == "closed":
            rect(c0 - 1.5, 21.9, 3.0, 0.8, ink)
        else:  # x: dizzy
            for a, b in ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)):
                rect(c0 + a - 0.5, 21.5 + b - 0.5, 1, 1, ink)

    # mouth
    m = pose.mouth
    if m == "flat":
        rect(15.0, 27.0, 2.0, 0.8, ink)
    elif m == "smile":
        rect(14.0, 26.4, 1.0, 1.0, ink)
        rect(15.0, 27.2, 2.0, 1.0, ink)
        rect(17.0, 26.4, 1.0, 1.0, ink)
    elif m == "grin":
        rect(14.0, 26.4, 4.0, 1.0, ink)
        rect(15.0, 27.4, 2.0, 1.0, ink)
    elif m == "o":
        rect(15.0, 26.8, 2.0, 1.6, ink)
    elif m == "worried":
        rect(14.4, 27.6, 1.2, 0.8, ink)
        rect(15.4, 26.8, 1.2, 0.8, ink)
        rect(16.4, 27.6, 1.2, 0.8, ink)
    elif m == "yawn":
        rect(14.6, 26.2, 2.8, 2.4, ink)
    elif m == "snore":
        rect(15.3, 27.0, 1.4, 1.0, ink)

    if pose.blush > 0.05:
        c = T.qc(T.ORANGE, 0.55 * min(1.0, pose.blush))
        rect(10.0, 25.2, 2.0, 1.0, c)
        rect(20.0, 25.2, 2.0, 1.0, c)

    # antennae bend from their base on the hair
    for r, c in _STRANDS:
        rect(c + pose.shear * (6 - r) + pose.hair_dx, r + pose.hair_dy, 1, 1, ink)

    # the plus
    a = pose.plus_k
    col = QColor(pose.plus_color)
    ph = pose.plus_dy
    rect(30, 8 + ph, 1, 1, col)
    rect(30, 8 - a + ph, 1, a, col)
    rect(30, 9 + ph, 1, a, col)
    rect(30 - a, 8 + ph, a, 1, col)
    rect(31, 8 + ph, a, 1, col)

    if pose.bang > 0.05:                                # alert: red "!"
        s = min(1.2, pose.bang)
        h = 3.8 * s
        rect(2.0, 4.4 - h, 1.4, h, QColor(T.RED))
        rect(2.0, 5.2, 1.4, 1.2, QColor(T.RED))

    if pose.sweat >= 0:
        c = QColor(SWEAT)
        c.setAlphaF(max(0.0, 1.0 - pose.sweat ** 2))
        y = 17.4 + pose.sweat * 5.0
        rect(29.0, y, 1.0, 1.0, c)
        rect(28.5, y + 1, 2.0, 1.0, c)
        rect(28.5, y + 2, 2.0, 1.0, c)
    p.restore()

    _paint_fx(p, pose.fx, px)


def _paint_fx(p: QPainter, items: tuple, px: float) -> None:
    """Free-floating particles live in canvas space, so body squash never distorts them."""
    for kind, x, y, s, color, alpha in items:
        c = QColor(color)
        c.setAlphaF(alpha)

        def cell(cx, cy, w, h):
            p.fillRect(QRectF(cx * px, cy * px, w * px, h * px), c)

        if kind == "pix":
            cell(x, y, s, s)
        elif kind == "plus":
            cell(x, y, s, s)
            cell(x - s, y, s, s)
            cell(x + s, y, s, s)
            cell(x, y - s, s, s)
            cell(x, y + s, s, s)
        elif kind == "z":
            cell(x, y, 3 * s, s)
            cell(x + 2 * s, y + s, s, s)
            cell(x + s, y + 2 * s, s, s)
            cell(x, y + 3 * s, s, s)
            cell(x, y + 4 * s, 3 * s, s)


# ---- behaviour per mood -------------------------------------------------------------------------
STYLE = {
    "monitoring": dict(open=1.0, wide=0.0, base_y=0.0, lift=0.0, glass=0.0, bob=(0.30, 3.4)),
    "idle":       dict(open=0.62, wide=0.0, base_y=0.35, lift=0.0, glass=0.0, bob=(0.40, 4.6)),
    "alert":      dict(open=1.0, wide=1.0, base_y=-0.2, lift=-0.8, glass=-0.25, bob=(0.12, 0.9)),
    "celebrate":  dict(open=1.0, wide=0.0, base_y=0.0, lift=-0.2, glass=0.0, bob=(0.0, 1.0)),
    "sleep":      dict(open=0.0, wide=0.0, base_y=1.0, lift=0.35, glass=0.55, bob=(0.5, 5.0)),
}
CONFETTI = (T.RED, T.ORANGE, T.ORANGE, "#FFA46B", "#B9B7B0", "#D8D6CF")   # no black: it vanishes into the hair


class Mascot(QWidget):
    """Animated pixel nerd. mood: idle | monitoring | alert | celebrate | sleep."""

    def __init__(self, px: int = 6, mood: str = "idle", fill: str | None = None, parent=None, interactive: bool = True):
        super().__init__(parent)
        self._px, self._fill, self._interactive = px, fill or T.PAPER, interactive
        self._mood = mood if mood in MOODS else "monitoring"
        self.setFixedSize(GRID_W * px, GRID_H * px)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if interactive:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rng = random.Random()
        self._ticker = Ticker(self._step)
        self._paused = False
        self._t = self._mt = 0.0

        self._sq = Spring(0.0, 220.0, 12.0)         # squash (+) / stretch (-)
        self._hair = Spring(0.0, 95.0, 7.0)         # hair follows the head with a lag
        self._ant = Spring(0.0, 70.0, 5.0)          # antenna bend
        self._glass = Spring(0.0, 260.0, 20.0)      # glasses can bounce
        self._open, self._wide = Smooth(1.0, 18.0), Smooth(0.0, 14.0)
        self._base_y, self._lift, self._glass_base = Smooth(0.0, 6.0), Smooth(0.0, 8.0), Smooth(0.0, 8.0)
        self._blush = Smooth(0.0, 10.0)
        self._lx, self._ly = Smooth(0.0, 16.0), Smooth(0.0, 16.0)

        self._hop_y = self._hop_v = 0.0
        self._relaunch_at = 0.0
        self._blink_t, self._blink_at = -1.0, 1.5
        self._glint_t, self._glint_at = -1.0, 3.5
        self._push_t, self._push_at = -1.0, 9.0
        self._yawn_t, self._yawn_at = -1.0, 7.0
        self._wander, self._wander_at = (0.0, 0.0), 0.0
        self._glance, self._glance_until = (0.0, 0.0), 0.0
        self._sweat_t = 0.0
        self._combo, self._last_poke, self._dizzy_until = 0, -9.0, 0.0
        self._hover = False
        self._spawn_acc = self._plus_at = self._z_at = 0.0
        self._fx: list[list] = []                   # [kind, x, y, vx, vy, age, life, s0, s1, colour, gravity]

        self._enter_mood(first=True)
        self._pose = Pose.static(self._mood)

    # ---- public API ----------------------------------------------------------------------------
    @property
    def mood(self) -> str:
        return self._mood

    def set_mood(self, mood: str) -> None:
        if mood not in MOODS:
            mood = "monitoring"
        if mood == self._mood:
            return
        leaving = self._mood
        self._mood = mood
        if leaving == "celebrate":
            self._fx = [f for f in self._fx if f[0] != "conf"]
        self._enter_mood()
        self._ticker.wake()

    def hop(self, height: float = 2.4) -> None:
        self._launch(height)
        self._ticker.wake()

    def glance(self, dx: float, dy: float = 0.0, seconds: float = 0.9) -> None:
        """Look somewhere for a moment (cells; dx up to ~1.7)."""
        self._glance, self._glance_until = (dx, dy), self._t + seconds
        self._ticker.wake()

    def poke(self, pos=None) -> None:
        """A click: hop, and a combo that ends in a dizzy spin if you keep going."""
        t = self._t
        self._combo = self._combo + 1 if t - self._last_poke < 1.2 else 1
        self._last_poke = t
        self._launch(2.0 + min(self._combo, 5) * 0.2)
        self._ant.kick(self._rng.choice((-0.7, 0.7)))
        if self._combo >= 2 and pos is not None:
            float_text(self, f"x{self._combo}", pos)
        if self._combo >= 5:
            self._dizzy_until, self._combo = t + 1.9, 0
        self._ticker.wake()

    def pause(self) -> None:
        self._paused = True
        self._ticker.sleep()

    def resume(self) -> None:
        self._paused = False
        self._ticker.wake()

    # ---- events --------------------------------------------------------------------------------
    def showEvent(self, e):
        if not self._paused:
            self._ticker.wake()
        super().showEvent(e)

    def hideEvent(self, e):
        self._ticker.sleep()
        super().hideEvent(e)

    def enterEvent(self, e):
        if self._interactive:
            self._hover = True
            self._ticker.wake()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if self._interactive and e.button() == Qt.MouseButton.LeftButton:
            self.poke(e.position())
        else:
            super().mousePressEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        paint_pose(p, self._pose, self._px, self.devicePixelRatioF(), self._fill)

    # ---- simulation ----------------------------------------------------------------------------
    def _enter_mood(self, first: bool = False) -> None:
        st = STYLE[self._mood]
        for sm, key in ((self._open, "open"), (self._wide, "wide"), (self._base_y, "base_y"),
                        (self._lift, "lift"), (self._glass_base, "glass")):
            sm.target = st[key]
            if first:
                sm.snap(st[key])
        self._blush.target = 1.0 if self._mood == "celebrate" else 0.0
        if first:
            self._blush.snap(self._blush.target)
            return
        self._mt = 0.0
        self._sq.kick(7.0)                           # a small squish whenever the mood changes
        if self._mood == "celebrate":
            self._launch(3.0)
        elif self._mood == "alert":
            self._ant.kick(0.9)
            self._hair.kick(-10.0)

    def _launch(self, height: float) -> None:
        self._hop_v = math.sqrt(2 * HOP_G * height)
        self._hop_y = 1e-3
        self._sq.kick(-9.0)                          # stretch on take-off

    def _spawn(self, kind, x, y, vx, vy, life, s0, s1, color, g=0.0):
        if len(self._fx) < 70:
            self._fx.append([kind, x, y, vx, vy, 0.0, life, s0, s1, color, g])

    def _cursor_look(self) -> tuple[float, float]:
        c = self.mapFromGlobal(QCursor.pos())
        ex, ey = (OX + SW / 2) * self._px, (OY + 21.5) * self._px
        vx, vy = c.x() - ex, c.y() - ey
        d = math.hypot(vx, vy)
        if d < 1.0:
            return 0.0, 0.0
        k = math.tanh(d / (self._px * 28.0))
        return vx / d * k * 1.7, vy / d * k * 0.9

    def _step(self, dt: float) -> bool:
        if not self.isVisible() or self._paused:
            return False
        rng = self._rng
        self._t += dt
        self._mt += dt
        t, m = self._t, self._mood
        st = STYLE[m]
        dizzy = t < self._dizzy_until
        glass_base = self._glass_base.step(dt)

        # hop physics + landing
        if self._hop_y > 0.0 or self._hop_v > 0.0:
            self._hop_v -= HOP_G * dt
            self._hop_y += self._hop_v * dt
            if self._hop_y <= 0.0:
                impact = -self._hop_v
                self._hop_y = self._hop_v = 0.0
                self._sq.kick(min(15.0, impact * 0.8))
                self._ant.kick(rng.choice((-0.6, 0.6)))
                self._relaunch_at = t + 0.05
                for i in range(6):
                    self._spawn("pix", OX + 16 + rng.uniform(-5, 5), GRID_H - 1.4, rng.uniform(-6, 6) , -rng.uniform(1, 3),
                                0.38, 0.9, 0.3, "#B9B7B0", 14.0)
        elif m == "celebrate" and t >= self._relaunch_at:
            self._launch(3.0)

        # blink
        if self._blink_t < 0 and t >= self._blink_at:
            self._blink_t = 0.0
        lid = 1.0
        if self._blink_t >= 0:
            self._blink_t += dt
            u = self._blink_t / (0.16 if m != "idle" else 0.34)
            if u >= 1.0:
                self._blink_t = -1.0
                double = rng.random() < 0.16
                self._blink_at = t + (0.14 if double else rng.uniform(2.2, 5.6))
            else:
                lid = 1.0 - math.sin(math.pi * u)

        # monitoring: glints and the occasional push of the glasses
        glint = -99.0
        if m == "monitoring":
            if self._glint_t < 0 and t >= self._glint_at:
                self._glint_t = 0.0
            if self._glint_t >= 0:
                self._glint_t += dt
                u = self._glint_t / 0.75
                if u >= 1.0:
                    self._glint_t, self._glint_at = -1.0, t + rng.uniform(4.5, 8.5)
                else:
                    glint = 5.0 + 22.0 * u
            if self._push_t < 0 and t >= self._push_at:
                self._push_t = 0.0
                self._blink_t = 0.0
            if self._push_t >= 0:
                self._push_t += dt
                self._glass.target = -0.95 if self._push_t < 0.32 else 0.0
                if self._push_t > 0.75:
                    self._push_t, self._push_at = -1.0, t + rng.uniform(11.0, 20.0)
            else:
                self._glass.target = glass_base
        else:
            self._glass.target = glass_base

        # idle yawn
        yawn = -1.0
        if m == "idle":
            if self._yawn_t < 0 and t >= self._yawn_at:
                self._yawn_t = 0.0
            if self._yawn_t >= 0:
                self._yawn_t += dt
                yawn = self._yawn_t / 1.7
                if yawn >= 1.0:
                    self._yawn_t, self._yawn_at, yawn = -1.0, t + rng.uniform(7.0, 12.0), -1.0

        # where the eyes look
        if dizzy:
            tx = ty = 0.0
        elif t < self._glance_until:
            tx, ty = self._glance
        elif m in ("monitoring", "alert"):
            tx, ty = self._cursor_look()
        elif m == "idle":
            if t >= self._wander_at:
                self._wander = (rng.uniform(-1.3, 1.3), rng.uniform(-0.5, 0.5))
                self._wander_at = t + rng.uniform(1.6, 3.8)
            tx, ty = self._wander
        else:
            tx = ty = 0.0
        wide = self._wide.step(dt)
        mx, my = 1.7 - 0.7 * wide, 0.9 - 0.4 * wide
        self._lx.target, self._ly.target = clamp(tx, -mx, mx), clamp(ty, -my, my)
        lx, ly = self._lx.step(dt), self._ly.step(dt)

        # body
        amp, period = st["bob"]
        bob = math.sin(t * 2 * math.pi / period) * amp
        base_y = self._base_y.step(dt)
        stretch = 0.0
        if yawn >= 0:
            bump = math.sin(math.pi * yawn)
            bob -= 0.5 * bump
            stretch = 0.05 * bump
        body_dy = bob + base_y - self._hop_y
        shake = 0.0
        if m == "alert":
            shake = math.sin(t * 52) * 0.3 * (0.65 + 0.35 * math.sin(t * 3.1))
        if dizzy:
            shake = math.sin(t * 9) * 0.45
        sq = clamp(self._sq.step(dt), -1.3, 1.3)

        self._hair.target = body_dy
        hair_rel = self._hair.step(dt) - body_dy
        hair_dy = clamp(hair_rel * 0.8, -1.4, 1.4) + self._lift.step(dt)
        self._ant.target = math.sin(t * 1.3) * 0.03
        shear = clamp(self._ant.step(dt), -0.14, 0.14)
        glass_dy = self._glass.step(dt)
        blush = self._blush.step(dt)
        if self._hover and m in ("monitoring", "idle") and not dizzy:
            blush = max(blush, 0.6)

        # face
        openness = self._open.step(dt)
        eyes, mouth = "open", "flat"
        if dizzy:
            eyes, mouth = "x", "worried"
        elif m == "celebrate":
            eyes, mouth = "happy", "grin"
        elif m == "sleep":
            eyes = "closed"
            mouth = "snore" if math.sin(t * 2 * math.pi / 5.0) > 0 else "flat"
        elif yawn >= 0:
            eyes, mouth = "closed", "yawn"
        elif self._hover and m in ("monitoring", "idle"):
            eyes, mouth = "happy", "smile"
        elif m == "alert":
            mouth = "o" if int(t * 3.5) % 2 == 0 else "worried"
        eye_h = (3.0 * openness + 0.8 * wide) * lid
        eye_w = 2.0 + 0.6 * wide
        eye_bottom = EYE_BOTTOM + 0.4 * wide

        # plus
        plus_color, plus_k = T.ORANGE, 1.0 + 0.18 * math.sin(t * 3.0)
        if m == "alert":
            plus_color, plus_k = T.RED, 1.0 + 0.25 * math.sin(t * 14)
        elif m == "celebrate":
            plus_k = 1.3 + 0.3 * math.sin(t * 9)
        elif m == "sleep":
            plus_color, plus_k = "#B9B7B0", 0.8
        plus_dy = math.sin(t * 2.2) * 0.25

        bang = min(1.0, self._mt * 6.0) * (0.85 + 0.15 * math.sin(t * 12)) if m == "alert" else 0.0
        sweat = -1.0
        if m == "alert":
            self._sweat_t = (self._sweat_t + dt) % 1.25
            sweat = self._sweat_t / 0.95 if self._sweat_t < 0.95 else -1.0

        # particles
        if m in ("monitoring", "idle", "celebrate") and t >= self._plus_at:
            self._plus_at = t + rng.uniform(2.4, 4.2)
            self._spawn("plus", OX + 30.5, OY + 8.5, rng.uniform(0.8, 1.8), -rng.uniform(2.0, 3.2), 1.3, 0.5, 0.5, T.ORANGE)
        if m == "sleep" and t >= self._z_at:
            self._z_at = t + 1.5
            self._spawn("z", OX + 27.5, OY + 9.0, 2.2, -3.0, 2.6, 0.45, 0.85, T.GRAY)
        if m == "celebrate":                       # a fountain from the top of the head
            self._spawn_acc += dt * (30 if self._mt < 0.5 else 10)
            while self._spawn_acc >= 1.0:
                self._spawn_acc -= 1.0
                side = rng.choice((-1, 1))
                self._spawn("conf", OX + 16 + side * rng.uniform(0, 7), OY + 4.0, side * rng.uniform(2.0, 9.0),
                            -rng.uniform(11.0, 19.0), rng.uniform(1.2, 1.7), 1.6, 1.2, rng.choice(CONFETTI), 40.0)
        live = []
        for f in self._fx:
            f[5] += dt
            if f[5] < f[6]:
                f[4] += f[10] * dt
                f[1] += f[3] * dt
                f[2] += f[4] * dt
                live.append(f)
        self._fx = live

        # quantise to device pixels so identical-looking frames compare equal and are skipped
        s = self._px * self.devicePixelRatioF()

        def q(v: float) -> float:
            return round(v * s) / s

        fx, back = [], []
        for kind, x, y, _vx, _vy, age, life, s0, s1, color, _g in self._fx:
            k = age / life
            alpha = 1.0 if k < 0.6 else max(0.0, 1.0 - (k - 0.6) / 0.4)
            item = ("pix" if kind == "conf" else kind, q(x), q(y), q(s0 + (s1 - s0) * k), color, round(alpha * 8) / 8)
            (back if kind == "conf" else fx).append(item)
        if dizzy:
            for i in range(3):
                a = t * 7 + i * 2.094
                fx.append(("plus", q(OX + 16 + math.cos(a) * 8), q(OY + 3.0 + math.sin(a) * 1.6), q(0.5),
                           T.ORANGE if i else T.RED, 1.0))

        sx, sy = 1.0 + 0.07 * sq, 1.0 - 0.10 * sq + stretch
        pose = Pose(
            dx=q(shake), dy=q(body_dy), sx=round(sx, 3), sy=round(sy, 3),
            hair_dx=q(-shake * 0.5), hair_dy=q(hair_dy), glass_dy=q(glass_dy), shear=round(shear, 3),
            eyes=eyes, eye_w=q(eye_w), eye_h=q(max(0.5, eye_h)), eye_bottom=q(eye_bottom), lx=q(lx), ly=q(ly),
            mouth=mouth, blush=round(blush, 1), plus_k=q(plus_k), plus_color=plus_color, plus_dy=q(plus_dy),
            bang=round(bang, 2), sweat=round(sweat, 2), glint=q(glint) if glint > -50 else -99.0,
            shadow=round(12.0 * (1.0 - 0.35 * clamp(self._hop_y / 3.0))), fx=tuple(fx), back=tuple(back),
        )
        if pose != self._pose:
            self._pose = pose
            self.update()
        return True


class RingMascot(QWidget):
    """The mascot inside a slowly rotating dotted ring (used by the popup and the lock screen)."""

    def __init__(self, size: int = 230, px: int = 4, mood: str = "alert", dark: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._phase = 0.0
        self._mood = mood
        self._dark = dark
        self.mascot = Mascot(px=px, mood=mood, parent=self, interactive=False)
        self.mascot.move((size - self.mascot.width()) // 2, (size - self.mascot.height()) // 2 + 2)
        self._ticker = Ticker(self._spin)

    def set_mood(self, mood: str) -> None:
        self._mood = mood
        self.mascot.set_mood(mood)

    def _spin(self, dt: float) -> bool:
        if not self.isVisible():
            return False
        self._phase = (self._phase + 0.30 * dt) % 1.0
        self.update()
        return True

    def showEvent(self, e):
        self._ticker.wake()
        super().showEvent(e)

    def hideEvent(self, e):
        self._ticker.sleep()
        super().hideEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        r = self.width() / 2 - 6
        n = 72
        base = QColor(T.INK)
        if self._dark:  # light disc so the dark outline reads on a black screen
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.SURFACE))
            p.drawEllipse(c, r - 16, r - 16)
        for i in range(n):
            a = 2 * math.pi * i / n - math.pi / 2
            lead = ((i / n) - self._phase) % 1.0   # 0 = head of the sweep
            tail = 1.0 - lead
            glow = max(0.0, 1.0 - tail * 5.0) if tail < 0.2 else 0.0
            col = T.mix(T.qc(base.name(), 0.42), T.qc(base.name(), 1.0), glow)
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
    """Static render of the head for the tray, the window and the extension icons."""
    px, pad = 8, 2                                      # pad: room for the lifted hair and the plus's arms
    sprite = QPixmap((SW + 2 * pad) * px, (SH + 2 * pad) * px)
    sprite.fill(Qt.GlobalColor.transparent)
    p = QPainter(sprite)
    p.translate((pad - OX) * px, (pad - OY) * px)
    paint_pose(p, replace(Pose.static(mood), shadow=0.0), px, 1.0, T.PAPER)
    p.end()
    scaled = sprite.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    q = QPainter(out)
    q.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    q.end()
    return QIcon(out)
