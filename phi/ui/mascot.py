"""PHI's companion: a tamagotchi-style pixel nerd. Messy hair, square glasses, one orange plus.

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
SW, SH = 44, 41            # the sprite itself, drawn after the reference art (12 px per cell there)
OX, OY = 8, 7              # sprite origin inside the canvas (headroom for hops, room right for sparks)
PAD = OX                    # extra columns each side of the sprite layers, for big hair
GRID_W, GRID_H = SW + 2 * OX, OY + SH + 1   # the last row is the ground shadow

EYE_L, EYE_R = 15.0, 28.0  # pupil centres: the middle of each lens
EYE_BOTTOM = 31.0
FACE_CX = 21.5             # the line between the lenses
HI = "#3A3A3A"             # hair highlight
GLINT = "#8E8C86"
SWEAT = "#B9B7B0"
HOP_G = 87.0               # gravity for hops, in cells/s^2


# ---- sprite data: a messy black fringe with a bang, big square glasses with tall slit pupils, a tapering
# face with a flat chin and a tiny mouth, two thin antennae and an orange plus (see the reference image).
def _grid() -> list[list[str]]:
    return [["."] * SW for _ in range(SH)]


def _span(g, row: int, *runs: tuple[int, int], ch: str = "#") -> None:
    for a, b in runs:
        for c in range(a, b + 1):
            g[row][c] = ch


def _build() -> dict[str, list[list[str]]]:
    """Traced from the reference art at 12 px per cell. Black, white and one orange plus."""
    skin, line, hair, glasses = _grid(), _grid(), _grid(), _grid()

    # --- face: straight sides beside the lenses, then a stepped jaw down to a flat chin
    for r in range(15, 34):
        _span(skin, r, (6, 37))
    for r, (a, b) in {34: (10, 33), 35: (11, 32), 36: (12, 31), 37: (13, 30), 38: (14, 29)}.items():
        _span(skin, r, (a, b))
    for r in range(27, 34):
        line[r][5] = line[r][38] = "#"
    _span(line, 34, (6, 9), (34, 37))
    for r, (a, b) in {35: (10, 33), 36: (11, 32), 37: (12, 31), 38: (13, 30)}.items():
        line[r][a] = line[r][b] = "#"
    _span(line, 39, (14, 29))

    # --- hair: a messy mop with stray spikes, a pointed bang, and the forehead showing on the right
    rows = {
        4: [(15, 24)], 5: [(15, 26)], 6: [(9, 29)], 7: [(8, 31)], 8: [(6, 6), (8, 32)],
        9: [(5, 5), (7, 34)], 10: [(6, 36)], 11: [(5, 37)], 12: [(4, 38)], 13: [(2, 2), (4, 39)],
        14: [(1, 39)], 15: [(2, 40)],
        16: [(3, 23), (30, 40)], 17: [(3, 21), (31, 40)], 18: [(3, 20), (32, 41)], 19: [(3, 20), (33, 43)],
        20: [(0, 20), (33, 40)], 21: [(1, 12), (18, 20), (34, 41)], 22: [(3, 12), (19, 20), (34, 40)],
        23: [(3, 10), (19, 19), (34, 41)], 24: [(2, 8), (35, 40)], 25: [(3, 8), (35, 40)],
        26: [(2, 2), (4, 7), (36, 39)], 27: [(4, 5), (38, 39)],
    }
    for r, runs in rows.items():
        _span(hair, r, *runs)
    for r, c in ((12, 4), (16, 3), (22, 3), (6, 9), (17, 40)):    # a few nicks so the edge stays rough
        hair[r][c] = "."
    shine = {7: (19, 24), 8: (20, 23), 9: (21, 22),               # dark-grey glints, as in the art
             13: (11, 13), 14: (10, 12), 15: (9, 10), 18: (7, 8), 19: (7, 7),
             17: (18, 19), 16: (33, 35)}
    for r, (a, b) in shine.items():
        for c in range(a, b + 1):
            if hair[r][c] == "#":
                hair[r][c] = "g"
    for c in (34, 35):
        if hair[17][c] == "#":
            hair[17][c] = "g"

    # --- glasses: thick square rims with softened corners, joined by a short bridge
    for x0, x1 in ((9, 19), (23, 33)):
        _span(glasses, 24, (x0 + 1, x1 - 1))
        _span(glasses, 25, (x0, x1))
        _span(glasses, 32, (x0 + 1, x1 - 1))
        for r in range(26, 32):
            glasses[r][x0] = glasses[r][x1] = "#"
    _span(glasses, 26, (20, 22))
    _span(glasses, 27, (20, 22))
    return {"skin": skin, "line": line, "hair": hair, "glasses": glasses}




def _hair_buns() -> list[list[str]]:
    """Fia, traced from the reference picture. All shapes below are in the picture's own pixel coordinates
    (1024 x 1024) and are rasterised onto the sprite grid, so the proportions stay true to the art:
    two big buns, a cap with a flat peak, ragged bangs with a sliver of forehead, hair falling beside the
    lenses, and thin curling strands. The grid is PAD columns wider on both sides."""
    W = SW + 2 * PAD
    g = [["."] * W for _ in range(SH)]
    SX, SY = 14.5, 15.5                    # picture pixels per sprite cell (the hair is a little smaller than the art)

    def to_px(c, r):                       # centre of a cell, in picture pixels
        return 520 + (c + 0.5 - 22) * SX, 565 + (r + 0.5 - 24) * SY

    def inside(pt, poly):
        x, y = pt
        hit = False
        for i in range(len(poly)):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % len(poly)]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                hit = not hit
        return hit

    def fill(polys, ch="#", only=None):
        for r in range(SH):
            for c in range(-PAD, SW + PAD):
                pt = to_px(c, r)
                if any(inside(pt, q) for q in polys):
                    if only is None or g[r][c + PAD] == only:
                        g[r][c + PAD] = ch

    def stroke(points):
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            n = max(1, int(max(abs(x2 - x1), abs(y2 - y1)) / 2))
            for i in range(n + 1):
                x, y = x1 + (x2 - x1) * i / n, y1 + (y2 - y1) * i / n
                c, r = int((x - 520) / SX + 22 + 1000) - 1000, int((y - 565) / SY + 24 + 1000) - 1000
                if 0 <= r < SH and -PAD <= c < SW + PAD:
                    g[r][c + PAD] = "#"

    body = [
        # left bun
        [(225, 245), (330, 240), (375, 262), (400, 300), (405, 345), (395, 400), (340, 445), (290, 485), (235, 485),
         (200, 445), (178, 400), (176, 320), (185, 290)],
        # hair falling from the left bun, beside the lens
        [(215, 470), (335, 440), (342, 500), (335, 560), (312, 612), (285, 618), (258, 592), (225, 545), (212, 500)],
        # cap with a flat peak
        [(330, 450), (400, 330), (440, 290), (570, 285), (640, 310), (675, 350), (705, 430), (560, 430), (420, 450)],
        # right bun
        [(690, 215), (790, 210), (835, 235), (865, 290), (880, 355), (870, 415), (830, 442), (780, 452), (700, 432),
         (655, 385), (640, 332), (645, 285), (662, 245)],
        # hair falling from the right bun, beside the lens
        [(690, 420), (802, 432), (812, 500), (802, 562), (772, 602), (736, 612), (700, 592), (690, 520)],
        # bangs: ragged strands ending in points above the glasses
        [(335, 430), (482, 400), (500, 440), (470, 520), (456, 548), (440, 522), (420, 556), (396, 526), (380, 552),
         (350, 532)],
        [(486, 395), (512, 395), (518, 470), (506, 548), (490, 548)],
        [(542, 415), (582, 380), (602, 470), (586, 548), (566, 548), (556, 470)],
        [(575, 380), (692, 430), (702, 560), (662, 556), (640, 522), (602, 470)],
    ]
    fill(body)

    strands = [
        [(165, 345), (140, 360), (130, 375), (145, 400), (140, 438)],                  # left edge of the left bun
        [(165, 462), (190, 478), (215, 472), (225, 500)],                              # curl under the left bun
        [(262, 630), (245, 662), (240, 700), (250, 726)],
        [(300, 712), (295, 745), (310, 775), (336, 796)],
        [(360, 262), (362, 240), (380, 230), (405, 250), (410, 282), (405, 302)],      # loop above the left bun
        [(645, 205), (625, 225), (615, 260), (620, 285), (636, 302)],                  # curl by the right bun
        [(850, 345), (875, 360), (880, 390), (886, 416)],
        [(857, 430), (850, 462), (846, 498)],
        [(790, 490), (800, 520), (806, 556)],
        [(790, 590), (806, 612), (811, 646), (800, 682)],
        [(720, 676), (746, 686), (756, 706)],
        [(726, 708), (716, 740), (696, 776), (680, 800)],
    ]
    for s in strands:
        stroke(s)

    fill([
        [(285, 278), (335, 275), (345, 300), (330, 330), (295, 325)],                  # left bun
        [(330, 450), (345, 425), (430, 362), (452, 368), (440, 386), (360, 446)],      # cap, left band
        [(572, 378), (605, 372), (668, 430), (672, 462), (640, 448)],                  # cap, right band
        [(700, 258), (742, 248), (722, 300), (700, 330), (690, 300)],                  # right bun
        [(748, 298), (820, 305), (838, 345), (790, 350), (755, 338)],
        [(740, 395), (830, 380), (842, 425), (790, 436)],
        [(700, 372), (740, 400), (760, 470), (745, 545), (715, 572), (705, 520), (715, 450)],
    ], ch="g", only="#")
    return g


def _pad(g):
    return [["."] * PAD + row + ["."] * PAD for row in g]


VARIANTS = {"classic": "Phi", "buns": "Fia"}
VARIANT = "classic"
STRANDS = {
    "classic": ([(0, 25), (0, 26), (0, 27), (1, 27), (1, 28), (2, 28), (2, 29), (3, 29), (4, 30), (5, 31), (6, 32),
                 (7, 32), (8, 32), (9, 32), (9, 33), (9, 34), (8, 34), (8, 35), (7, 35), (7, 36), (6, 36), (5, 37),
                 (4, 38)], 10),
    "buns": ([], 5),
}
PLUS_AT = {"classic": (40, 10), "buns": (48, 6)}


def set_variant(name: str) -> None:
    """Pick which character every Mascot and icon draws."""
    global VARIANT
    VARIANT = name if name in VARIANTS else "classic"
    _layers.cache_clear()


@lru_cache(maxsize=4)
def _sprite(variant: str) -> dict[str, list[list[str]]]:
    s = {k: _pad(v) for k, v in _build().items()}
    if variant == "buns":
        s["hair"] = _hair_buns()
    return s

# antennae are drawn cell by cell so they can bend: (row, col)
_STRANDS = [(0, 25), (0, 26), (0, 27), (1, 27), (1, 28), (2, 28), (2, 29), (3, 29), (4, 30), (5, 31), (6, 32),
            (7, 32), (8, 32), (9, 32),
            (9, 33), (9, 34), (8, 34), (8, 35), (7, 35), (7, 36), (6, 36), (5, 37), (4, 38)]
_STRAND_BASE = 10


@lru_cache(maxsize=24)
def _layers(cell_dev: int, ratio: float, fill: str, variant: str = "classic") -> dict[str, QPixmap]:
    """Pre-render each layer at an integer number of device pixels per cell (so cell edges never blur)."""
    plan = (("skin", {"#": fill}), ("line", {"#": T.INK}), ("hair", {"#": T.INK, "g": HI, "o": T.ORANGE}), ("glasses", {"#": T.INK}))
    out: dict[str, QPixmap] = {}
    GW = len(_sprite(variant)["skin"][0])
    for name, colors in plan:
        img = QImage(GW * cell_dev, SH * cell_dev, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        q = QPainter(img)
        for r, row in enumerate(_sprite(variant)[name]):
            c = 0
            while c < GW:
                ch = row[c]
                if ch in colors:
                    c0 = c
                    while c < GW and row[c] == ch:
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
    eye_h: float = 4.0
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
    shadow: float = 18.0
    fx: tuple = ()             # in front of the body: (kind, x, y, size, colour, alpha), canvas cells
    back: tuple = ()           # behind the body (confetti), same layout

    @staticmethod
    def static(mood: str) -> "Pose":
        if mood == "alert":
            return Pose(eye_w=3.0, eye_h=5.6, eye_bottom=32.0, mouth="o", plus_color=T.ORANGE, bang=1.0, hair_dy=-1.0, shear=-0.05)
        if mood == "celebrate":
            return Pose(eyes="happy", mouth="grin", blush=1.0, plus_k=1.3)
        if mood == "sleep":
            return Pose(eyes="closed", mouth="snore", plus_color="#B9B7B0", plus_k=0.8, dy=0.9, glass_dy=0.5)
        if mood == "idle":
            return Pose(eye_h=3.0)
        return Pose()


def paint_pose(p: QPainter, pose: Pose, px: float, dpr: float, fill: str) -> None:
    cell_dev = max(1, round(px * dpr))
    L = _layers(cell_dev, cell_dev / px, fill, VARIANT)
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

    origin = QPointF((OX - PAD) * px, OY * px)
    p.drawPixmap(origin, L["skin"])
    p.drawPixmap(origin, L["line"])
    p.drawPixmap(origin + QPointF(pose.hair_dx * px, pose.hair_dy * px), L["hair"])
    p.drawPixmap(origin + QPointF(0, pose.glass_dy * px), L["glasses"])

    # sparkle sweeping over the top rim of the glasses
    if pose.glint > -50:
        gy = 24 + pose.glass_dy
        for x in list(range(10, 21)) + list(range(23, 34)):
            k = max(0.0, 1.0 - abs(x + 0.5 - pose.glint) / 2.8)
            if k > 0.05:
                rect(x, gy, 1, 1, T.mix(T.INK, GLINT, k))

    # eyes: tall slit pupils inside the lenses
    for c0 in (EYE_L, EYE_R):
        ex = c0 + pose.lx
        if pose.eyes == "open":
            rect(ex - pose.eye_w / 2, pose.eye_bottom + pose.ly - pose.eye_h, pose.eye_w, pose.eye_h, ink)
        elif pose.eyes == "happy":
            rect(c0 - 1.0, 28.0, 2.0, 1.0, ink)
            rect(c0 - 2.0, 29.0, 1.0, 1.0, ink)
            rect(c0 + 1.0, 29.0, 1.0, 1.0, ink)
        elif pose.eyes == "closed":
            rect(c0 - 2.0, 29.4, 4.0, 0.9, ink)
        else:  # x: dizzy
            for a, b in ((-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)):
                rect(c0 + a * 1.2 - 0.5, 29.0 + b * 1.2 - 0.5, 1, 1, ink)

    # mouth: a tiny mark under the bridge
    m = pose.mouth
    if m == "flat":
        rect(20.5, 35.4, 2.0, 0.8, ink)
    elif m == "smile":
        rect(19.5, 35.2, 1.0, 1.0, ink)
        rect(20.5, 36.0, 2.0, 1.0, ink)
        rect(22.5, 35.2, 1.0, 1.0, ink)
    elif m == "grin":
        rect(19.5, 35.2, 4.0, 1.0, ink)
        rect(20.5, 36.2, 2.0, 1.0, ink)
    elif m == "o":
        rect(20.5, 35.6, 2.0, 1.8, ink)
    elif m == "worried":
        rect(19.6, 36.4, 1.4, 0.8, ink)
        rect(20.8, 35.6, 1.4, 0.8, ink)
        rect(22.0, 36.4, 1.4, 0.8, ink)
    elif m == "yawn":
        rect(20.0, 35.0, 3.0, 2.8, ink)
    elif m == "snore":
        rect(20.8, 36.0, 1.6, 1.0, ink)

    if pose.blush > 0.05:
        c = T.qc(T.ORANGE, 0.55 * min(1.0, pose.blush))
        rect(11.0, 35.0, 2.0, 1.0, c)
        rect(30.0, 35.0, 2.0, 1.0, c)

    # antennae bend from their base on the hair
    strands, base_row = STRANDS[VARIANT]
    for r, c in strands:
        rect(c + pose.shear * (base_row - r) + pose.hair_dx, r + pose.hair_dy, 1, 1, ink)

    # the orange plus floating off the hair
    a = pose.plus_k
    col = QColor(pose.plus_color)
    ph = pose.plus_dy
    qx, qy = PLUS_AT[VARIANT]
    rect(qx, qy + ph, 2, 2, col)
    rect(qx - a, qy + ph, a, 2, col)
    rect(qx + 2, qy + ph, a, 2, col)
    rect(qx, qy - a + ph, 2, a, col)
    rect(qx, qy + 2 + ph, 2, a, col)

    if pose.bang > 0.05:                                # alert: red "!"
        s_ = min(1.2, pose.bang)
        h = 5.0 * s_
        rect(2.0, 7.0 - h, 1.6, h, QColor(T.ORANGE))
        rect(2.0, 8.0, 1.6, 1.4, QColor(T.ORANGE))

    if pose.sweat >= 0:
        c = QColor(SWEAT)
        c.setAlphaF(max(0.0, 1.0 - pose.sweat ** 2))
        y = 21.0 + pose.sweat * 9.0
        rect(39.0, y, 1.0, 1.0, c)
        rect(38.5, y + 1, 2.0, 1.0, c)
        rect(38.5, y + 2, 2.0, 1.0, c)
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
CONFETTI = (T.ORANGE, T.ORANGE, "#FFA46B", "#FFC59E", "#B9B7B0", "#D8D6CF")   # no black: it vanishes into the hair


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
        self._hop_v = math.sqrt(2 * HOP_G * height * 1.4)
        self._hop_y = 1e-3
        self._sq.kick(-9.0)                          # stretch on take-off

    def _spawn(self, kind, x, y, vx, vy, life, s0, s1, color, g=0.0):
        if len(self._fx) < 70:
            self._fx.append([kind, x, y, vx, vy, 0.0, life, s0, s1, color, g])

    def _cursor_look(self) -> tuple[float, float]:
        c = self.mapFromGlobal(QCursor.pos())
        ex, ey = (OX + FACE_CX) * self._px, (OY + 29.0) * self._px
        vx, vy = c.x() - ex, c.y() - ey
        d = math.hypot(vx, vy)
        if d < 1.0:
            return 0.0, 0.0
        k = math.tanh(d / (self._px * 28.0))
        return vx / d * k * 2.6, vy / d * k * 1.4

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
                    self._spawn("pix", OX + FACE_CX + rng.uniform(-7, 7), GRID_H - 1.4, rng.uniform(-6, 6) , -rng.uniform(1, 3),
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
                    glint = 8.0 + 28.0 * u
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
        mx, my = 2.6 - 0.8 * wide, 1.4 - 0.5 * wide
        self._lx.target, self._ly.target = clamp(tx, -mx, mx), clamp(ty, -my, my)
        lx, ly = self._lx.step(dt), self._ly.step(dt)

        # body
        amp, period = st["bob"]
        amp *= 1.3
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
        eye_h = (4.0 * openness + 1.2 * wide) * lid
        eye_w = 2.0 + 0.9 * wide
        eye_bottom = EYE_BOTTOM + 0.7 * wide

        # plus
        plus_color, plus_k = T.ORANGE, 1.0 + 0.18 * math.sin(t * 3.0)
        if m == "alert":
            plus_color, plus_k = T.ORANGE, 1.0 + 0.25 * math.sin(t * 14)
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
            self._spawn("plus", OX + PLUS_AT[VARIANT][0] + 1.0, OY + PLUS_AT[VARIANT][1] + 1.0, rng.uniform(1.0, 2.4), -rng.uniform(3.0, 4.6), 1.3, 0.7, 0.7, T.ORANGE)
        if m == "sleep" and t >= self._z_at:
            self._z_at = t + 1.5
            self._spawn("z", OX + 38.0, OY + 12.0, 3.0, -4.0, 2.6, 0.6, 1.1, T.GRAY)
        if m == "celebrate":                       # a fountain from the top of the head
            self._spawn_acc += dt * (30 if self._mt < 0.5 else 10)
            while self._spawn_acc >= 1.0:
                self._spawn_acc -= 1.0
                side = rng.choice((-1, 1))
                self._spawn("conf", OX + FACE_CX + side * rng.uniform(0, 10), OY + 3.0, side * rng.uniform(3.0, 12.0),
                            -rng.uniform(15.0, 26.0), rng.uniform(1.2, 1.7), 2.2, 1.6, rng.choice(CONFETTI), 56.0)
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
                fx.append(("plus", q(OX + FACE_CX + math.cos(a) * 12), q(OY + 5.0 + math.sin(a) * 2.2), q(0.7),
                           T.ORANGE, 1.0))

        sx, sy = 1.0 + 0.07 * sq, 1.0 - 0.10 * sq + stretch
        pose = Pose(
            dx=q(shake), dy=q(body_dy), sx=round(sx, 3), sy=round(sy, 3),
            hair_dx=q(-shake * 0.5), hair_dy=q(hair_dy), glass_dy=q(glass_dy), shear=round(shear, 3),
            eyes=eyes, eye_w=q(eye_w), eye_h=q(max(0.5, eye_h)), eye_bottom=q(eye_bottom), lx=q(lx), ly=q(ly),
            mouth=mouth, blush=round(blush, 1), plus_k=q(plus_k), plus_color=plus_color, plus_dy=q(plus_dy),
            bang=round(bang, 2), sweat=round(sweat, 2), glint=q(glint) if glint > -50 else -99.0,
            shadow=round(18.0 * (1.0 - 0.35 * clamp(self._hop_y / 4.2))), fx=tuple(fx), back=tuple(back),
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
    """PHI_ in dot-matrix letters. The red dots after it arrive one by one, hold, then start over."""

    # Red dots lit on each beat: they arrive left to right, one per beat, stay lit for a moment, then reset.
    DOT_BEATS = (0, 1, 2, 3, 4, 5, 5, 5)
    BEAT_MS = 190

    def __init__(self, dot: float = 3.0, text: str = "PHI_", parent=None):
        super().__init__(parent)
        self._dot, self._text = dot, text
        self._beat = 0
        step = dot * 2.2
        self.setFixedSize(int(len(text) * 6 * step), int(7 * step) + 2)
        self._timer = QTimer(self)
        self._timer.setInterval(self.BEAT_MS)
        self._timer.timeout.connect(self._advance)

    def _advance(self):
        self._beat = (self._beat + 1) % len(self.DOT_BEATS)
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
        lit = self.DOT_BEATS[self._beat]
        prev = self.DOT_BEATS[self._beat - 1]
        for gi, ch in enumerate(self._text):
            glyph = GLYPHS[ch]
            for y, row in enumerate(glyph):
                for x, v in enumerate(row):
                    if v != "#":
                        continue
                    cursor = ch == "_"
                    radius = self._dot * 0.8
                    if cursor:
                        if x >= lit:
                            continue                           # this dot has not arrived yet
                        if x == lit - 1 and lit > prev:
                            radius *= 1.3                      # the newest dot pops a little as it lands
                    p.setBrush(QColor(T.RED if cursor else T.INK))
                    p.drawEllipse(QPointF((gi * 6 + x) * step + step / 2, y * step + step / 2 + 1), radius, radius)


def ghost_icon(mood: str = "monitoring", size: int = 256) -> QIcon:
    """Static render of the head for the tray, the window and the extension icons."""
    px, pad = 8, 2                                      # pad: room for the lifted hair and the plus's arms
    padx = 8 if VARIANT == "buns" else pad              # Fia's buns stick out sideways
    sprite = QPixmap((SW + 2 * padx) * px, (SH + 2 * pad) * px)
    sprite.fill(Qt.GlobalColor.transparent)
    # The icon always uses the light palette, so the tray, taskbar and exe show the same face in every theme.
    saved = {k: getattr(T, k) for k in T.LIGHT}
    T.__dict__.update(T.LIGHT)
    _layers.cache_clear()
    try:
        p = QPainter(sprite)
        p.translate((padx - OX) * px, (pad - OY) * px)
        paint_pose(p, replace(Pose.static(mood), shadow=0.0), px, 1.0, T.PAPER)
        p.end()
    finally:
        T.__dict__.update(saved)
        _layers.cache_clear()
    scaled = sprite.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(size, size)
    out.fill(Qt.GlobalColor.transparent)
    q = QPainter(out)
    q.drawPixmap((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    q.end()
    return QIcon(out)
