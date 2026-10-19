"""Start-with-Windows via the per-user Run key (no admin rights needed)."""
from __future__ import annotations

import os
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "PHI"


def _command() -> str:
    if getattr(sys, "frozen", False):  # packaged PHI.exe
        return f'"{sys.executable}" --background'
    exe = sys.executable
    pyw = exe.replace("python.exe", "pythonw.exe") if exe.lower().endswith("python.exe") else exe
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f'"{pyw}" "{os.path.join(root, "run_phi.pyw")}" --background'


def set_enabled(on: bool) -> None:
    if sys.platform != "win32" or os.environ.get("PHI_NO_AUTOSTART"):
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, VALUE, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, VALUE)
            except FileNotFoundError:
                pass
