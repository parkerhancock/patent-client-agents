"""Tests for the INPI session lifecycle (XSRF + login + refresh).

Covers the four-stage flow in :mod:`patent_client_agents.inpi_pi.session`:

1. Cold session: ``fetch_xsrf`` → ``login`` populates an
   :class:`InpiSession`.
2. ``refresh`` succeeds → new access token, refresh token preserved.
3. ``refresh`` fails → caller falls back to a fresh XSRF + login.
4. Cookies and the ``expires_at`` window are preserved across calls.

All transport is mocked via :class:`httpx.MockTransport` — no live
INPI traffic. INPI Data account credentials are not available in v1
per the spec §6 open item.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from law_tools_core.exceptions import AuthenticationError
from patent_client_agents.inpi_pi.session import (
    BOOTSTRAP_PATH,
    DEFAULT_TOKEN_TTL_SECONDS,
    LOGIN_PATH,
    REFRESH_PATH,
    XSRF_COOKIE_NAME,
    InpiSession,
    fetch_xsrf,
    login,
    refresh,
)

BASE_URL = "https://api-gateway.inpi.fr"


def _login_body(
    *,
    access: str = "test-access-token-AAA",
    refresh_tok: str = "test-refresh-token-BBB",
    expires_in: int | float | None = 1800,
) -> dict[str, Any]:
    body: dict[str, Any] = {"access_token": access, "refresh_token": refresh_tok}
    if expires_in is not None:
        body["expires_in"] = expires_in
    return body


def _set_cookie(name: str, value: str) -> str:
    """Render a single Set-Cookie header value with default Path attr."""
    return f"{name}={value}; Path=/"


# ---------------------------------------------------------------------------
# fetch_xsrf
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_xsrf_returns_cookie_value() -> None:
    """fetch_xsrf returns the XSRF-TOKEN cookie issued by the gateway."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == BOOTSTRAP_PATH
        return httpx.Response(
            200,
            headers=[("Set-Cookie", _set_cookie(XSRF_COOKIE_NAME, "xsrf-001"))],
            json={},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        token = await fetch_xsrf(client, base_url=BASE_URL)
    assert token == "xsrf-001"


@pytest.mark.asyncio
async def test_fetch_xsrf_raises_when_cookie_absent() -> None:
    """Missing XSRF-TOKEN cookie → AuthenticationError with status code."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError):
            await fetch_xsrf(client, base_url=BASE_URL)


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_populates_session_from_body() -> None:
    """Successful login captures bearer + refresh + xsrf + expires_at."""
    body = _login_body(expires_in=1800)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == LOGIN_PATH
        assert request.method == "POST"
        # XSRF header arrived as expected
        assert request.headers.get("X-XSRF-TOKEN") == "xsrf-001"
        # body carries credentials
        payload = json.loads(request.content.decode())
        assert payload == {"username": "u", "password": "p"}
        return httpx.Response(
            200,
            headers=[
                ("Set-Cookie", _set_cookie("access_token", body["access_token"])),
                ("Set-Cookie", _set_cookie("refresh_token", body["refresh_token"])),
                ("Set-Cookie", _set_cookie(XSRF_COOKIE_NAME, "xsrf-002")),
            ],
            json=body,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)

    assert isinstance(session, InpiSession)
    assert session.access_token == "test-access-token-AAA"
    assert session.refresh_token == "test-refresh-token-BBB"
    assert session.xsrf_token == "xsrf-002"  # gateway rotated XSRF
    assert session.expires_at is not None
    # expires_at lies in (now, now + 1800s + tolerance)
    now = datetime.now(UTC)
    assert now < session.expires_at <= now + timedelta(seconds=1801)
    # cookie jar populated
    assert session.cookies["access_token"] == "test-access-token-AAA"


@pytest.mark.asyncio
async def test_login_falls_back_to_default_ttl_when_expires_in_missing() -> None:
    """No expires_in / exp → expires_at = now + DEFAULT_TOKEN_TTL_SECONDS."""
    body = _login_body(expires_in=None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[
                ("Set-Cookie", _set_cookie("access_token", body["access_token"])),
                ("Set-Cookie", _set_cookie("refresh_token", body["refresh_token"])),
            ],
            json=body,
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)

    now = datetime.now(UTC)
    assert session.expires_at is not None
    delta = session.expires_at - now
    assert DEFAULT_TOKEN_TTL_SECONDS - 5 <= delta.total_seconds() <= DEFAULT_TOKEN_TTL_SECONDS + 5


@pytest.mark.asyncio
async def test_login_accepts_jwt_exp_field() -> None:
    """JWT-style ``exp`` (epoch seconds) parsed as expires_at."""
    future = int((datetime.now(UTC) + timedelta(seconds=900)).timestamp())
    body = {"access_token": "x", "refresh_token": "y", "exp": future}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)

    assert session.expires_at is not None
    assert abs(session.expires_at.timestamp() - future) < 1.0


@pytest.mark.asyncio
async def test_login_raises_auth_error_on_401() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad creds")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError) as exc:
            await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)
        assert "Invalid INPI credentials" in str(exc.value)


@pytest.mark.asyncio
async def test_login_raises_when_no_access_token_in_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        # 200 OK but body and cookies carry no access_token
        return httpx.Response(200, json={"refresh_token": "x"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError) as exc:
            await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)
        assert "did not return an access_token" in str(exc.value)


@pytest.mark.asyncio
async def test_login_raises_on_5xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError) as exc:
            await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)
        assert "HTTP 500" in str(exc.value)


@pytest.mark.asyncio
async def test_login_tolerates_non_json_body() -> None:
    """Empty body + access_token cookie still works (cookie-only flavor)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[
                ("Set-Cookie", _set_cookie("access_token", "cookie-only-access")),
                ("Set-Cookie", _set_cookie("refresh_token", "cookie-only-refresh")),
            ],
            content=b"",  # not valid JSON
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await login(client, "u", "p", "xsrf-001", base_url=BASE_URL)

    assert session.access_token == "cookie-only-access"
    assert session.refresh_token == "cookie-only-refresh"


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_rotates_access_keeps_refresh_token() -> None:
    """Refresh returns new access_token; refresh_token preserved if not rotated."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == REFRESH_PATH
        assert request.method == "POST"
        # XSRF header + refresh cookie arrived
        assert request.headers.get("X-XSRF-TOKEN") == "xsrf-001"
        return httpx.Response(
            200,
            headers=[
                ("Set-Cookie", _set_cookie("access_token", "rotated-AAA")),
            ],
            json={"access_token": "rotated-AAA", "expires_in": 1800},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await refresh(client, "test-refresh-token-BBB", "xsrf-001", base_url=BASE_URL)

    assert session.access_token == "rotated-AAA"
    # Server did NOT rotate refresh; we re-use the input
    assert session.refresh_token == "test-refresh-token-BBB"


@pytest.mark.asyncio
async def test_refresh_rotates_refresh_token_when_server_does() -> None:
    """If server rotates refresh_token, that gets captured too."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[
                ("Set-Cookie", _set_cookie("access_token", "rotated-AAA")),
                ("Set-Cookie", _set_cookie("refresh_token", "rotated-BBB")),
            ],
            json={"access_token": "rotated-AAA"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await refresh(client, "old-refresh", "xsrf-001", base_url=BASE_URL)

    assert session.refresh_token == "rotated-BBB"


@pytest.mark.asyncio
async def test_refresh_raises_on_401() -> None:
    """Rejected refresh token → AuthenticationError so caller can re-login."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="refresh rejected")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError) as exc:
            await refresh(client, "bad-refresh", "xsrf-001", base_url=BASE_URL)
        assert "refresh token rejected" in str(exc.value)


@pytest.mark.asyncio
async def test_refresh_raises_on_5xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="busy")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError) as exc:
            await refresh(client, "x", "y", base_url=BASE_URL)
        assert "HTTP 503" in str(exc.value)


@pytest.mark.asyncio
async def test_refresh_raises_when_no_access_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AuthenticationError) as exc:
            await refresh(client, "x", "y", base_url=BASE_URL)
        assert "did not return a new access_token" in str(exc.value)


@pytest.mark.asyncio
async def test_refresh_tolerates_non_json_body() -> None:
    """access_token via cookie only (no JSON body)."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers=[("Set-Cookie", _set_cookie("access_token", "cookie-AAA"))],
            content=b"",
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        session = await refresh(client, "old-refresh", "xsrf", base_url=BASE_URL)

    assert session.access_token == "cookie-AAA"


# ---------------------------------------------------------------------------
# InpiSession.is_expired
# ---------------------------------------------------------------------------


class TestInpiSessionIsExpired:
    def test_empty_session_is_expired(self) -> None:
        assert InpiSession().is_expired() is True

    def test_no_expires_at_is_expired(self) -> None:
        s = InpiSession(access_token="x", expires_at=None)
        assert s.is_expired() is True

    def test_future_expiry_is_not_expired(self) -> None:
        future = datetime.now(UTC) + timedelta(seconds=3600)
        s = InpiSession(access_token="x", expires_at=future)
        assert s.is_expired() is False

    def test_within_buffer_is_expired(self) -> None:
        """expires_at within buffer_seconds → treated as expired."""
        soon = datetime.now(UTC) + timedelta(seconds=30)
        s = InpiSession(access_token="x", expires_at=soon)
        # default buffer is 60s
        assert s.is_expired() is True

    def test_past_expiry_is_expired(self) -> None:
        past = datetime.now(UTC) - timedelta(seconds=60)
        s = InpiSession(access_token="x", expires_at=past)
        assert s.is_expired() is True
