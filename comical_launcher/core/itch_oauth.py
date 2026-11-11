"""itch.io OAuth (implicit grant) URL construction and redirect parsing.

No network calls happen here at all — an embedded browser view does the
actual navigation to itch.io's real login page, and this module only
builds the URL to load and parses whatever comes back once the browser
reaches our redirect URI. The person's itch.io password is typed directly
into itch.io's own page and never passes through this code — only the
resulting OAuth token does.

SETUP REQUIRED: register an OAuth application at
https://itch.io/user/settings/oauth-apps with the redirect URI set to
exactly REDIRECT_URI below, then put the resulting client id in CLIENT_ID.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse

CLIENT_ID = "32172600b4dea4e5d0bd058b1bd0b4a0"
REDIRECT_URI = "http://127.0.0.1:47128/callback"


def is_configured() -> bool:
    return not CLIENT_ID.startswith("YOUR_ITCH")


def authorize_url() -> str:
    params = {
        "client_id": CLIENT_ID,
        "scope": "profile",
        "response_type": "token",
        "redirect_uri": REDIRECT_URI,
    }
    return f"https://itch.io/user/oauth?{urlencode(params)}"


def is_redirect(url: str) -> bool:
    """True once navigation reaches our redirect URI — nothing needs to
    actually be listening there; the embedded view reports the target URL
    (fragment included) as soon as navigation starts, before it tries to
    actually load it."""
    return url.startswith(REDIRECT_URI)


def extract_token(url: str) -> str | None:
    """Parses `access_token` out of the URL fragment (implicit grant)."""
    parsed = urlparse(url)
    fragment_params = dict(parse_qsl(parsed.fragment))
    return fragment_params.get("access_token")


def extract_error(url: str) -> str | None:
    """itch.io reports denial/errors as a query parameter, not a
    fragment, e.g. `?error=access_denied`."""
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))
    return query_params.get("error")
