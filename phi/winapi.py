"""Thin ctypes layer over the Win32 calls PHI needs. No keystrokes, no screenshots."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import NamedTuple, Optional

IS_WINDOWS = sys.platform == "win32"


class Foreground(NamedTuple):
    exe: str
    pid: int


if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.GetTickCount.restype = wintypes.DWORD

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _pid_cache: dict[int, str] = {}


def _exe_for_pid(pid: int) -> Optional[str]:
    if pid in _pid_cache:
        return _pid_cache[pid]
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            name = os.path.basename(buf.value)
            if len(_pid_cache) > 256:
                _pid_cache.clear()
            _pid_cache[pid] = name
            return name
    finally:
        kernel32.CloseHandle(handle)
    return None


def foreground() -> Optional[Foreground]:
    """Process name of the focused window. Only the executable name is read, never window content."""
    if not IS_WINDOWS:
        return None
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    exe = _exe_for_pid(pid.value)
    return Foreground(exe, pid.value) if exe else None


def idle_seconds() -> float:
    """Seconds since the last keyboard/mouse input (system-wide)."""
    if not IS_WINDOWS:
        return 0.0
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    elapsed = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return elapsed / 1000.0
