"""Discord Rich Presence. While a game launched through this launcher is
running, the launcher disconnects its own RPC so it doesn't conflict with or
override the game's native Rich Presence. Purely cosmetic: if Discord isn't
installed or running, every call here fails silently and the game still
launches normally — Rich Presence is never allowed to block or break
anything.

SETUP REQUIRED: create an application at
https://discord.com/developers/applications (Rich Presence needs no
special approval) and put its numeric Application ID in DISCORD_CLIENT_ID.
"""

from __future__ import annotations

import time

from pypresence import Presence

DISCORD_CLIENT_ID = "1543195842406781018"

_client: Presence | None = None
_idle_since: int | None = None


def _connect_if_needed() -> Presence | None:
    """Returns a live Presence client, connecting lazily across available pipes.
    Iterates through pipes 0..9 to avoid clashes with IDEs or other RPC apps.
    Never raises — returns None on any failure."""
    global _client

    if DISCORD_CLIENT_ID.startswith("YOUR_DISCORD"):
        return None  # not configured — skip quietly

    if _client is not None:
        return _client

    # Scan Discord IPC pipes 0 through 9 to find an open slot
    for pipe_num in range(10):
        try:
            client = Presence(DISCORD_CLIENT_ID, pipe=pipe_num)
            client.connect()
            _client = client
            return _client
        except Exception:
            continue

    _client = None
    return None


def clear_presence() -> None:
    """Closes and cleans up the launcher's RPC connection completely.
    Call this right before launching a game so the launcher releases its
    Discord connection, letting the game handle its own Rich Presence uninterrupted."""
    global _client
    if _client is not None:
        try:
            _client.clear()
            _client.close()
        except Exception:
            pass
        finally:
            _client = None


def set_playing(game_title: str) -> None:
    """Fallback presence update for games that do NOT have built-in RPC.
    If your game has its own Discord Rich Presence integration, call clear_presence()
    instead so the launcher's RPC doesn't interfere."""
    global _client

    client = _connect_if_needed()
    if client is None:
        return

    try:
        client.update(
            details=f"Playing {game_title}",
            state="My library only has 1 item 😭",
            start=int(time.time()),
        )
    except Exception:
        _client = None


def set_idle() -> None:
    """Sets a "browsing the launcher" activity for whenever the app is
    open but no game is running: right after boot, and again once a game
    exits. The elapsed timer resets only the first time this is called
    after startup, so bouncing between the library and a game doesn't
    restart the "idle since" clock."""
    global _client, _idle_since

    client = _connect_if_needed()
    if client is None:
        return

    if _idle_since is None:
        _idle_since = int(time.time())

    try:
        client.update(
            details="Browsing the library",
            state="My library only has 1 item 😭",
            start=_idle_since,
        )
    except Exception:
        _client = None