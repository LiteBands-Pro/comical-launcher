"""Cross-platform hardware fingerprinting.

Combines a handful of stable hardware identifiers and hashes them into a
single deterministic machine signature. No third-party dependency is
needed for this — everything here is stdlib (subprocess, pathlib) plus
plain file reads.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess


def _run_powershell(command: str) -> str | None:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=5,
            # Without this, every powershell.exe spawn pops its own
            # console window: this app has no console attached (it's a
            # windowed PyInstaller build), so Windows creates a brand new
            # one for each console child process instead of reusing a
            # parent's. CREATE_NO_WINDOW stops that window from being
            # created at all -- the process still runs and its output is
            # still captured, it's just never visible.
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _windows_traits() -> list[str]:
    traits: list[str] = []

    cpu_id = _run_powershell("(Get-CimInstance Win32_Processor).ProcessorId")
    if cpu_id:
        traits.append(f"cpu:{cpu_id}")

    board_uuid = _run_powershell("(Get-CimInstance Win32_ComputerSystemProduct).UUID")
    if board_uuid:
        traits.append(f"board:{board_uuid}")

    mac = _run_powershell(
        '(Get-CimInstance Win32_NetworkAdapter -Filter '
        '"PhysicalAdapter=True AND MACAddress IS NOT NULL" | '
        "Select-Object -First 1 -ExpandProperty MACAddress)"
    )
    if mac:
        traits.append(f"mac:{mac}")

    return traits


def _linux_traits() -> list[str]:
    traits: list[str] = []

    try:
        with open("/sys/class/dmi/id/product_uuid", "r", encoding="utf-8") as f:
            traits.append(f"board:{f.read().strip()}")
    except OSError:
        pass

    try:
        with open("/etc/machine-id", "r", encoding="utf-8") as f:
            traits.append(f"machine:{f.read().strip()}")
    except OSError:
        pass

    try:
        import os

        for iface in sorted(os.listdir("/sys/class/net/")):
            if iface == "lo":
                continue
            addr_path = f"/sys/class/net/{iface}/address"
            try:
                with open(addr_path, "r", encoding="utf-8") as f:
                    mac = f.read().strip()
            except OSError:
                continue
            if mac and mac != "00:00:00:00:00:00":
                traits.append(f"mac:{mac}")
                break
    except OSError:
        pass

    return traits


_cached_hwid: str | None = None


def get_hwid() -> str:
    """Returns a stable, hex-encoded SHA-256 machine signature.

    Cached after the first call: on Windows this is backed by several
    `powershell.exe` spawns, which are genuinely slow to start (hundreds
    of milliseconds each), and this app calls get_hwid() from several
    places in a single session (boot, settings display, install, launch).
    The hardware can't change mid-session, so recomputing is pure waste.
    """
    global _cached_hwid
    if _cached_hwid is not None:
        return _cached_hwid

    system = platform.system()
    if system == "Windows":
        traits = _windows_traits()
    elif system == "Linux":
        traits = _linux_traits()
    else:
        traits = []

    if not traits:
        traits = ["fallback-unknown-host"]

    traits.sort()  # order-independent so trait discovery order never changes the hash
    joined = "|".join(traits)
    _cached_hwid = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return _cached_hwid
