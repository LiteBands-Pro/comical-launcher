# Comical Launcher — Releases

This repo holds **built releases only** — no source code lives here.

It exists purely so [Comical Launcher](#) can check for and download
updates to itself. The actual source is in a private repo; this one is
public on purpose, because the launcher's auto-updater calls GitHub's
Releases API without authentication (`GET /repos/<owner>/<repo>/releases/latest`),
and that endpoint only serves data for private repos with a token — which
can't be kept secret once it's baked into a binary that gets downloaded by
everyone (a `strings` pass on the exe pulls it right back out). Splitting
the built binaries into their own public repo, with no source in it,
sidesteps that entirely: nothing sensitive lives here to leak.

## What's here

Just [Releases](../../releases) — each one a tagged version with two
attached files:

| Asset | Platform |
|---|---|
| `ComicalLauncherSetup.exe` | Windows — an Inno Setup installer that upgrades an existing install in place |
| `ComicalLauncher-linux.tar.gz` | Linux — a tarball of the full app folder (binary + bundled Qt/WebEngine libraries) |

No source, no issues expected, no pull requests expected. If you're
looking for the actual codebase, you're in the wrong repo — this one is
infrastructure, not a project to contribute to.

## How the launcher uses this repo

On every launch, before showing its UI, the launcher checks this repo's
latest release. If the release's tag is newer than the version currently
running, it shows a **mandatory** update screen — no skip button — that
downloads and applies whichever asset matches the person's OS. If GitHub
is unreachable or there's no internet, that's treated as "no update
available," not as "update required" — a network hiccup never blocks
someone from playing.

Version comparison is numeric (`1.10.0 > 1.9.0`), and tolerates a leading
`v` on the tag (`v1.2.0` and `1.2.0` are equivalent).

## Publishing a new version

1. Build both platforms — `scripts/build_windows.ps1` and
   `scripts/build_linux.sh` in the source repo produce the two files
   below automatically, named correctly.
2. Push a new tag here (e.g. `1.2.0` or `v1.2.0`) and create a GitHub
   Release from it.
3. Attach exactly these two files, with these **exact** filenames — the
   launcher matches on filename, so anything else uploaded (a changelog,
   a zip of source, etc.) is simply ignored and safe to include if you
   want:
   - `ComicalLauncherSetup.exe`
   - `ComicalLauncher-linux.tar.gz`
4. Write the release description as normal release notes — it's shown
   verbatim on the update screen as "what's new."
5. Publish. GitHub auto-computes a SHA-256 digest for each uploaded
   asset; the launcher verifies it automatically before applying the
   update, so no extra checksum step is needed on your end.

That's it — every launcher instance picks this release up on its next
launch.
