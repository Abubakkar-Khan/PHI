"""Find the desktop apps installed on this PC (from Start menu shortcuts) so one can be picked and restricted.

Only names and executable file names are read; nothing is stored until the user adds an app.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, Signal

_SKIP_WORDS = ("uninstall", "readme", "license", "release notes", "documentation", "help", "manual", "website",
               "support", "changelog", "what's new", "repair", "feedback", "troubleshoot")
_SKIP_EXES = {"msiexec.exe", "unins000.exe", "uninstall.exe", "update.exe", "setup.exe", "installer.exe", "phi.exe"}

_SCRIPT = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$sh = New-Object -ComObject WScript.Shell
$roots = @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs", "$env:APPDATA\Microsoft\Windows\Start Menu\Programs")
$out = Get-ChildItem -Path $roots -Filter *.lnk -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $t = $sh.CreateShortcut($_.FullName).TargetPath
    if ($t -like '*.exe') { [pscustomobject]@{ name = $_.BaseName; exe = (Split-Path $t -Leaf) } }
}
ConvertTo-Json -InputObject @($out) -Compress
"""

_cache: list[dict] | None = None


def installed_apps() -> list[dict]:
    """[{'name': 'Discord', 'exe': 'discord.exe'}, ...] sorted by name. Cached after the first scan."""
    global _cache
    if _cache is not None:
        return _cache
    apps: dict[str, dict] = {}
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _SCRIPT],
                capture_output=True, timeout=40, creationflags=0x08000000)       # CREATE_NO_WINDOW
            rows = json.loads(res.stdout.decode("utf-8", "replace") or "[]")
        except (OSError, subprocess.SubprocessError, ValueError):
            rows = []
        for r in rows if isinstance(rows, list) else [rows]:
            name, exe = (r.get("name") or "").strip(), (r.get("exe") or "").lower()
            if not name or not exe or exe in _SKIP_EXES or any(w in name.lower() for w in _SKIP_WORDS):
                continue
            apps.setdefault(exe, {"name": name, "exe": exe})
    _cache = sorted(apps.values(), key=lambda a: a["name"].lower())
    return _cache


class AppScanner(QObject):
    """Runs the scan off the UI thread and hands the list back with a signal."""
    done = Signal(list)

    def start(self) -> None:
        threading.Thread(target=lambda: self.done.emit(installed_apps()), name="phi-appscan", daemon=True).start()
