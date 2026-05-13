"""Tests for law_tools_core.oauth2.OAuth2ClientCredentialsAuth."""

from __future__ import annotations

import base64
import datetime as dt

import httpx
import pytest

from law_tools_core.exceptions import AuthenticationError
from law_tools_core.oauth2 import OAuth2ClientCredentialsAuth

TOKEN_URL = "https://example.test/oauth2/token"
API_URL = "https://example.test/api/resource"


class _Recorder:
    """Captures every request the MockTransport sees, in order.

    Each handler factory below builds a fresh recorder. Tests assert on
    ``recorder.requests`` to confirm header injection, token refresh
    behavior, and call ordering.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []


def _make_token_response(access_token: str = "tok-1", expires_in: int = 3600) -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": access_token, "token_type": "Bearer", "expires_in": expires_in},
    )


def _make_transport(handler):
    return httpx.MockTransport(handler)


def _async_client(auth: OAuth2ClientCredentialsAuth, handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_make_transport(handler), auth=auth)


class TestTokenAcquisition:
    @pytest.mark.asyncio
    async def test_first_request_fetches_token_and_injects_header(self) -> None:
        rec = _Recorder()

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                return _make_token_response("alpha", expires_in=3600)
            assert request.headers["Authorization"] == "Bearer alpha"
            return httpx.Response(200, json={"ok": True})

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            r = await client.get(API_URL)
        assert r.status_code == 200

        # Token request first, then the API call.
        assert len(rec.requests) == 2
        token_req, api_req = rec.requests
        assert str(token_req.url) == TOKEN_URL
        assert token_req.method == "POST"
        # Default: credentials in HTTP Basic header.
        expected_basic = "Basic " + base64.b64encode(b"cid:csec").decode("ascii")
        assert token_req.headers["Authorization"] == expected_basic
        body = token_req.content.decode("utf-8") if token_req.content else ""
        assert "grant_type=client_credentials" in body
        # API request got the bearer.
        assert api_req.headers["Authorization"] == "Bearer alpha"

    @pytest.mark.asyncio
    async def test_credentials_in_body_skips_basic_auth(self) -> None:
        rec = _Recorder()

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                return _make_token_response()
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL,
            client_id="cid",
            client_secret="csec",
            credentials_in_body=True,
        )
        async with _async_client(auth, handler) as client:
            await client.get(API_URL)

        token_req = rec.requests[0]
        assert "Authorization" not in token_req.headers
        body = token_req.content.decode("utf-8")
        assert "client_id=cid" in body
        assert "client_secret=csec" in body

    @pytest.mark.asyncio
    async def test_scope_and_extra_params_added_to_token_request(self) -> None:
        rec = _Recorder()

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                return _make_token_response()
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL,
            client_id="cid",
            client_secret="csec",
            scope="read:patents",
            extra_token_params={"audience": "ipa-api"},
        )
        async with _async_client(auth, handler) as client:
            await client.get(API_URL)

        body = rec.requests[0].content.decode("utf-8")
        assert "scope=read%3Apatents" in body
        assert "audience=ipa-api" in body


class TestTokenCaching:
    @pytest.mark.asyncio
    async def test_second_request_reuses_cached_token(self) -> None:
        rec = _Recorder()

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                return _make_token_response("cached", expires_in=3600)
            return httpx.Response(200, json={"ok": True})

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            await client.get(API_URL)
            await client.get(API_URL)

        # Only one token fetch; two API calls.
        token_requests = [r for r in rec.requests if str(r.url) == TOKEN_URL]
        api_requests = [r for r in rec.requests if str(r.url) == API_URL]
        assert len(token_requests) == 1
        assert len(api_requests) == 2
        # Both API requests got the same bearer.
        assert all(r.headers["Authorization"] == "Bearer cached" for r in api_requests)

    @pytest.mark.asyncio
    async def test_expired_token_triggers_refresh(self) -> None:
        rec = _Recorder()
        token_counter = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                token_counter["n"] += 1
                return _make_token_response(f"tok-{token_counter['n']}", expires_in=3600)
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            await client.get(API_URL)
            # Force expiry — pretend the token expired in the past.
            auth._expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
            await client.get(API_URL)

        token_requests = [r for r in rec.requests if str(r.url) == TOKEN_URL]
        api_requests = [r for r in rec.requests if str(r.url) == API_URL]
        assert len(token_requests) == 2
        assert api_requests[0].headers["Authorization"] == "Bearer tok-1"
        assert api_requests[1].headers["Authorization"] == "Bearer tok-2"

    @pytest.mark.asyncio
    async def test_invalidate_token_forces_refresh(self) -> None:
        rec = _Recorder()
        token_counter = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                token_counter["n"] += 1
                return _make_token_response(f"tok-{token_counter['n']}")
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            await client.get(API_URL)
            auth.invalidate_token()
            await client.get(API_URL)

        assert token_counter["n"] == 2


class TestRefreshOn401:
    @pytest.mark.asyncio
    async def test_401_triggers_one_refresh_and_retry(self) -> None:
        rec = _Recorder()
        token_counter = {"n": 0}
        api_call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            rec.requests.append(request)
            if str(request.url) == TOKEN_URL:
                token_counter["n"] += 1
                return _make_token_response(f"tok-{token_counter['n']}", expires_in=3600)
            api_call_count["n"] += 1
            # First API call rejects token despite it being fresh; second accepts.
            if api_call_count["n"] == 1:
                return httpx.Response(401)
            return httpx.Response(200, json={"ok": True})

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            r = await client.get(API_URL)
        assert r.status_code == 200
        assert token_counter["n"] == 2
        assert api_call_count["n"] == 2


class TestTokenEndpointErrors:
    @pytest.mark.asyncio
    async def test_non_200_token_response_raises_authentication_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(403, text="forbidden")
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            with pytest.raises(AuthenticationError) as exc_info:
                await client.get(API_URL)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_non_json_token_response_raises_authentication_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(200, text="<html>nope</html>")
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            with pytest.raises(AuthenticationError):
                await client.get(API_URL)

    @pytest.mark.asyncio
    async def test_missing_access_token_field_raises_authentication_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(200, json={"expires_in": 3600})
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        async with _async_client(auth, handler) as client:
            with pytest.raises(AuthenticationError):
                await client.get(API_URL)

    @pytest.mark.asyncio
    async def test_missing_expires_in_falls_back_to_one_hour(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == TOKEN_URL:
                return httpx.Response(200, json={"access_token": "tok"})
            return httpx.Response(200)

        auth = OAuth2ClientCredentialsAuth(
            token_url=TOKEN_URL, client_id="cid", client_secret="csec"
        )
        before = dt.datetime.now(dt.UTC)
        async with _async_client(auth, handler) as client:
            await client.get(API_URL)
        after = dt.datetime.now(dt.UTC)
        assert auth._expires_at is not None
        elapsed_max = (after - before).total_seconds() + 5
        lifetime = (auth._expires_at - before).total_seconds()
        # ~3600s, generous bounds to absorb test scheduling jitter.
        assert 3600 - 5 <= lifetime <= 3600 + elapsed_max
