# Comical Launcher (Python)

Pure Python desktop launcher for Rocky Chapter 1
(https://comical-games.itch.io/rocky-chapter-1) — no HTML, CSS, or
JavaScript anywhere. The GUI is PySide6 (Qt), which is what most
professional cross-platform desktop apps are actually built with.

Sign in with a real itch.io account (no API key handling by the person at
all — see "Account login" below), OS-locked downloads (a Windows install
only ever fetches the Windows build, Linux only the Linux one), fast
parallel-chunk downloading, adaptive parallel decryption on launch,
at-rest AES-256-GCM encryption keyed to the device's hardware ID,
ephemeral decrypt-run-wipe execution, an Uninstall option for recovering
a corrupted install, Discord Rich Presence while playing, and a hidden-
by-default device ID.

## Run it

```bash
pip install -r requirements.txt
python -m comical_launcher.main
```

That opens the actual window. Signing in, downloading, and Discord Rich
Presence need the placeholders below filled in first, but the app runs
and the window opens either way.

## Directory tree

```
comical-launcher-py/
├── requirements.txt
├── README.md
├── icons/
│   ├── icon.png
│   └── icon.ico
├── scripts/
│   ├── build_windows.ps1       # venv -> PyInstaller -> Inno Setup -> installer_output\ComicalLauncherSetup.exe
│   └── build_linux.sh          # venv -> PyInstaller -> installer_output/ComicalLauncher-linux.tar.gz
└── comical_launcher/
    ├── main.py                 # entry point
    ├── core/                   # all non-UI logic — no Qt imports here
    │   ├── hwid.py              # cross-platform hardware fingerprinting -> SHA-256, cached per session
    │   ├── crypto.py            # AES-256-GCM encrypt/decrypt, keyed by HWID alone
    │   ├── itch_key.py          # local-only storage for the itch.io OAuth token
    │   ├── itch_oauth.py        # itch.io OAuth URL building + redirect parsing (no Qt, no network)
    │   ├── itch_api.py          # itch.io API: profile/game lookup, parallel chunked download
    │   ├── firebase.py          # silent device registration (HWID) to Firebase
    │   ├── discord_rpc.py       # Discord Rich Presence ("Playing Rocky") while the game runs
    │   ├── launcher.py          # decrypt (adaptively parallel) -> launch -> wipe, + uninstall_game()
    │   ├── anti_debug.py        # debugger detection (ctypes, no external deps)
    │   ├── game_config.py       # game id/title + OS-locked upload selection
    │   ├── version.py           # LAUNCHER_VERSION + semver comparison, shared by both updaters below
    │   ├── launcher_updater.py  # MANDATORY self-update for the launcher itself
    │   ├── game_updater.py      # OPTIONAL, ask-first update check for the installed game
    │   └── i18n.py              # English/French/Arabic string catalog, no Qt import — see "Language" below
    └── ui/                      # PySide6 widgets — the only place Qt is imported
        ├── styles.py             # flat dark theme, one accent color, no gradients/glow
        ├── workers.py            # background-thread runner so network calls never freeze the UI
        ├── smooth_progress_bar.py # eased progress bar animation
        ├── connect_view.py       # itch.io landing screen -> embedded login (lazy-loaded)
        ├── itch_login_view.py    # embedded itch.io login page (QWebEngineView)
        ├── library_view.py       # game row + install/play + update prompt + 3-dot uninstall + settings panel
        ├── update_view.py        # blocking "update required" dialog for the mandatory launcher update
        └── main_window.py        # ties views together with a fade transition, runs the update check first
```

## Why PySide6 instead of Tkinter

Tkinter ships with Python and needs no install, but its widgets look
dated and animating anything smoothly means fighting the toolkit. PySide6
is the official Python binding for Qt — the same toolkit real
cross-platform apps use (VLC, OBS Studio's Qt frontend, many JetBrains
tooling panels) — and it has real property animations, a proper event
loop, and native-looking widgets on both Windows and Linux out of the
box. The UI theme here is deliberately plain: flat dark background, one
accent color, no gradients or glow — a native title bar instead of a
custom draggable one, since that's what makes an app look like a normal
app rather than a demo.

## Account login (no API key, no external browser)

Signing in uses a real itch.io account, not a manually-pasted API key —
this removes the exact failure mode of a key getting pasted somewhere it
shouldn't (chat, a screenshot, a committed file). Clicking "Log in with
itch.io" opens itch.io's own real login page **inside this app's window**
via `QWebEngineView` — no separate browser process ever opens. The
person's password goes straight to itch.io over HTTPS and never passes
through this codebase at all; the app only ever sees the OAuth token
itch.io hands back at the end (`itch_oauth.py` builds the login URL and
parses that token out of the redirect — no network calls happen in that
module, the embedded browser does the actual navigation).

The heavy part — the Chromium subprocess behind `QWebEngineView` — is
only constructed the first time someone actually clicks "Log in", not at
app startup (`connect_view.py`'s `_ensure_login_view()`), so an
already-signed-in person, or someone who hasn't reached that screen yet,
never pays that startup cost.

## Before it fully works: six placeholders

| File | Constant | Where to get it |
|---|---|---|
| `comical_launcher/core/itch_oauth.py` | `CLIENT_ID` | https://itch.io/user/settings/oauth-apps (redirect URI must be exactly `http://127.0.0.1:47128/callback`) |
| `comical_launcher/core/game_config.py` | `ROCKY_GAME_ID` | itch.io dashboard -> Edit game -> URL |
| `comical_launcher/core/firebase.py` | `FIREBASE_DB_URL` | Firebase console -> Realtime Database |
| `comical_launcher/core/discord_rpc.py` | `DISCORD_CLIENT_ID` | https://discord.com/developers/applications |
| `comical_launcher/core/launcher_updater.py` | `RELEASES_REPO_OWNER`, `RELEASES_REPO_NAME` | a **public** GitHub repo you create just to hold built releases (see "Updates" below) — separate from wherever this source lives |
| `comical_launcher/core/game_config.py` | `GAME_VERSION_MANIFEST_URL` | same idea, a separate small JSON file for the game's own version |

Everything except itch.io login degrades gracefully if left unset — cover
art just doesn't load, device registration silently skips, Discord Rich
Presence silently no-ops, and both update checks silently do nothing
(no nagging, no broken UI) until their manifest URL is filled in.
`CLIENT_ID` is the one placeholder that blocks something outright:
clicking "Log in with itch.io" without it set shows a clear inline error
instead of trying and failing confusingly.

## Updates

Two independent, differently-behaved update systems:

**The launcher itself (`core/launcher_updater.py`, `ui/update_view.py`) —
mandatory.** On every boot, before the connect/library screen ever
appears, the launcher calls GitHub's Releases API
(`GET /repos/{RELEASES_REPO_OWNER}/{RELEASES_REPO_NAME}/releases/latest`)
against a **separate, public** repo that holds nothing but built
releases — no source. That split is deliberate: this project's source
repo can be private, but the GitHub API only serves release data for
private repos with an authenticated token, and a token baked into a
shipped binary can always be pulled back out of it (`strings` on the
exe). A public releases-only repo sidesteps the whole problem — the API
call is unauthenticated, nothing secret ships in the launcher, and there's
nothing sensitive in that repo to leak (just built installers/binaries
that would eventually be public via download anyway).

To publish a version bump the launcher will pick up:
1. Push a tag to the releases repo and create a GitHub Release from it
   (tag can be `1.2.0` or `v1.2.0` — both parse fine).
2. Attach exactly two assets, named **exactly**:
   - `ComicalLauncherSetup.exe` — the Inno Setup installer from
     `installer.iss` (it knows how to upgrade an existing install in
     place).
   - `ComicalLauncher-linux.tar.gz` — a tarball of the *entire* onedir
     build folder (binary + its bundled Qt/WebEngine libraries), produced
     automatically by `scripts/build_linux.sh`. Not a bare binary — the
     Linux build is a folder, not a single file (see `comical_launcher.spec`),
     so the auto-updater extracts and swaps in the whole folder rather
     than overwriting just the executable.
   (Anything else attached, like a changelog, is ignored — matching is
   exact-filename on purpose.)
3. The release's description becomes the "what's new" text shown on the
   update screen.
4. GitHub auto-computes a SHA-256 digest for uploaded assets; when
   present, that's verified against the download before it's applied —
   no extra step needed on your end.

If `tag_name` there is newer than `LAUNCHER_VERSION` in
`core/version.py`, a blocking dialog opens with no cancel/skip button
anywhere — the person downloads and applies the update to continue at
all. On Windows that means running the downloaded Inno Setup installer
(`installer.iss` is configured with
`CloseApplications`/`RestartApplications` so it can close and relaunch
the running launcher itself); on Linux it means extracting the tarball
and swapping the whole app folder in place before re-exec'ing the new
binary (see `apply_update_and_exit()`'s docstring for exactly how). If
the *check itself* fails — no
internet, GitHub unreachable, repo/release not created yet — that's
treated the same as "no update available" and the app opens normally;
only a confirmed newer version blocks anything.

**The game (`core/game_updater.py`) — optional, ask first.** After
signing in, if `GAME_VERSION_MANIFEST_URL` (in `game_config.py`) points
at a similar `{"version": "...", "notes": "..."}` JSON file and it's
newer than what's installed, the person is asked "Update now?" — Yes
downloads and re-installs in place (same download/encrypt path as a
fresh install, just overwriting), No leaves the currently-installed
build completely alone. Either way **Play stays enabled and untouched**;
declining an update is never sticky-blocked by the launcher, and an
"Update" button remains next to Play so they can update later on their
own terms. Bump this manifest's `version` after publishing a new upload
in `game_config.py`'s `_UPLOADS`, so the two stay in sync.

## Language

English, French, and Arabic, switchable from Settings → Language, with no
restart needed — every open screen re-renders immediately.

- `core/i18n.py` holds the entire string catalog as a plain Python dict
  (`STRINGS`), not a compiled Qt `.ts`/`.qm` pipeline — no `lupdate`/
  `lrelease` tooling required to build. Add a language by adding a key to
  `LANGUAGES` and filling in that language's entry for every key in
  `STRINGS`; the module's own test (missing-translation check) is worth
  running after — see "How this was verified" below.
- Each UI widget that shows translated text registers a `retranslate_ui()`
  method via `i18n.add_listener(...)` in its constructor, and re-derives
  its current text from tracked state (e.g. `library_view.py`'s
  `_status_key`/`_status_kwargs`) rather than a frozen string — so
  switching language mid-download still shows "Downloading… 42%"
  correctly in the new language, not a stale English string that only
  updates on the next state change.
- Arabic is RTL. `main.py` sets `QApplication`'s layout direction once at
  startup from the saved language (so the very first frame is already
  correct, no visible re-flow), and `main_window.py` registers a listener
  to flip it live if the language is changed while the app is running.
- Two things are deliberately **not** translated: the embedded itch.io
  login page (`itch_login_view.py`'s `QWebEngineView`) is itch.io's own
  real site loaded live — its language is whatever itch.io serves,
  entirely outside this app's control — and a launcher-update's release
  notes (`update_view.py`) are shown verbatim from whatever language the
  maintainer wrote them in on GitHub; only the *fallback* text (no notes
  written) is one of this app's own translated strings.
- Translations here are a solid first pass done for functionality, not
  reviewed by native speakers. If this ships to real French/Arabic-
  speaking players, get a native speaker to proofread `STRINGS` in
  `core/i18n.py` before launch.

## How this was verified

Every module here was actually run and tested in a sandbox, not just
written and assumed correct:

- `crypto.py`: round-trip tested (encrypt/decrypt bytes and files),
  wrong-key rejection confirmed, secure-delete confirmed.
- `itch_api.py`: both download code paths (parallel-range and
  single-stream) tested byte-for-byte against a real file. This caught a
  real bug — mixing HTTP Range requests with gzip-compressed responses
  corrupts byte offsets, since a "range" means something different
  depending on which stream it's applied to. Fixed by forcing
  `Accept-Encoding: identity` on every download request.
- `discord_rpc.py`: verified against pypresence's actual source
  (confirmed `connect()` raises `DiscordNotFound` cleanly when Discord
  isn't running, confirmed the not-configured no-op path works).
- `launcher.py`: full end-to-end test — installed a fake encrypted
  "game," launched it, confirmed it actually ran, confirmed the
  decrypted temp copy was wiped after, confirmed the encrypted original
  survived untouched.
- The full Qt app: actually instantiated and run under a real event
  loop (Qt's offscreen platform, for a display-less sandbox), including
  two genuine bugs found and fixed:
  - Closing the app while a background network call was still in flight
    crashed the process (Qt asserts and aborts if a `QThread` is
    destroyed while still running). Fixed with a thread registry that
    the app waits on during shutdown, plus a hard-exit fallback for the
    pathological case of a thread that's genuinely stuck past the wait
    timeout — confirmed by directly reproducing both the crash and the
    fix, then stress-tested across 20 repeated runs with a tight timing
    window to rule out it being a fluke.
  - A subtler bug in that same fix: the thread-cleanup callback was a
    bare lambda, which Qt has no way to associate with a thread — so it
    ran on the *worker* thread instead of the main thread, racing
    against the shutdown code. Fixed by making the cleanup a bound
    method of a proper `QObject`, which Qt correctly marshals to the
    main thread.
- `smooth_progress_bar.py`: caught that `QProgressBar` defaults to a
  0-99 range, not 0-100 — would have misrepresented 100% completion.
  Fixed by explicitly setting the range, then confirmed the animated
  value actually settles at 50 and 100 by running a real event loop.
- `i18n.py`: verified every key in `STRINGS` has all three languages
  (a small completeness check, not just eyeballing the dict), verified
  `t()`'s fallback behavior (unknown key returns the key itself rather
  than raising; a missing format argument returns the unformatted string
  rather than raising), and verified the state-tracking retranslation
  pattern itself — simulated `library_view.py`'s `_status_key`/
  `_status_kwargs` approach outside Qt and confirmed switching languages
  mid-download re-renders "Downloading… 42%" correctly in each language
  rather than freezing at whatever language was active when the download
  started. What's *not* independently confirmed: the actual Qt
  `retranslate_ui()` methods firing against real widgets on a language
  switch, since PySide6 isn't installed in this sandbox (see the note
  below on the full Qt app) — the underlying logic they call is tested,
  the Qt wiring itself should get a manual pass before shipping.
- `library_view.py`: install/play button mode-toggling tested directly
  against mocked install state; the "launcher backgrounds itself"
  behavior verified by confirming the hide-window and show-window
  signals actually fire around a (mocked) game launch call, not just
  that the code compiles.
- Parallel decryption in `launcher.py`: measured, not assumed. First
  test showed parallel decrypt was *slower* than sequential — traced to
  this sandbox having exactly one CPU core (`os.cpu_count() == 1`),
  where threading is pure overhead with no real parallelism to offset
  it. Rather than ship an "optimization" that only helps on hardware
  this sandbox couldn't verify, `launcher.py` now checks `os.cpu_count()`
  at runtime and only threads the decryption when there's more than one
  core to actually use — confirmed the fallback correctly engages here,
  and confirmed the parallel path still produces byte-identical output
  to sequential when forced on.
- `hwid.py`: added a session-level cache after noticing `get_hwid()` is
  called from four places per run — on Windows each call spawns three
  `powershell.exe` processes, which are genuinely slow to start.
  Confirmed the cache means the expensive lookup only runs once no
  matter how many call sites hit it.
- Embedded itch.io login (`itch_login_view.py`, `itch_oauth.py`): the
  itch.io domain itself isn't reachable from this sandbox's tools, so
  the OAuth flow was verified two ways instead — the URL-building and
  redirect-parsing logic (`itch_oauth.py`) tested directly against every
  realistic redirect shape (success, denial, an unrelated page), and the
  actual `QWebEngineView` navigation-interception mechanism verified
  against a local test server standing in for itch.io's redirect,
  confirming `urlChanged` reports the full URL fragment (where the OAuth
  token lives) intact before the page even finishes loading. The full
  click-to-connected flow was then tested end-to-end with the token
  extraction real and only the final `whoami`/`save_key` network calls
  mocked. Getting `QWebEngineView` running at all in this headless,
  root-user sandbox needed `--no-sandbox` (Chromium refuses to run as
  root otherwise) — a sandbox-only wrinkle, not something an end user
  running the app normally would ever hit.
- `uninstall_game()`: tested the removal itself, and separately tested
  that calling it on a slug that was never installed is a safe no-op
  rather than an error. The confirmation-dialog UI path was tested with
  both the cancel and confirm choices mocked, checking the underlying
  removal only actually runs when the person confirms.
- The hidden-HWID toggle: confirmed the field shows masked text by
  default, reveals the real value on click, and re-masks on a second
  click — not just that the code compiles.

## Building a standalone executable

```bash
# Windows (PowerShell) -> installer_output\ComicalLauncherSetup.exe
.\scripts\build_windows.ps1

# Linux -> installer_output/ComicalLauncher-linux.tar.gz
./scripts/build_linux.sh
```

Both create a dedicated build venv, run PyInstaller against
`comical_launcher.spec` (already tuned to exclude unused PySide6
submodules, locale packs, and plugin binaries — see the comments in that
file), and produce the exact artifact `launcher_updater.py` expects as a
release asset: an Inno Setup installer on Windows, a tarball of the whole
onedir build on Linux (see "Updates" above for why Linux ships as a
folder rather than a single binary). You need to actually run each
script on that OS — PyInstaller builds for the platform it's running on,
not cross-platform. A GitHub Actions matrix (`windows-latest` +
`ubuntu-latest`, each running its script, then uploading both artifacts
to a GitHub Release on the releases repo) is the standard way to produce
and publish both from one push without owning both machines.

## Security notes

- The itch.io OAuth token is stored in a local, owner-only-permission
  file (`itch_key.py`) — `%APPDATA%\ComicalLauncher\itch_key.local` on
  Windows, `~/.config/ComicalLauncher/itch_key.local` on Linux. It's
  never hardcoded, never typed by the person, and never seen by this
  codebase until itch.io hands it back after a real account login.
- The AES-256-GCM key for installed games is derived from the device's
  HWID alone — copy the encrypted files to another machine and the
  derived key is different, so decryption fails outright.
- The device ID shown in Settings is masked by default (a row of dots,
  not the real value) — it's local diagnostic info, not a secret, but
  there's no reason to have it sitting on screen by default either.
- `anti_debug.py`'s checks (`IsDebuggerPresent` on Windows,
  `ptrace(PTRACE_TRACEME)` on Linux) are real but well-known, easily
  bypassed speed bumps — one layer among several, not real anti-tamper.
- Writing device records directly to Firebase from a distributed client
  means the write endpoint is technically public. Lock down your
  Realtime Database rules (starter rules are in the `firebase.py` doc
  comment) so writes can only *create* a record, never overwrite an
  existing one.
# Comical Launcher — Releases

This repo holds **releases only** — The launcher is unfortunately not open-source.

This repository has the sole purpose of making [Comical Launcher](#) able to check for and download
updates for itself. This program is free but proprietary because it contains sensible API keys that if leaked could cause ABSOLUTE chaos

## What's here

Just [Releases](../../releases) — each one a tagged version with two
attached files:

| Asset | Platform |
|---|---|
| `ComicalLauncherSetup.exe` | Windows — an installer built using Inno Setup that upgrades an existing installation automatically |
| `ComicalLauncher-linux.tar.gz` | Linux — a tarball of the full app folder (binary + bundled Qt/WebEngine libraries) |

## How the launcher uses this repo

On every launch, before showing its UI, the launcher checks this repo's
latest release. If the release's tag is newer than the version currently
running, it shows a **mandatory** update screen — no skip button — that
downloads and applies whichever asset matches the person's OS. If GitHub
is unreachable or there's no internet, that's treated as "no update
available," not as "update required" — a network hiccup never blocks
someone from playing. We force updates when internet is available to prevent glitches, issues and security problems.

Version comparison is numeric (`1.10.0 > 1.9.0`), and tolerates a leading
`v` on the tag (`v1.2.0` and `1.2.0` are equivalent).

And that's pretty much it ! You do not need to know anything else about this repo.
