"""Review what was hidden from Activity. Names are only shown here, after an explicit click."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from .. import stats
from . import theme as T
from .pages import mk_label
from .widgets import LinkButton, PillButton

KIND_TAG = {"app": "App", "site": "Website", "shorts": "YouTube Shorts"}


class HiddenDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Hidden activity")
        self.setMinimumSize(420, 360)
        self.setStyleSheet(f"QDialog {{ background: {T.BG}; }}")
        v = QVBoxLayout(self)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(10)
        v.addWidget(mk_label("Hidden activity", T.sans(20, T.QFont.Weight.Medium)))
        note = mk_label("These are left out of every list, chart and total. Nothing is deleted, "
                        "and PHI keeps tracking limits as usual.", T.sans(13), T.GRAY)
        note.setWordWrap(True)
        v.addWidget(note)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        self.body = QWidget()
        self.body.setAutoFillBackground(False)
        self.lay = QVBoxLayout(self.body)
        self.lay.setContentsMargins(0, 4, 0, 4)
        self.lay.setSpacing(0)
        scroll.setWidget(self.body)
        v.addWidget(scroll, 1)
        done = PillButton("Done", "primary", height=34)
        done.clicked.connect(self.accept)
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(done)
        v.addLayout(foot)
        self._build()

    def _build(self) -> None:
        while self.lay.count():
            w = self.lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        items = self.cfg.get("hidden_items") or []
        if not items:
            msg = mk_label("Nothing is hidden.", T.sans(14), T.GRAY, Qt.AlignmentFlag.AlignCenter)
            msg.setMinimumHeight(120)
            self.lay.addWidget(msg)
        for h in items:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(2, 8, 2, 8)
            col = QVBoxLayout()
            col.setSpacing(0)
            col.addWidget(mk_label(h.get("label") or h.get("key", ""), T.sans(15, T.QFont.Weight.Medium)))
            col.addWidget(mk_label(KIND_TAG.get(h.get("kind"), ""), T.sans(12), T.GRAY))
            hl.addLayout(col, 1)
            btn = LinkButton("Show again", size=13)
            btn.clicked.connect(lambda _=False, h=h: self._show_again(h))
            hl.addWidget(btn)
            self.lay.addWidget(row)
        self.lay.addStretch(1)

    def _show_again(self, h: dict) -> None:
        stats.unhide_item(self.cfg, h["kind"], h["key"])
        self._build()
