"""Design tokens: warm paper, near-black ink, one signal red."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase

BG = "#F0EFEB"
SURFACE = "#F7F6F2"
PAPER = "#FCFBF9"
INK = "#171717"
GRAY = "#777777"
RED = "#E53935"
ORANGE = "#FF6B1A"   # the mascot's plus sign; used sparingly for sparks
LINE = "#DAD8D1"
SOFT = "#E6E4DE"

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


GLOBAL_QSS = f"""
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
