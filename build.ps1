# Builds dist\PHI\PHI.exe (PyInstaller) and installer_output\PHI-Setup.exe (Inno Setup).
# Uses Python 3.12 + PySide6 6.8.3 (widest Windows compatibility). Setup once:
#   py -3.12 -m venv .venv312; .\.venv312\Scripts\python.exe -m pip install PySide6==6.8.3 pyinstaller
$ErrorActionPreference = "Stop"
$py = ".\.venv312\Scripts\python.exe"
if (-not (Test-Path "redist\vc_redist.x64.exe")) {
    New-Item -ItemType Directory redist -Force | Out-Null
    Invoke-WebRequest https://aka.ms/vs/17/release/vc_redist.x64.exe -OutFile redist\vc_redist.x64.exe
}
& $py tools/make_icons.py
& $py -m PyInstaller --noconfirm --clean --windowed --name PHI --icon phi.ico --paths . run_phi.pyw
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "C:\Program Files (x86)\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) { & $iscc installer.iss } else { Write-Warning "Inno Setup not found; skipped installer." }
