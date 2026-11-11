"""Local disk cache for the game's title + cover art.

Before this, every single boot re-fetched both from itch.io
(data.json + the cover image bytes) before the library screen could show
real artwork — meaning the "blank card, then art pops in a moment later"
flash happened on literally every launch, even for someone who's played
this a hundred times and whose art never changes.

Now the last-known title/art loads instantly from disk (sub-millisecond,
no network) so the library screen is fully painted on first frame. A
background refresh still runs afterwards, same as before, and silently
updates both the UI and this cache if itch.io has something newer —
so the cache self-heals and never goes stale for more than one launch.
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import NamedTuple, Optional


class CachedArt(NamedTuple):
    title: Optional[str]
    cover_bytes: Optional[bytes]


def _cache_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "ComicalLauncher" / "Cache"
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "comical-launcher"


def _meta_path() -> Path:
    return _cache_dir() / "meta.json"


def _cover_path() -> Path:
    return _cache_dir() / "cover.img"


def load(game_slug: str) -> CachedArt:
    """Best-effort read of whatever was cached for this game last time.
    Missing/corrupt cache is just an empty result, never an error —
    callers fall back to their normal "fetch it" path either way."""
    title: Optional[str] = None
    cover_bytes: Optional[bytes] = None
    try:
        meta = json.loads(_meta_path().read_text())
        if meta.get("game_slug") == game_slug:
            title = meta.get("title")
    except (FileNotFoundError, ValueError, OSError):
        pass
    try:
        cover_bytes = _cover_path().read_bytes()
    except OSError:
        cover_bytes = None
    return CachedArt(title=title, cover_bytes=cover_bytes)


def save(game_slug: str, title: Optional[str], cover_bytes: Optional[bytes]) -> None:
    """Best-effort write-back after a successful network refresh. Never
    raises — a failed cache write just means next boot fetches again,
    which is exactly the pre-cache behavior, not a regression."""
    try:
        _cache_dir().mkdir(parents=True, exist_ok=True)
        if title:
            _meta_path().write_text(json.dumps({"game_slug": game_slug, "title": title}))
        if cover_bytes:
            _cover_path().write_bytes(cover_bytes)
    except OSError:
        pass
