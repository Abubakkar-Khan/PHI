"""Shared pieces for the screens: the app context, label helper and the Page base class."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from ..db import Settings, Store
from ..engine import Engine
from . import theme as T


@dataclass
class Ctx:
    store: Store
    cfg: Settings
    engine: Engine
    scheduler: object = None      # ReminderScheduler, set by the app after startup


def mk_label(text: str, font, color: str | None = None, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
    lb = QLabel(text)
    lb.setFont(font)
    lb.setStyleSheet(f"color:{color or T.INK}; background:transparent;")
    lb.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    return lb


class Page(QWidget):
    def refresh(self) -> None:  # overridden
        pass

    def enter(self) -> None:
        """Play the page's entrance (bars growing, rows fading in). Called when the page becomes visible."""
