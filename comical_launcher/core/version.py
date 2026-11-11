"""Launcher version + lightweight semantic-version comparison.

Bump LAUNCHER_VERSION on every release that ships through
launcher_updater.py's manifest — this exact string is what gets compared
against the "version" field the manifest publishes, and it should match
MyAppVersion in installer.iss (that's what actually ends up in the built
installer's version metadata; this constant is what the *running* app
compares itself against).
"""

from __future__ import annotations

LAUNCHER_VERSION = "1.0.0"


def parse(version: str) -> tuple[int, ...]:
    """Turns "1.2.3" into (1, 2, 3) for a real numeric comparison — a
    plain string compare would incorrectly put "1.10.0" before "1.9.0".
    Tolerant of a leading "v" and of non-numeric junk in a segment
    (treated as 0) so a slightly malformed manifest doesn't crash the
    check outright."""
    parts = []
    for chunk in version.strip().lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(remote: str, local: str) -> bool:
    return parse(remote) > parse(local)
