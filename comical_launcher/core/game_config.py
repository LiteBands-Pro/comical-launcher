"""Static configuration for Rocky Chapter 1
(https://comical-games.itch.io/rocky-chapter-1). Centralizing this here
means the rest of the app never decides which itch.io upload to fetch —
it's picked once, here, based on the OS actually running this code, so a
Windows install can never accidentally end up with the Linux build.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass

# itch.io's numeric game id for the Rocky Chapter 1 page. Find it in the
# itch.io creator dashboard: Edit game -> the URL contains
# `/game/edit/<ID>` — that number goes here. The cover-art lookup needs
# this to be set correctly.
ROCKY_GAME_ID = 4728924

# The public page url — the no-login download path (itch_public.py) works
# by loading this page directly, so it has to be the real page, not the
# dashboard/edit url.
GAME_URL = "https://comical-games.itch.io/rocky-chapter-1"

GAME_SLUG = "rocky"
GAME_TITLE = "Rocky"

# Optional. Points at a small JSON file (any static host — GitHub raw,
# GitHub Pages, etc.) shaped like: {"version": "1.2.0", "notes": "..."}.
# Bump "version" there whenever a new build is pushed to the itch.io
# uploads above. Left blank, the game-update check (game_updater.py)
# silently does nothing — the launcher still installs and plays Rocky
# fine, it just never offers an update prompt. See README's "Updates"
# section for how this differs from the launcher's own (mandatory)
# update check.
GAME_VERSION_MANIFEST_URL = ""


@dataclass(frozen=True)
class PlatformUpload:
    upload_id: int
    binary_filename: str


_UPLOADS = {
    "Windows": PlatformUpload(upload_id=19306300, binary_filename="Rocky Chapter 1.exe"),
    "Linux": PlatformUpload(upload_id=19306301, binary_filename="Rocky Chapter 1.x86_64"),
}


def recommended_upload() -> PlatformUpload | None:
    """The upload id + binary filename for whichever OS this is actually
    running on. None on platforms Rocky doesn't ship for."""
    return _UPLOADS.get(platform.system())
