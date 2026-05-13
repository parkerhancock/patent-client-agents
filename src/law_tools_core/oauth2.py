"""OAuth 2.0 client_credentials authentication for httpx clients.

Generic httpx.Auth implementation of RFC 6749 §4.4 client_credentials grant.
Use as the ``auth=`` argument to ``BaseAsyncClient`` (or any httpx client).

Token caching:
    First request fetches a token, then injects ``Authorization: Bearer ...``.
    Subsequent requests reuse the cached token until it expires (minus a
    30-second safety margin). On HTTP 401 the cached token is discarded,
    a fresh one is fetched, and the original request is retried once. A
    second 401 surfaces as :class:`AuthenticationError`.

Token endpoint conventions:
    Credentials default to HTTP Basic in the token request (most common).
    Set ``credentials_in_body=True`` for servers that expect ``client_id``
    + ``client_secret`` in the form body instead. ``scope`` is included
    as a form parameter when provided.

Example::

    class IpAustraliaPatentsClient(BaseAsyncClient):
        DEFAULT_BASE_URL = "https://production.api.ipaustralia.gov.au/.../v1"
        CACHE_NAME = "ip_australia_patents"

        def __init__(self, *, client_id: str, client_secret: str) -> None:
            super().__init__(
                auth=OAuth2ClientCredentialsAuth(
                    token_url="https://portal.api.ipaustralia.gov.au/oauth2/token",
                    client_id=client_id,
                    client_secret=client_secret,
                ),
            )
"""

from __future__ import annotations

import base64
import datetime as dt
import logging
from collections.abc import Generator

import httpx

from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)

_EXPIRY_SAFETY_MARGIN = dt.timedelta(seconds=30)
_FALLBACK_TOKEN_LIFETIME = dt.timedelta(seconds=3600)


class OAuth2ClientCredentialsAuth(httpx.Auth):
    """RFC 6749 §4.4 client_credentials grant for httpx clients.

    See module docstring for the full contract.
    """

    requires_response_body = True

    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str | None = None,
        credentials_in_body: bool = False,
        extra_token_params: dict[str, str] | None = None,
    ) -> None:
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._credentials_in_body = credentials_in_body
        self._extra_token_params = dict(extra_token_params or {})

        self._access_token: str | None = None
        self._expires_at: dt.datetime | None = None

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        # Stage 1: ensure we have a token (cached or freshly minted), send the request.
        if self._token_expired():
            token_response = yield self._build_token_request()
            self._parse_token_response(token_response)
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        response = yield request
        if response.status_code != 401:
            return

        # Stage 2: token was rejected. Refresh once and retry. A second 401 (or
        # any non-200 token response) propagates as AuthenticationError.
        logger.info("OAuth2 access token rejected (HTTP 401); refreshing once")
        token_response = yield self._build_token_request()
        self._parse_token_response(token_response)
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        yield request

    def _token_expired(self) -> bool:
        if self._access_token is None or self._expires_at is None:
            return True
        return dt.datetime.now(dt.UTC) >= self._expires_at - _EXPIRY_SAFETY_MARGIN

    def _build_token_request(self) -> httpx.Request:
        data: dict[str, str] = {"grant_type": "client_credentials"}
        if self._scope:
            data["scope"] = self._scope
        data.update(self._extra_token_params)
        headers: dict[str, str] = {"Accept": "application/json"}

        if self._credentials_in_body:
            data["client_id"] = self._client_id
            data["client_secret"] = self._client_secret
        else:
            credentials = f"{self._client_id}:{self._client_secret}".encode()
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")

        return httpx.Request("POST", self._token_url, headers=headers, data=data)

    def _parse_token_response(self, response: httpx.Response) -> None:
        if response.status_code != 200:
            body_preview = response.text[:500] if response.text else ""
            raise AuthenticationError(
                f"OAuth2 token endpoint returned HTTP {response.status_code}",
                response.status_code,
                body_preview,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            body_preview = response.text[:500] if response.text else ""
            raise AuthenticationError(
                "OAuth2 token endpoint returned non-JSON response",
                response.status_code,
                body_preview,
            ) from exc

        token = payload.get("access_token")
        if not token:
            body_preview = response.text[:500] if response.text else ""
            raise AuthenticationError(
                "OAuth2 token endpoint response did not include access_token",
                response.status_code,
                body_preview,
            )

        expires_in_raw = payload.get("expires_in")
        try:
            expires_in_seconds = int(expires_in_raw) if expires_in_raw is not None else None
        except (TypeError, ValueError):
            expires_in_seconds = None

        lifetime = (
            dt.timedelta(seconds=expires_in_seconds)
            if expires_in_seconds and expires_in_seconds > 0
            else _FALLBACK_TOKEN_LIFETIME
        )

        self._access_token = token
        self._expires_at = dt.datetime.now(dt.UTC) + lifetime

    def invalidate_token(self) -> None:
        """Force the next request to fetch a fresh token.

        Useful in tests. Production code should never need this — the 401
        handler in :meth:`auth_flow` covers in-flight invalidations.
        """
        self._access_token = None
        self._expires_at = None


__all__ = ["OAuth2ClientCredentialsAuth"]
