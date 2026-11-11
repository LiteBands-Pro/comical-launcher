"""Optional, ask-first update check for the installed *game* — distinct
from launcher_updater.py, which is mandatory. If a newer build is
published, the player is asked whether to update now; declining just
leaves the currently-installed build in place, and Play keeps working
either way. There's no forced path here at all, on purpose.

Installed versions are tracked in a small local text file next to the
itch.io key (see itch_key.py's config_dir()) rather than inside the
encrypted install directory itself, so:
  - uninstalling and reinstalling the exact same build doesn't lose the
    version stamp, and
  - a corrupted/removed install doesn't leave a stale version file
    behind for the next fresh install to trip over.

Like launcher_updater.py, this is a placeholder until GAME_VERSION_MANIFEST_URL
(in game_config.py) is set to something real — is_configured() is False
and check_for_update() always returns None until then.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

from . import itch_key, version

REQUEST_TIMEOUT = 15


def is_configured(manifest_url: str) -> bool:
    return bool(manifest_url)


@dataclass
class GameUpdateInfo:
    version: str
    notes: str


class UpdateCheckError(Exception):
    pass


def _version_path(game_slug: str) -> Path:
    return itch_key.config_dir() / f"{game_slug}_version.local"


def get_installed_version(game_slug: str) -> Optional[str]:
    path = _version_path(game_slug)
    if not path.exists():
        return None
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def save_installed_version(game_slug: str, game_version: str) -> None:
    _version_path(game_slug).write_text(game_version.strip(), encoding="utf-8")


def check_for_update(manifest_url: str, game_slug: str) -> Optional[GameUpdateInfo]:
    """Returns update info if the manifest's version is newer than what's
    recorded as installed. Returns None if not configured, or if no
    version is recorded yet — a version is only ever stamped right after
    a successful install/update (see library_view.py), so "nothing
    recorded" means either the game isn't installed or it was installed
    before this feature/placeholder existed; either way there's nothing
    meaningful to compare against, so this stays silent rather than
    nagging based on a guess.

    Network/parse problems raise UpdateCheckError — callers should treat
    that the same as "couldn't check", not as "no update", and should
    fail silently rather than interrupting the person over it (this
    check is a courtesy, not a requirement)."""
    if not manifest_url:
        return None

    installed = get_installed_version(game_slug)
    if not installed:
        return None

    try:
        resp = requests.get(manifest_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpdateCheckError(f"couldn't check for a game update: {exc}") from exc

    remote_version = data.get("version")
    if not remote_version:
        raise UpdateCheckError("game update manifest had no 'version' field")

    if not version.is_newer(remote_version, installed):
        return None

    return GameUpdateInfo(version=remote_version, notes=data.get("notes", ""))
