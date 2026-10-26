"""'Add an app': pick from the apps installed on this PC (plus anything PHI has seen you use)."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from ..apps import AppScanner
from ..utils import pretty_app
from . import theme as T
from .pages import mk_label
from .widgets import LinkButton, PillButton


class AppPicker(QDialog):
    def __init__(self, parent, store, taken: set[str]):
        super().__init__(parent)
        self.setWindowTitle("Add an app")
        self.setModal(True)
        self.setMinimumSize(460, 560)
        self.setStyleSheet(
            f"QDialog {{ background: {T.BG}; }}"
            f"QListWidget {{ background: {T.SURFACE}; border: 1px solid {T.LINE}; border-radius: 12px; outline: 0; padding: 6px; }}"
            f"QListWidget::item {{ padding: 10px 12px; border-radius: 8px; color: {T.INK}; }}"
            f"QListWidget::item:hover {{ background: {T.SOFT}; }}"
            f"QListWidget::item:selected {{ background: {T.INK}; color: {T.PAPER}; }}")
        self.choice: dict | None = None
        self._taken = {t.lower() for t in taken}
        self._all: list[dict] = []

        # apps PHI has actually seen you use (covers Store apps that have no Start-menu .exe)
        today = date.today()
        seen = store.by_name((today - timedelta(days=30)).isoformat(), today.isoformat(), ("app",))
        self._seen = [{"name": pretty_app(n), "exe": n} for _k, n, secs in seen if secs >= 60]

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 22, 24, 20)
        v.setSpacing(12)
        v.addWidget(mk_label("Choose an app", T.sans(20, T.QFont.Weight.Medium)))
        v.addWidget(mk_label("PHI will minimize it when your daily limit is reached.", T.sans(13), T.GRAY))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search")
        self.search.setFixedHeight(36)
        self.search.textChanged.connect(self._fill)
        v.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self._accept())
        v.addWidget(self.list, 1)
        self.status = mk_label("Looking for installed apps\u2026", T.sans(12), T.GRAY)
        v.addWidget(self.status)
        row = QHBoxLayout()
        cancel = LinkButton("Cancel", size=13)
        cancel.clicked.connect(self.reject)
        self.add_btn = PillButton("Add", "primary", height=38)
        self.add_btn.setFixedWidth(110)
        self.add_btn.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addStretch(1)
        row.addWidget(self.add_btn)
        v.addLayout(row)

        self._fill()
        self._scanner = AppScanner()
        self._scanner.done.connect(self._loaded)
        self._scanner.start()

    def _loaded(self, apps: list) -> None:
        self._all = apps
        self.status.setText(f"{len(self._merged())} apps")
        self._fill()

    def _merged(self) -> list[dict]:
        merged: dict[str, dict] = {a["exe"]: a for a in self._all}
        for a in self._seen:
            merged.setdefault(a["exe"], a)
        return sorted((a for e, a in merged.items() if e not in self._taken), key=lambda a: a["name"].lower())

    def _fill(self) -> None:
        q = self.search.text().strip().lower()
        self.list.clear()
        apps = self._merged()
        shown = [a for a in apps if q in a["name"].lower() or q in a["exe"]] if q else apps
        for a in shown:
            it = QListWidgetItem(f"{a['name']}     {a['exe']}")
            it.setData(Qt.ItemDataRole.UserRole, a)
            self.list.addItem(it)
        if q and not any(a["exe"].removesuffix(".exe") == q.removesuffix(".exe") for a in apps):
            exe = q.replace(" ", "")
            exe = exe if exe.endswith(".exe") else exe + ".exe"
            if exe not in self._taken and not any(ch in exe for ch in '\\/:*?"<>|'):
                it = QListWidgetItem(f"Use \u201c{exe}\u201d")
                it.setData(Qt.ItemDataRole.UserRole, {"name": pretty_app(exe), "exe": exe})
                self.list.addItem(it)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _accept(self) -> None:
        it = self.list.currentItem()
        if it is not None:
            self.choice = it.data(Qt.ItemDataRole.UserRole)
            self.accept()
