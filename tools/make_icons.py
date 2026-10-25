"""Render the extension icons and a multi-size phi.ico from the mascot. Run: python tools/make_icons.py"""
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from phi.ui.mascot import ghost_icon  # noqa: E402

app = QApplication([])
icon = ghost_icon("monitoring", 512)


def png_bytes(size: int) -> bytes:
    data = QByteArray()                       # keep a reference: QBuffer does not own it
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    icon.pixmap(size, size).save(buf, "PNG")
    buf.close()
    return bytes(data)


# extension icons
out = os.path.join(ROOT, "extension", "icons")
os.makedirs(out, exist_ok=True)
for size in (16, 32, 48, 128):
    with open(os.path.join(out, f"{size}.png"), "wb") as fh:
        fh.write(png_bytes(size))

# Windows .ico with every size Explorer, the taskbar and the Start menu ask for (PNG-compressed entries)
sizes = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
images = [(s, png_bytes(s)) for s in sizes]
header = struct.pack("<HHH", 0, 1, len(images))
offset = 6 + 16 * len(images)
entries, blobs = b"", b""
for s, data in images:
    entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset + len(blobs))
    blobs += data
with open(os.path.join(ROOT, "phi.ico"), "wb") as fh:
    fh.write(header + entries + blobs)
print("wrote phi.ico with", len(images), "sizes")
