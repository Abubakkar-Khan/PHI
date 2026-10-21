"""Design tokens: warm paper, near-black ink, one signal red."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

LIGHT = dict(BG="#F0EFEB", SURFACE="#F7F6F2", PAPER="#FCFBF9", INK="#171717", GRAY="#777777", RED="#E53935",
             LINE="#DAD8D1", SOFT="#E6E4DE", CELL="#E9E7E1", BAR="#CBC9C2", EDGE="#CFCDC6")
DARK = dict(BG="#141414", SURFACE="#1C1C1C", PAPER="#242424", INK="#EDEBE6", GRAY="#8C8B87", RED="#FF4A44",
            LINE="#2E2E2E", SOFT="#2A2A2A", CELL="#262626", BAR="#454545", EDGE="#3A3A3A")
ORANGE = "#FF6B1A"   # the mascot's plus sign; used sparingly for sparks

# live tokens: widgets read these at paint time, so apply() restyles everything built afterwards
BG, SURFACE, PAPER, INK, GRAY, RED = (LIGHT[k] for k in ("BG", "SURFACE", "PAPER", "INK", "GRAY", "RED"))
LINE, SOFT, CELL, BAR, EDGE = (LIGHT[k] for k in ("LINE", "SOFT", "CELL", "BAR", "EDGE"))

THEME_KEYS = ("theme_mode", "theme_bg", "theme_text", "theme_accent")


def derive(bg: str, text: str, accent: str) -> dict:
    """Build a full palette from just three colours: background, text and accent."""
    b, t = QColor(bg), QColor(text)
    light = b.lightnessF() > 0.5
    white = "#FFFFFF"
    return dict(
        BG=b.name(), INK=t.name(), RED=QColor(accent).name(),
        SURFACE=mix(b, white, 0.5 if light else 0.04).name(),
        PAPER=mix(b, white, 0.8 if light else 0.08).name(),
        GRAY=mix(t, b, 0.5).name(), LINE=mix(b, t, 0.14).name(), SOFT=mix(b, t, 0.08).name(),
        CELL=mix(b, t, 0.07).name(), BAR=mix(b, t, 0.24).name(), EDGE=mix(b, t, 0.20).name(),
    )


def apply(mode: str, custom: tuple[str, str, str] | None = None) -> None:
    """mode: light | dark | custom (custom = background, text, accent)."""
    if mode == "dark":
        pal = DARK
    elif mode == "custom" and custom:
        pal = derive(*custom)
    else:
        pal = LIGHT
    globals().update(pal)


def apply_settings(cfg) -> None:
    apply(cfg.get("theme_mode"), (cfg.get("theme_bg"), cfg.get("theme_text"), cfg.get("theme_accent")))

SANS = ["Geist", "Inter", "Segoe UI Variable Text", "Segoe UI", "Arial"]
MONO = ["Geist Mono", "JetBrains Mono", "Cascadia Mono", "Cascadia Code", "Consolas", "Courier New"]

_families: set[str] | None = None
_resolved: dict[str, str] = {}


def _pick(key: str, candidates: list[str]) -> str:
    global _families
    if key in _resolved:
        return _resolved[key]
    if _families is None:
        _families = set(QFontDatabase.families())
    _resolved[key] = next((c for c in candidates if c in _families), candidates[-1])
    return _resolved[key]


def sans(px: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(_pick("sans", SANS))
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def mono(px: int, weight: QFont.Weight = QFont.Weight.Normal, spacing: float = 0.0) -> QFont:
    f = QFont(_pick("mono", MONO))
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def qc(color: str, alpha: float = 1.0) -> QColor:
    c = QColor(color)
    c.setAlphaF(alpha)
    return c


def mix(a: str | QColor, b: str | QColor, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
        round(ca.alpha() + (cb.alpha() - ca.alpha()) * t),
    )


def qss() -> str:
    return f"""
QToolTip {{ background: {INK}; color: {PAPER}; border: none; padding: 5px 8px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 2px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {GRAY}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QLineEdit {{
    background: {PAPER}; color: {INK}; border: 1px solid {LINE}; border-radius: 8px;
    padding: 0 10px; selection-background-color: {INK}; selection-color: {PAPER};
}}
QLineEdit:focus {{ border: 1px solid {INK}; }}
QMenu {{
    background: {PAPER}; color: {INK}; border: 1px solid {LINE}; padding: 6px;
}}
QMenu::item {{ padding: 7px 22px 7px 14px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SOFT}; color: {INK}; }}
QMenu::item:disabled {{ color: {GRAY}; }}
QMenu::separator {{ height: 1px; background: {LINE}; margin: 5px 8px; }}
"""
