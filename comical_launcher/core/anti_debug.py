"""Lightweight runtime anti-tamper check.

NOTE: this is a speed bump, not real protection against a determined
reverse engineer — pair with code signing and server-side checks if you
need stronger guarantees.
"""

from __future__ import annotations

import ctypes
import platform


def is_being_debugged() -> bool:
    system = platform.system()
    if system == "Windows":
        return _windows_is_debugged()
    if system == "Linux":
        return _linux_is_traced()
    return False


def _windows_is_debugged() -> bool:
    try:
        return bool(ctypes.windll.kernel32.IsDebuggerPresent())  # type: ignore[attr-defined]
    except Exception:
        return False


def _linux_is_traced() -> bool:
    # If the process is already being traced (e.g. by a debugger), a
    # second PTRACE_TRACEME call from within the same process fails (-1).
    PTRACE_TRACEME = 0
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        result = libc.ptrace(PTRACE_TRACEME, 0, 0, 0)
        return result == -1
    except Exception:
        return False
