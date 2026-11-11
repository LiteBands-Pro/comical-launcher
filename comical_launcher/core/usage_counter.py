"""Anonymous, zero-setup launch counting via CountAPI — a free, keyless
hit-counter service: one GET request increments a counter, no account,
no project setup, no database rules to write. This replaces the earlier
Firebase-based device registration, which needed a real project + a
Realtime Database URL + security rules before it did anything at all.

Every launch pings this once, fire-and-forget — same shape as the old
Firebase call: never blocks the UI, never raises visibly, failures are
just logged and ignored.

To see the current count at any time, visit this in a browser:
    https://api.countapi.xyz/get/<COUNTAPI_NAMESPACE>/<COUNTAPI_KEY>

Caveat: CountAPI has no auth, so this only counts *launches*, not unique
people (there's no login-free way to dedupe that without running your
own backend) — and technically anyone who learns your namespace/key pair
could also hit or read it, since there's no access control. Fine for a
rough usage number; not fine as a real analytics system.
"""

from __future__ import annotations

import requests

# Change these to something specific to your project — CountAPI counters
# are identified by name only, so a generic key risks colliding with (or
# being bumped by) somebody else's counter.
COUNTAPI_NAMESPACE = "comical-launcher"
COUNTAPI_KEY = "ut_GfI6axj14DHXt5OPQYYZzPWNbttuIxO1mM2286RW"

COUNTAPI_BASE = "https://api.countapi.xyz"


def record_launch() -> None:
    """Fire-and-forget: pings the hit counter once per app launch. Any
    failure (no network, service down) is swallowed — this is usage
    tracking, not something the app should ever depend on to run."""
    try:
        requests.get(f"{COUNTAPI_BASE}/hit/{COUNTAPI_NAMESPACE}/{COUNTAPI_KEY}", timeout=10)
    except requests.RequestException as exc:
        print(f"[usage_counter] ping failed: {exc}")
