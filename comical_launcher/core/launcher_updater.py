"""Mandatory self-update for the launcher itself.

Unlike the game (see game_updater.py), a launcher update is never
optional — running an old launcher against a changed itch.io upload
layout, a changed API, or a fixed security issue isn't something the
player should be able to defer indefinitely. check_for_update() is
fail-open on any network problem (someone with no internet, or GitHub
being briefly unreachable, should still be able to play) — it raises
UpdateCheckError rather than pretending "no update", and the caller
(main_window.py) treats that the same as "no update found" and lets the
app open normally. But once a real, newer version IS found, the caller
shows a blocking screen (ui/update_view.py) that refuses to let the rest
of the app open until it's applied — there's no skip button anywhere in
that flow, by design.

Source of truth: GitHub Releases, on a *separate* repo from the one this
source code lives in (RELEASES_REPO_OWNER / RELEASES_REPO_NAME below) —
deliberately, so the code repo can be private while this repo stays
public. That split matters because the GitHub REST API only serves
release data for private repos with an authenticated token, and a token
baked into a shipped binary is trivially extractable (`strings` on the
exe) — there's no way to keep it secret once it's in something everyone
downloads. A public releases-only repo (no source, just built installers
and binaries as release assets) sidesteps that entirely: the API call
below is unauthenticated, nothing secret ships in the launcher, and the
worst case of the repo being scraped is "someone finds the exe a version
early," which is nothing.

Until RELEASES_REPO_OWNER/RELEASES_REPO_NAME are filled in (same
placeholder pattern as ROCKY_GAME_ID, DISCORD_CLIENT_ID, ...),
is_configured() is False and check_for_update() always returns None, so
an unconfigured build behaves exactly as if no update system existed.

How to publish a release that this picks up:
  1. Tag it (any of "1.2.0", "v1.2.0" both parse fine — see version.py).
  2. Attach exactly two build assets, named exactly:
       - Windows: ComicalLauncherSetup.exe   (the Inno Setup installer
         from installer.iss — it knows how to upgrade an existing
         install in place)
       - Linux:   ComicalLauncher-linux.tar.gz   (a tarball of the
         *entire* onedir build folder — e.g.
         `tar -czf ComicalLauncher-linux.tar.gz -C dist "Comical Launcher"`
         so the archive contains one top-level folder holding the
         binary plus all its bundled Qt/WebEngine libraries; see
         scripts/build_linux.sh, which produces this automatically)
     (Different filenames won't be found — _ASSET_FILENAMES below is
     exact-match on purpose, so a stray extra asset in the release, like
     a changelog.txt, is never mistaken for the build.)
  3. Optional: the release body becomes the "what's new" text shown on
     the update screen.
  4. Optional but recommended: GitHub computes a `digest` (sha256) for
     each uploaded asset automatically — this module verifies it via
     itch_api's existing checksum check when GitHub provides one, and
     skips verification (not an error) when it doesn't.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import requests

from . import itch_api, version

# Public repo that holds ONLY built releases — no source. See module
# docstring for why this is split from wherever the source code lives.
# e.g. RELEASES_REPO_OWNER = "comical-games", RELEASES_REPO_NAME = "comical-launcher-releases"
RELEASES_REPO_OWNER = ""
RELEASES_REPO_NAME = ""

_GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT = 15

# Exact asset filenames check_for_update() looks for on the latest
# release — see the module docstring's publishing steps.
#
# Linux is a .tar.gz of the whole onedir build, not a bare binary: the
# app ships as a folder full of bundled Qt/WebEngine libraries (see
# comical_launcher.spec's COLLECT step), so a single-file swap would
# leave those libraries stale or missing. See apply_update_and_exit()
# for how the archive gets applied.
_ASSET_FILENAMES = {
    "Windows": "ComicalLauncherSetup.exe",
    "Linux": "ComicalLauncher-linux.tar.gz",
}


def is_configured() -> bool:
    return bool(RELEASES_REPO_OWNER and RELEASES_REPO_NAME)


@dataclass
class LauncherUpdateInfo:
    version: str
    notes: str
    download_url: str
    sha256: Optional[str]


class UpdateCheckError(Exception):
    pass


def check_for_update() -> Optional[LauncherUpdateInfo]:
    """Returns update info if a newer launcher build is published, None
    if already current, not configured, or nothing is published for this
    OS yet. Network/parse problems raise UpdateCheckError — callers
    should treat that as "couldn't check right now", not as "update
    required"."""
    if not is_configured():
        return None

    url = f"{_GITHUB_API_BASE}/repos/{RELEASES_REPO_OWNER}/{RELEASES_REPO_NAME}/releases/latest"
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                # GitHub's API rejects requests with no User-Agent at all.
                "User-Agent": "comical-launcher-updater",
            },
        )
        if resp.status_code == 404:
            # No releases published yet on this repo — not an error,
            # just genuinely nothing to compare against.
            return None
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpdateCheckError(f"couldn't check for updates: {exc}") from exc

    remote_version = data.get("tag_name")
    if not remote_version:
        raise UpdateCheckError("latest release had no tag_name")

    if not version.is_newer(remote_version, version.LAUNCHER_VERSION):
        return None

    expected_name = _ASSET_FILENAMES.get(platform.system())
    if not expected_name:
        return None  # unsupported OS — nothing to offer

    asset = next(
        (a for a in data.get("assets", []) if a.get("name") == expected_name), None
    )
    if asset is None:
        # The release exists and is newer, but whoever published it
        # hasn't attached this platform's build yet (e.g. still building
        # the Windows installer). Same reasoning as the itch.io upload-id
        # 404 case elsewhere: don't block someone on a platform this
        # specific release just doesn't have yet.
        return None

    sha256 = None
    digest = asset.get("digest")  # GitHub-computed, format "sha256:<hex>"
    if digest and digest.startswith("sha256:"):
        sha256 = digest.split(":", 1)[1]

    return LauncherUpdateInfo(
        version=remote_version,
        notes=data.get("body") or "",
        download_url=asset.get("browser_download_url"),
        sha256=sha256,
    )


def download_update(info: LauncherUpdateInfo, on_progress: Optional[Callable] = None) -> Path:
    """Downloads the new build to a temp file and returns its path.
    Reuses itch_api's chunked, verified downloader — it works with any
    direct file URL, not just itch.io's own."""
    suffix = ".exe" if platform.system() == "Windows" else ".tar.gz"
    dest = Path(tempfile.gettempdir()) / f"comical-launcher-update-{info.version}{suffix}"
    itch_api.download_from_url(
        info.download_url, dest, on_progress=on_progress, expected_sha256=info.sha256
    )
    return dest


def _current_executable() -> Path:
    # Frozen (PyInstaller) build: sys.executable is the actual launcher
    # binary the person double-clicked. Running from source (dev/test),
    # there's no meaningful "binary to replace" — fall back to argv[0]
    # purely so the function has something to return; that path is never
    # exercised outside a frozen build in practice.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(sys.argv[0]).resolve()


def apply_update_and_exit(downloaded_path: Path) -> None:
    """Hands off to the freshly downloaded build and ends this process.
    Never returns — callers should assume the app is about to disappear
    the moment this is called, and should have already updated the UI
    to say so beforehand.

    Windows: the download is a full Inno Setup installer (installer.iss
    sets CloseApplications so it closes this exe itself if it's still
    running when the installer starts) — this just launches it detached
    and quits; the installer handles the rest, including relaunching the
    app afterward since installer.iss's [Run] section does that already.

    Linux: the download is a .tar.gz of the entire onedir build folder,
    not a bare binary (see _ASSET_FILENAMES's comment for why — the app
    is a folder full of bundled Qt/WebEngine libraries, and a single-file
    swap would leave those stale). A short detached shell script waits
    for this process to exit, extracts the archive to a temp dir, swaps
    it in for the current app folder (old folder renamed aside first so
    the swap is close to atomic — if the mv into place fails partway,
    the old build is still recoverable from the `.old` folder rather
    than gone), cleans up, and re-execs the new binary. Uses `tar`
    directly via the shell rather than Python's tarfile module because
    this step deliberately runs *after* this process — and therefore
    this whole Python interpreter — has already exited.
    """
    system = platform.system()

    if system == "Windows":
        subprocess.Popen(
            [str(downloaded_path)],
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        os._exit(0)

    if system == "Linux":
        current_exe = _current_executable()
        app_dir = current_exe.parent
        exe_name = current_exe.name
        backup_dir = app_dir.parent / f"{app_dir.name}.old"
        script = (
            f'while kill -0 {os.getpid()} 2>/dev/null; do sleep 0.2; done; '
            f'TMP="$(mktemp -d)"; '
            f'tar -xzf "{downloaded_path}" -C "$TMP"; '
            f'set -- "$TMP"/*/; '
            f'NEWDIR="$1"; '
            f'rm -rf "{backup_dir}"; '
            f'mv "{app_dir}" "{backup_dir}"; '
            f'mv "$NEWDIR" "{app_dir}"; '
            f'rm -rf "{backup_dir}" "$TMP" "{downloaded_path}"; '
            f'chmod +x "{app_dir}/{exe_name}"; '
            f'exec "{app_dir}/{exe_name}"'
        )
        subprocess.Popen(
            ["/bin/sh", "-c", script],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os._exit(0)

    # Unknown platform: nothing safe to automate — surface the path
    # instead of silently doing nothing, so it's at least discoverable.
    raise RuntimeError(
        f"don't know how to self-update on {system}; downloaded build is at {downloaded_path}"
    )
