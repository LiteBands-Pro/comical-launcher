"""Shared HTTP session for every outbound request in this app.

Previously every call site did its own `requests.get(...)`, each of
which opens a fresh TCP connection and — for itch.io calls, does a fresh
TLS handshake too. That's the single biggest easy speed win available
here: itch.io alone gets hit 2-4 times in a typical boot+install run
(whoami, page load, csrf exchange, cover art, download), and a plain
`requests` call has no way to reuse the connection between them.

A single module-level `requests.Session`, shared by every caller, keeps
a small connection pool alive so the second and later requests to the
same host skip DNS + TCP + TLS entirely and reuse the warm connection —
routinely a 100-300ms saving per request on top of just being lighter on
CPU. It also gets automatic retries with backoff for the transient
"connection reset" / 5xx blips that a game-sized download over a home
connection will occasionally hit.
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_retry = Retry(
    total=2,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 503, 504),
    allowed_methods=("GET", "HEAD", "POST"),
)
_adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=_retry)

session = requests.Session()
session.mount("https://", _adapter)
session.mount("http://", _adapter)
