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
