"""Local-only storage for the itch.io API key. The person pastes it once
into the launcher's connect screen and it's persisted here — never
hardcoded, never sent anywhere except directly to itch.io's API.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


def _config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    directory = base / "ComicalLauncher"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def config_dir() -> Path:
    """Public accessor for the same per-user config directory this
    module stores its key in — other local-only, non-secret files (e.g.
    game_updater.py's installed-version stamp) live alongside it here
    rather than each reimplementing the same OS-path logic."""
    return _config_dir()


def _key_path() -> Path:
    # .local suffix as a reminder: never commit/sync this file
    return _config_dir() / "itch_key.local"


def save_key(key: str) -> None:
    path = _key_path()
    path.write_text(key.strip(), encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600


def load_key() -> str | None:
    path = _key_path()
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def clear_key() -> None:
    path = _key_path()
    if path.exists():
        path.unlink()
