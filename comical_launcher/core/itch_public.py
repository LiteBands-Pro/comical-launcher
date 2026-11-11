"""Anonymous, no-login download path for a free itch.io game.

itch.io's real API deliberately won't grant OAuth tokens the
`game:view:uploads` scope needed to list or download a game's files —
confirmed straight from itch.io's own dev forum (itch.io/t/6502109), and
that holds true even for a token belonging to the game's own owner. A
full-scope API key from account settings *does* work, but only for
whichever account that key belongs to — it can't be "the download key
for anyone," so it's not a fit for a public launcher handed out to
players.

For a free game, the actual fix is simpler: don't authenticate at all.
The itch.io game page's own "Download Now" button doesn't use the
scoped API either — it loads the page (which hands back a CSRF token +
session cookie), then POSTs that token to a per-upload endpoint that
mints a short-lived, signed CDN url. This module reproduces exactly that
request. It's the same technique community tools like itch-dl and
itchio-downloader use for downloading free games without an account.

Caveat: this isn't a documented, stable API — it's the same request the
page's own JavaScript makes, reverse-engineered from the page's HTML. It
can break if itch.io changes their page markup or endpoint. It has NOT
been tested against the live site from this environment (no network
access here) — test it against the real game page before shipping, and
if the request shape has changed, the error messages below should point
at what to go check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from .itch_api import ItchError

_CSRF_RE = re.compile(r'name="csrf_token"\s+value="([^"]+)"')


@dataclass
class GamePageSession:
    csrf_token: str
    cookies: "requests.cookies.RequestsCookieJar"


def open_game_page(game_url: str) -> GamePageSession:
    """Loads the game's itch.io page once to get the CSRF token + session
    cookie every download request after this needs. Call this once per
    session (or at least once per download) — the token is short-lived."""
    resp = requests.get(game_url, timeout=15)
    if not resp.ok:
        raise ItchError(
            f"couldn't load the game page (HTTP {resp.status_code}): {game_url} "
            "— check GAME_URL in game_config.py is the real page url"
        )
    match = _CSRF_RE.search(resp.text)
    if not match:
        raise ItchError(
            "couldn't find a csrf token on the game page. Either itch.io changed "
            "their page markup (this technique needs updating), or the page isn't "
            "a normal game page — check GAME_URL in game_config.py"
        )
    return GamePageSession(csrf_token=match.group(1), cookies=resp.cookies)


def get_public_download_url(game_url: str, upload_id: int, session: GamePageSession) -> str:
    """Exchanges the game-page session for a signed, time-limited CDN url
    for one upload — the same request the page's own Download button
    makes. Only works while the game is free/pay-what-you-want; itch.io
    will refuse this for anything requiring a purchase."""
    resp = requests.post(
        f"{game_url}/file/{upload_id}",
        params={"source": "game_download"},
        data={"csrf_token": session.csrf_token},
        cookies=session.cookies,
        headers={"X-Requested-With": "XMLHttpRequest"},
        timeout=15,
    )
    if not resp.ok:
        raise ItchError(
            f"itch.io wouldn't hand out a download link for upload {upload_id} "
            f"(HTTP {resp.status_code}). Likely causes: the upload id in "
            "game_config.py is wrong, the game stopped being free, or itch.io "
            "changed how this endpoint works."
        )
    try:
        url = resp.json().get("url")
    except ValueError:
        url = None
    if not url:
        raise ItchError(
            "itch.io's response had no download url in it — the response shape "
            "may have changed; this technique needs updating"
        )
    return url


def download_upload_public(game_url: str, upload_id: int, dest, on_progress=None, expected_sha256=None) -> None:
    """Full no-login download of one upload from a free game's page."""
    from . import itch_api  # local import: avoids a circular import at module load

    session = open_game_page(game_url)
    url = get_public_download_url(game_url, upload_id, session)
    itch_api.download_from_url(url, dest, on_progress=on_progress, expected_sha256=expected_sha256)


@dataclass
class PublicGameInfo:
    title: str | None
    cover_url: str | None


def get_game_metadata(game_url: str) -> PublicGameInfo:
    """Best-effort, unauthenticated title/cover-art lookup via the game
    page's own `data.json` (the same file the page's embed widget reads —
    seen on public itch.io game pages, e.g. thorbjorn.itch.io/tiled/data.json).
    Not part of any documented API; if itch.io drops this, callers should
    treat a failure here as non-fatal, since it's cosmetic only."""
    resp = requests.get(f"{game_url}/data.json", timeout=15)
    if not resp.ok:
        raise ItchError(f"no public metadata at {game_url}/data.json (HTTP {resp.status_code})")
    data = resp.json()
    return PublicGameInfo(title=data.get("title"), cover_url=data.get("cover_image") or data.get("cover_url"))
