"""itch.io API client: profile lookup, game/cover-art lookup, and
downloads. Downloads use several concurrent ranged requests when the
server supports them and fall back to a single stream otherwise — either
way, chunked with progress callbacks and SHA-256 verification.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

ITCH_API_BASE = "https://itch.io/api/1"
# Number of concurrent range requests for the fast path. 4 is a common
# sweet spot for saturating typical CDN throughput without hammering the
# server or disk with too many concurrent writers.
PARALLEL_PARTS = 4
CHUNK_SIZE = 256 * 1024
# Range requests and compressed responses don't mix safely: a byte range
# applies to whichever stream the server sends, and if that's gzipped,
# "bytes 1000-1999" means something different than 1000 raw file bytes —
# plus requests' automatic gzip decoding chokes on a partial compressed
# stream. Forcing identity encoding keeps every byte offset meaning
# exactly what the code assumes it means.
_NO_COMPRESSION_HEADERS = {"Accept-Encoding": "identity"}

ProgressCallback = Callable[[int, int, float, float], None]
# (downloaded_bytes, total_bytes, speed_bytes_per_sec, eta_seconds) -> None


class ItchError(Exception):
    pass


@dataclass
class GameInfo:
    id: int
    title: str
    cover_url: Optional[str]


def whoami(api_key: str) -> str:
    """Returns the itch.io username for this key, or raises ItchError."""
    resp = requests.get(f"{ITCH_API_BASE}/{api_key}/me", timeout=15)
    if not resp.ok:
        raise ItchError(f"failed to fetch itch.io profile: {resp.status_code}")
    data = resp.json()
    try:
        return data["user"]["username"]
    except (KeyError, TypeError) as exc:
        raise ItchError("unexpected response from itch.io") from exc


def _explain_status(resp: "requests.Response", what: str, id_: int) -> str:
    """Turns a raw itch.io HTTP status into a message that actually says
    what to go check, instead of just the number."""
    if resp.status_code in (401, 403):
        return (
            f"itch.io rejected this account for {what} {id_} (HTTP {resp.status_code}). "
            "Either this itch.io account doesn't own/have access to the game "
            "(claim it on its itch.io page first), or the login token expired — "
            "try Settings -> Sign out, then sign in again."
        )
    if resp.status_code == 404:
        return (
            f"itch.io has no {what} with id {id_} (HTTP 404). Double check this id "
            "against your itch.io creator dashboard — Edit game -> the game id is in "
            "that URL, and each upload's id is in the URL when you click into it "
            "under Uploads."
        )
    return f"failed to fetch {what} {id_}: HTTP {resp.status_code}"


def get_game(api_key: str, game_id: int) -> GameInfo:
    resp = requests.get(f"{ITCH_API_BASE}/{api_key}/game/{game_id}", timeout=15)
    if not resp.ok:
        raise ItchError(_explain_status(resp, "game", game_id))
    game = resp.json().get("game", {})
    return GameInfo(
        id=game.get("id", game_id),
        title=game.get("title", "Rocky"),
        cover_url=game.get("cover_url"),
    )


def _resolve_download_url(api_key: str, upload_id: int) -> str:
    resp = requests.get(f"{ITCH_API_BASE}/{api_key}/upload/{upload_id}/download", timeout=15)
    if not resp.ok:
        raise ItchError(_explain_status(resp, "upload", upload_id))
    url = resp.json().get("url")
    if not url:
        raise ItchError("itch.io response had no download url")
    return url


def download_upload(
    api_key: str,
    upload_id: int,
    dest: Path,
    on_progress: Optional[ProgressCallback] = None,
    expected_sha256: Optional[str] = None,
    max_bytes_per_sec: int = 0,
) -> None:
    """Downloads an upload to `dest` using a real itch.io API key (one
    with game:view:uploads — i.e. from your own account settings, not an
    OAuth token). Only works for accounts that own/have access to the
    game. For public, no-login downloads of a free game, see
    itch_public.download_upload_public instead."""
    url = _resolve_download_url(api_key, upload_id)
    download_from_url(url, dest, on_progress, expected_sha256, max_bytes_per_sec)


def download_from_url(
    url: str,
    dest: Path,
    on_progress: Optional[ProgressCallback] = None,
    expected_sha256: Optional[str] = None,
    max_bytes_per_sec: int = 0,
) -> None:
    """The actual chunked/parallel/verified download, once a real,
    fetchable file URL is already known — shared by the api-key path
    above and the public no-login path in itch_public.py."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    supports_ranges = False
    try:
        head = requests.head(url, timeout=15, allow_redirects=True, headers=_NO_COMPRESSION_HEADERS)
        total = int(head.headers.get("Content-Length", 0))
        supports_ranges = head.headers.get("Accept-Ranges", "").lower() == "bytes"
    except requests.RequestException:
        pass

    if supports_ranges and total > 0 and max_bytes_per_sec == 0:
        _download_parallel(url, dest, total, on_progress)
    else:
        _download_single_stream(url, dest, total, on_progress, max_bytes_per_sec)

    if expected_sha256:
        _verify_sha256(dest, expected_sha256)


def _download_parallel(
    url: str, dest: Path, total: int, on_progress: Optional[ProgressCallback]
) -> None:
    # Preallocate the destination file to its final size.
    with open(dest, "wb") as f:
        f.truncate(total)

    part_size = -(-total // PARALLEL_PARTS)  # ceil division
    downloaded = 0
    lock = threading.Lock()
    stop_reporting = threading.Event()

    def add_downloaded(n: int) -> None:
        nonlocal downloaded
        with lock:
            downloaded += n

    def report_loop() -> None:
        start = time.monotonic()
        while not stop_reporting.is_set():
            with lock:
                d = downloaded
            elapsed = max(time.monotonic() - start, 0.001)
            speed = d / elapsed
            remaining = max(total - d, 0)
            eta = remaining / speed if speed > 0 else 0.0
            if on_progress:
                on_progress(d, total, speed, eta)
            if d >= total:
                break
            time.sleep(0.15)

    reporter = threading.Thread(target=report_loop, daemon=True)
    reporter.start()

    def fetch_range(start: int, end: int) -> None:
        headers = {"Range": f"bytes={start}-{end}", **_NO_COMPRESSION_HEADERS}
        with requests.get(url, headers=headers, stream=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(dest, "r+b") as f:
                f.seek(start)
                for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                    if not chunk:
                        continue
                    f.write(chunk)
                    add_downloaded(len(chunk))

    ranges = []
    start = 0
    while start < total:
        end = min(start + part_size, total) - 1
        ranges.append((start, end))
        start += part_size

    with ThreadPoolExecutor(max_workers=PARALLEL_PARTS) as pool:
        futures = [pool.submit(fetch_range, s, e) for s, e in ranges]
        for fut in futures:
            fut.result()  # re-raises any exception from the worker

    stop_reporting.set()
    reporter.join(timeout=1)
    if on_progress:
        on_progress(total, total, 0.0, 0.0)


def _download_single_stream(
    url: str,
    dest: Path,
    known_total: int,
    on_progress: Optional[ProgressCallback],
    max_bytes_per_sec: int,
) -> None:
    with requests.get(url, stream=True, timeout=30, headers=_NO_COMPRESSION_HEADERS) as resp:
        resp.raise_for_status()
        total = known_total or int(resp.headers.get("Content-Length", 0))

        downloaded = 0
        start_time = time.monotonic()
        window_start = start_time
        window_bytes = 0

        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                window_bytes += len(chunk)

                if max_bytes_per_sec > 0:
                    elapsed = time.monotonic() - window_start
                    window_cap = max_bytes_per_sec / 10  # per 100ms
                    if window_bytes >= window_cap:
                        target = 0.1
                        if elapsed < target:
                            time.sleep(target - elapsed)
                        window_start = time.monotonic()
                        window_bytes = 0

                if on_progress:
                    elapsed_total = max(time.monotonic() - start_time, 0.001)
                    speed = downloaded / elapsed_total
                    remaining = max(total - downloaded, 0)
                    eta = remaining / speed if speed > 0 else 0.0
                    on_progress(downloaded, total, speed, eta)


def _verify_sha256(path: Path, expected: str) -> None:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    actual = hasher.hexdigest()
    if actual.lower() != expected.lower():
        os.remove(path)
        raise ItchError(f"checksum mismatch: expected {expected}, got {actual}")
