"""Ephemeral execution: decrypts an installed (encrypted-at-rest) game into
a hidden temp directory, launches it, waits for exit, then securely wipes
the decrypted copy. The encrypted original on disk is never modified.

No login or license key is involved for this part — the AES key is
derived from this machine's HWID alone (see crypto.py), so a copy of the
encrypted files on another machine simply won't decrypt.
"""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from . import crypto, discord_rpc, hwid as hwid_mod

# Decrypting several files concurrently is a real speed win: AES-GCM via
# the `cryptography` package is a C extension that releases the GIL
# during the actual crypto work, and disk I/O overlaps across threads
# regardless. Capped at 8 so a game with hundreds of small files doesn't
# spawn hundreds of threads.
_DECRYPT_WORKERS = 8


def install_root() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ComicalLauncher" / "Games"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "comical-launcher" / "games"


def create_protected_dir(path: Path) -> None:
    """Creates a directory with owner-only access, hiding it on Windows."""
    path.mkdir(parents=True, exist_ok=True)

    if platform.system() == "Linux":
        os.chmod(path, stat.S_IRWXU)  # 0700
    elif platform.system() == "Windows":
        # Hidden attribute. NTFS ACL restriction to the current user
        # should be applied separately at install time, e.g.:
        #   icacls "<path>" /inheritance:r /grant:r "%USERNAME%":(OI)(CI)F
        try:
            subprocess.run(
                ["attrib", "+h", str(path)],
                check=False,
                timeout=5,
                # Same reasoning as hwid.py's powershell calls: this is a
                # console app spawned from a windowed app with no console
                # of its own, so it would otherwise flash a window open.
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except OSError:
            pass


def is_installed(game_slug: str) -> bool:
    return (install_root() / game_slug).exists()


def uninstall_game(game_slug: str) -> None:
    """Removes an install entirely — the recovery path when an install is
    corrupted (interrupted download, damaged files) and won't launch.
    The files on disk are already encrypted ciphertext, not the plaintext
    game, so a plain removal is enough here; there's nothing sensitive
    left behind to secure-wipe."""
    target = install_root() / game_slug
    if target.exists():
        shutil.rmtree(target)


def _walk_files(directory: Path) -> list[Path]:
    return [p for p in directory.rglob("*") if p.is_file()]


def launch_game(
    game_slug: str,
    binary_filename: str,
    game_title: str,
    on_before_launch: Optional[Callable[[], None]] = None,
    on_after_launch: Optional[Callable[[], None]] = None,
) -> None:
    """Runs a full ephemeral launch cycle:
    1. Integrity check (anti-debug) — imported lazily to avoid a hard
       dependency loop, since anti_debug has no dependency on this module.
    2. `on_before_launch` callback (the UI hides its window here) and sets
       Discord Rich Presence.
    3. Decrypts the installed payload into a hidden temp dir, keyed to
       this machine's HWID.
    4. Launches the game binary and blocks until it exits.
    5. Sets Discord Rich Presence back to idle, calls `on_after_launch`
       (UI shows itself again), and securely wipes the decrypted temp
       copy — always, even if the game crashed or step 4 raised.
    """
    from . import anti_debug

    if anti_debug.is_being_debugged():
        raise RuntimeError("integrity check failed: debugger detected")

    machine_id = hwid_mod.get_hwid()
    encrypted_dir = install_root() / game_slug
    if not encrypted_dir.exists():
        raise FileNotFoundError("game not installed")

    temp_dir = Path(tempfile.gettempdir()) / f".cl-run-{game_slug}-{os.getpid()}"
    create_protected_dir(temp_dir)

    if on_before_launch:
        on_before_launch()
    discord_rpc.clear_presence()

    run_error: Optional[BaseException] = None
    try:
        _run_decrypted(encrypted_dir, temp_dir, machine_id, binary_filename)
    except BaseException as exc:  # noqa: BLE001 - re-raised below, after cleanup
        run_error = exc
    finally:
        discord_rpc.set_idle()
        if on_after_launch:
            on_after_launch()
        crypto.secure_delete_dir(temp_dir)

    if run_error is not None:
        raise run_error


def _run_decrypted(encrypted_dir: Path, temp_dir: Path, machine_id: str, binary_filename: str) -> None:
    files = _walk_files(encrypted_dir)

    def decrypt_one(entry: Path) -> None:
        rel = entry.relative_to(encrypted_dir)
        dest = temp_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        crypto.decrypt_file(entry, dest, machine_id)

    # Threading only pays for itself when there's more than one core to
    # actually run on — on a single-core machine it's pure overhead
    # (thread scheduling + GIL contention) with no real parallelism to
    # offset it, measured directly rather than assumed. `cryptography`'s
    # AES-GCM does release the GIL during its C-level work, so this does
    # help on genuine multi-core hardware, which is what end users run.
    cpu_count = os.cpu_count() or 1
    worth_threading = cpu_count > 1 and len(files) > 1

    if worth_threading:
        with ThreadPoolExecutor(max_workers=min(_DECRYPT_WORKERS, cpu_count * 2)) as pool:
            # list() forces every future to be awaited so a failure in
            # any one file raises here instead of vanishing silently.
            list(pool.map(decrypt_one, files))
    else:
        for entry in files:
            decrypt_one(entry)

    binary_path = temp_dir / binary_filename

    if platform.system() == "Linux":
        current = os.stat(binary_path).st_mode
        os.chmod(binary_path, current | stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)

    result = subprocess.run([str(binary_path)], cwd=str(temp_dir))
    if result.returncode != 0:
        # Non-zero exit from the game itself isn't necessarily a launcher
        # error; surface it as a soft failure the UI can display.
        raise RuntimeError(f"game exited with status {result.returncode}")
