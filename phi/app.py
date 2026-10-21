"""Application wiring: store, bridge, engine, tray, windows."""
from __future__ import annotations

import os
import sys
import tempfile

from PySide6.QtCore import QLockFile, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME, autostart
from .db import Settings, Store
from .engine import Engine
from .server import Bridge, BridgeServer
from .urlreader import UrlReader
from .ui import theme as T
from .ui import mascot as mascot_module
from .ui.main_window import MainWindow
from .ui.mascot import ghost_icon
from .ui.pages import Ctx
from .ui.popup import PopupController


class Tray:
    def __init__(self, engine: Engine, cfg: Settings, window: MainWindow, quit_cb):
        self.engine, self.cfg, self.window = engine, cfg, window
        self.icons = self._make_icons()
        self.tray = QSystemTrayIcon(self.icons["monitoring"])
        self.tray.setToolTip("PHI")
        self.menu = QMenu()
        self.status = QAction("PHI_  monitoring")
        self.status.setEnabled(False)
        self.act_open = QAction("Open PHI")
        self.act_track = QAction("Pause tracking")
        self.act_rem = QAction("Pause reminders for 1 hour")
        self.act_quit = QAction("Quit")
        for a in (self.status, None, self.act_open, self.act_track, self.act_rem, None, self.act_quit):
            self.menu.addSeparator() if a is None else self.menu.addAction(a)
        self.act_open.triggered.connect(self.show_window)
        self.act_track.triggered.connect(self.toggle_tracking)
        self.act_rem.triggered.connect(self.toggle_reminders)
        self.act_quit.triggered.connect(quit_cb)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()
        self._mood = "monitoring"
        engine.snapshot.connect(self.on_snapshot)

    @staticmethod
    def _make_icons() -> dict:
        return {m: ghost_icon(m) for m in ("monitoring", "idle", "alert", "sleep")}

    def refresh_icons(self) -> None:
        self.icons = self._make_icons()
        self.tray.setIcon(self.icons.get(self._mood, self.icons["monitoring"]))

    def show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def toggle_tracking(self):
        self.engine.set_tracking_paused(not self.engine.tracking_paused)

    def toggle_reminders(self):
        if self.engine.reminders_paused:
            self.engine.pause_reminders(0)
        else:
            self.engine.pause_reminders(60)

    def on_snapshot(self, snap: dict):
        mood = snap["mood"]
        if mood != self._mood:
            self._mood = mood
            self.tray.setIcon(self.icons.get(mood, self.icons["monitoring"]))
        text = {"paused": "paused", "idle": "idle", "shorts": "shorts detected"}.get(snap["status"], "monitoring")
        self.status.setText(f"PHI_  {text}")
        self.act_track.setText("Resume tracking" if snap["tracking_paused"] else "Pause tracking")
        self.act_rem.setText("Resume reminders" if snap["reminders_paused"] else "Pause reminders for 1 hour")
        self.tray.setToolTip(f"PHI · {text}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    background = "--background" in argv
    if "--selftest" in argv:  # packaging check: can UI Automation load?
        try:
            import uiautomation as auto
            with auto.UIAutomationInitializerInThread():
                msg = "ok:" + auto.GetRootControl().ControlTypeName
        except Exception as exc:
            msg = f"fail:{exc!r}"
        with open(os.path.join(tempfile.gettempdir(), "phi_selftest.txt"), "w") as fh:
            fh.write(msg)
        return 0

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(ghost_icon("idle"))

    lock = QLockFile(os.path.join(tempfile.gettempdir(), "phi-app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None, "PHI", "PHI is already running. Look for the ghost icon in the system tray (click the ^ arrow).")
        return 0  # already running

    store = Store()
    cfg = Settings(store)
    store.purge_older_than(cfg.get("retention_days"))
    cfg.subscribe(lambda k: store.purge_older_than(cfg.get("retention_days")) if k == "retention_days" else None)
    autostart.set_enabled(bool(cfg.get("autostart")))
    T.apply_settings(cfg)
    app.setStyleSheet(T.qss())

    bridge = Bridge()
    server = BridgeServer(bridge)
    server.start()

    reader = UrlReader()
    reader.start()
    engine = Engine(store, cfg, bridge, reader=reader)
    ctx = Ctx(store, cfg, engine)
    window = MainWindow(ctx)
    popups = PopupController(engine, cfg)

    def on_theme_change(key: str) -> None:
        """Light / dark / custom: swap the tokens, then rebuild the window. Popups pick it up when they appear."""
        if key not in T.THEME_KEYS:
            return
        T.apply_settings(cfg)
        mascot_module._layers.cache_clear()
        app.setStyleSheet(T.qss())
        tray.refresh_icons()
        QTimer.singleShot(0, window.retheme)     # after the click handler that triggered us has returned
    cfg.subscribe(on_theme_change)

    def quit_app():
        engine.stop()
        reader.stop()
        server.stop()
        tray.tray.hide()
        lock.unlock()
        app.quit()

    tray = Tray(engine, cfg, window, quit_app)
    engine.start()
    if not background or not QSystemTrayIcon.isSystemTrayAvailable():
        window.show()
    code = app.exec()
    store.close()
    return code
