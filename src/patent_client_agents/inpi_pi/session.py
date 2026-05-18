"""Session lifecycle for the INPI api-gateway.

INPI's ``api-gateway.inpi.fr`` uses a session-bearer flow rather than
OAuth2. The flow is:

1. ``GET`` any apidiffusion endpoint (e.g. ``/services/apidiffusion/api/marques``)
   to receive a ``XSRF-TOKEN`` cookie. INPI's gateway issues this on the
   first uncredentialed call.
2. ``POST /services/apidiffusion/api/login`` with body
   ``{"username": ..., "password": ...}`` and header
   ``X-XSRF-TOKEN: <token>``. The response sets ``access_token`` and
   ``refresh_token`` cookies and a JSON body that may carry an
   ``expires_in`` hint.
3. Subsequent requests carry ``Authorization: Bearer <access_token>`` +
   ``X-XSRF-TOKEN`` and the session cookies.
4. On 401, attempt one refresh via ``POST /api/refresh``; if that fails,
   re-login from step 1.

Primary source: INPI Documentation Technique API PI v1.0 PDF
(https://www.inpi.fr/sites/default/files/Inpi_doc_tech_API_PI_v1.0_0.pdf)
§3 — flagged auth source per spec §2 and spec synopsis. Per the INPI
CGU (https://data.inpi.fr/content/editorial/cgu), production deployers
must register their own ``data.inpi.fr`` account (BYOK posture).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from law_tools_core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

# Default cookie name INPI's gateway uses for the XSRF token. Spelled
# this way (``XSRF-TOKEN``) and case-sensitive on the wire.
XSRF_COOKIE_NAME = "XSRF-TOKEN"
XSRF_HEADER_NAME = "X-XSRF-TOKEN"

# INPI apidiffusion paths used during session lifecycle. The bootstrap
# endpoint can be any GET-able URL on the gateway; ``/marques`` is the
# canonical no-side-effect probe.
BOOTSTRAP_PATH = "/services/apidiffusion/api/marques"
LOGIN_PATH = "/services/apidiffusion/api/login"
REFRESH_PATH = "/services/apidiffusion/api/refresh"

# Conservative default access-token TTL when the login response does not
# include an ``expires_in`` hint. INPI does not document the TTL; this
# 30-minute default plus a 60-second refresh buffer mirrors the
# defensive pattern in the JPO client.
DEFAULT_TOKEN_TTL_SECONDS = 30 * 60


@dataclass
class InpiSession:
    """Mutable session state for INPI api-gateway calls.

    Captures the full set of credentials that subsequent requests need:
    bearer token (sent as ``Authorization``), refresh token (used to
    re-mint the bearer without re-issuing the user's password), XSRF
    token (sent as ``X-XSRF-TOKEN`` header + held in the cookie jar),
    expiry timestamp (used to decide whether to proactively refresh),
    and the raw cookie dict (passed back to ``httpx.AsyncClient`` for
    cookie-jar reconstruction across requests).
    """

    access_token: str | None = None
    refresh_token: str | None = None
    xsrf_token: str | None = None
    expires_at: datetime | None = None
    cookies: dict[str, str] = field(default_factory=dict)

    def is_expired(self, *, buffer_seconds: int = 60) -> bool:
        """Return True when the access token is missing or about to expire."""
        if not self.access_token or self.expires_at is None:
            return True
        return datetime.now(UTC) >= self.expires_at - timedelta(seconds=buffer_seconds)


def _capture_cookies(response: httpx.Response) -> dict[str, str]:
    """Extract the cookie jar values from a response as a plain dict.

    httpx exposes ``response.cookies`` as a ``Cookies`` proxy; we copy
    out the keys we care about so the dict can be passed back into a
    subsequent client. INPI's gateway emits all session state via
    cookies, so the dict view is sufficient.
    """
    return {name: response.cookies.get(name) or "" for name in response.cookies.keys()}


def _parse_expires_at(body: dict[str, Any] | None) -> datetime:
    """Resolve the ``expires_at`` timestamp from a login/refresh response body.

    INPI's login response is not strictly standardized in the published
    tech doc. We accept either:

    * ``"expires_in"`` — seconds-from-now integer (OAuth convention)
    * ``"exp"`` — Unix epoch seconds (JWT convention)
    * neither — fall back to ``DEFAULT_TOKEN_TTL_SECONDS`` from now

    This keeps the refresh path conservative without taking a hard
    dependency on a single response shape.
    """
    now = datetime.now(UTC)
    if not body:
        return now + timedelta(seconds=DEFAULT_TOKEN_TTL_SECONDS)
    expires_in = body.get("expires_in")
    if isinstance(expires_in, int | float):
        return now + timedelta(seconds=float(expires_in))
    exp = body.get("exp")
    if isinstance(exp, int | float):
        return datetime.fromtimestamp(float(exp), tz=UTC)
    return now + timedelta(seconds=DEFAULT_TOKEN_TTL_SECONDS)


async def fetch_xsrf(client: httpx.AsyncClient, *, base_url: str) -> str:
    """Bootstrap an XSRF-TOKEN cookie from INPI's gateway.

    Performs an uncredentialed ``GET`` on a no-side-effect apidiffusion
    endpoint. INPI sets the ``XSRF-TOKEN`` cookie on the response; we
    return its value so the caller can include it as the
    ``X-XSRF-TOKEN`` header on the subsequent login.

    Raises:
        AuthenticationError: When the bootstrap response does not carry
            the expected cookie (typically a misconfigured base URL or
            a temporary INPI outage).
    """
    url = f"{base_url.rstrip('/')}{BOOTSTRAP_PATH}"
    logger.debug("Bootstrapping INPI XSRF cookie from %s", url)
    response = await client.get(url)
    token = response.cookies.get(XSRF_COOKIE_NAME)
    if not token:
        raise AuthenticationError(
            "INPI gateway did not issue an XSRF-TOKEN cookie on bootstrap",
            response.status_code,
            response.text[:500] if response.text else "",
        )
    return token


async def login(
    client: httpx.AsyncClient,
    username: str,
    password: str,
    xsrf_token: str,
    *,
    base_url: str,
) -> InpiSession:
    """Authenticate against INPI's gateway and capture session state.

    POSTs the credentials to ``/services/apidiffusion/api/login`` with
    the bootstrapped ``X-XSRF-TOKEN`` header. INPI sets the
    ``access_token`` and ``refresh_token`` cookies on the response;
    most deployments also echo them in the JSON body.

    Raises:
        AuthenticationError: 401/403 from the gateway, or absent
            ``access_token`` in both cookies and body.
    """
    url = f"{base_url.rstrip('/')}{LOGIN_PATH}"
    headers = {XSRF_HEADER_NAME: xsrf_token, "Content-Type": "application/json"}
    response = await client.post(
        url, json={"username": username, "password": password}, headers=headers
    )
    if response.status_code in (401, 403):
        raise AuthenticationError(
            "Invalid INPI credentials", response.status_code, response.text[:500]
        )
    if not response.is_success:
        raise AuthenticationError(
            f"INPI login failed: HTTP {response.status_code}",
            response.status_code,
            response.text[:500],
        )

    body: dict[str, Any] | None = None
    try:
        body = response.json()
    except ValueError:
        body = None

    cookies = _capture_cookies(response)
    access = cookies.get("access_token") or (body.get("access_token") if body else None)
    refresh = cookies.get("refresh_token") or (body.get("refresh_token") if body else None)
    xsrf = cookies.get(XSRF_COOKIE_NAME) or xsrf_token

    if not access:
        raise AuthenticationError(
            "INPI login did not return an access_token",
            response.status_code,
            response.text[:500] if response.text else "",
        )

    return InpiSession(
        access_token=access,
        refresh_token=refresh,
        xsrf_token=xsrf,
        expires_at=_parse_expires_at(body),
        cookies=cookies,
    )


async def refresh(
    client: httpx.AsyncClient,
    refresh_token: str,
    xsrf_token: str,
    *,
    base_url: str,
) -> InpiSession:
    """Refresh an INPI session using the refresh-token cookie.

    POSTs to ``/services/apidiffusion/api/refresh`` with the existing
    refresh-token cookie and the XSRF header. Returns a fresh
    :class:`InpiSession` reflecting the rotated access token (and, if
    INPI's gateway chooses to rotate it, the refresh token too).

    Raises:
        AuthenticationError: When the refresh-token cookie is rejected.
            Callers should fall back to a fresh ``fetch_xsrf`` + ``login``.
    """
    url = f"{base_url.rstrip('/')}{REFRESH_PATH}"
    headers = {XSRF_HEADER_NAME: xsrf_token}
    cookies = {"refresh_token": refresh_token, XSRF_COOKIE_NAME: xsrf_token}
    response = await client.post(url, headers=headers, cookies=cookies)
    if response.status_code in (401, 403):
        raise AuthenticationError(
            "INPI refresh token rejected", response.status_code, response.text[:500]
        )
    if not response.is_success:
        raise AuthenticationError(
            f"INPI refresh failed: HTTP {response.status_code}",
            response.status_code,
            response.text[:500],
        )

    body: dict[str, Any] | None = None
    try:
        body = response.json()
    except ValueError:
        body = None

    captured = _capture_cookies(response)
    access = captured.get("access_token") or (body.get("access_token") if body else None)
    new_refresh = (
        captured.get("refresh_token")
        or (body.get("refresh_token") if body else None)
        or refresh_token
    )
    xsrf = captured.get(XSRF_COOKIE_NAME) or xsrf_token

    if not access:
        raise AuthenticationError(
            "INPI refresh did not return a new access_token",
            response.status_code,
            response.text[:500] if response.text else "",
        )

    return InpiSession(
        access_token=access,
        refresh_token=new_refresh,
        xsrf_token=xsrf,
        expires_at=_parse_expires_at(body),
        cookies=captured,
    )


__all__ = [
    "InpiSession",
    "fetch_xsrf",
    "login",
    "refresh",
    "BOOTSTRAP_PATH",
    "LOGIN_PATH",
    "REFRESH_PATH",
    "XSRF_COOKIE_NAME",
    "XSRF_HEADER_NAME",
    "DEFAULT_TOKEN_TTL_SECONDS",
]
