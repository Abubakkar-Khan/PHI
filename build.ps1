# Builds dist\PHI\PHI.exe (PyInstaller) and installer_output\PHI-Setup.exe (Inno Setup).
$ErrorActionPreference = "Stop"
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install pyinstaller | Out-Null
& $py tools/make_icons.py
& $py -m PyInstaller --noconfirm --clean --windowed --name PHI --icon phi.ico --paths . `
    --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtPdf --exclude-module PySide6.QtSvg --exclude-module tkinter run_phi.pyw
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) { & $iscc installer.iss } else { Write-Warning "Inno Setup not found; skipped installer." }
