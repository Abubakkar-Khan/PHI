"""Render the extension icons from the mascot sprite. Run: python tools/make_icons.py"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from phi.ui.mascot import ghost_icon  # noqa: E402

app = QGuiApplication([])
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extension", "icons")
os.makedirs(out, exist_ok=True)
icon = ghost_icon("idle", 256)
for size in (16, 32, 48, 128):
    icon.pixmap(size, size).save(os.path.join(out, f"{size}.png"))
