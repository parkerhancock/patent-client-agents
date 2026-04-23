"""Core module tests for patent_client_agents."""

from __future__ import annotations

import json

import httpx
import pytest

from law_tools_core.base_client import BaseAsyncClient
from law_tools_core.exceptions import (
    ApiError,
    AuthenticationError,
    LawToolsCoreError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from law_tools_core.resilience import is_retryable_error, with_retry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_transport(status_code: int, body: str = "", headers: dict | None = None):
    """Create an httpx.MockTransport returning a fixed response."""

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        return httpx.Response(status_code, text=body, headers=headers or {})

    return httpx.MockTransport(handler)


def sequenced_transport(responses: list[tuple[int, str]]):
    """Transport that returns different responses on successive calls."""
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
        idx = min(call_count["n"], len(responses) - 1)
        call_count["n"] += 1
        status, body = responses[idx]
        return httpx.Response(status, text=body)

    return httpx.MockTransport(handler)


def make_client(transport: httpx.MockTransport, **kwargs) -> BaseAsyncClient:
    """Build a BaseAsyncClient backed by a mock transport."""
    http = httpx.AsyncClient(transport=transport)
    return BaseAsyncClient(
        base_url="https://api.test",
        client=http,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# LawToolsCoreError
# ---------------------------------------------------------------------------


class TestLawToolsCoreError:
    """Tests for LawToolsCoreError exception."""

    def test_can_raise_ip_tools_error(self) -> None:
        with pytest.raises(LawToolsCoreError):
            raise LawToolsCoreError("test error")

    def test_error_message_preserved(self) -> None:
        try:
            raise LawToolsCoreError("custom message")
        except LawToolsCoreError as e:
            assert str(e) == "custom message"

    def test_api_error_appends_log_hint(self) -> None:
        try:
            raise ApiError("boom", status_code=500)
        except ApiError as e:
            rendered = str(e)
            assert "boom" in rendered
            assert "HTTP 500" in rendered
            assert "patent_client_agents.log" in rendered


# ---------------------------------------------------------------------------
# BaseAsyncClient — instantiation
# ---------------------------------------------------------------------------


class TestBaseAsyncClientInit:
    """Tests for BaseAsyncClient construction."""

    def test_can_instantiate(self) -> None:
        client = BaseAsyncClient(base_url="https://example.com")
        assert client.base_url == "https://example.com"

    def test_default_values(self) -> None:
        client = BaseAsyncClient()
        assert client.base_url == ""
        assert client._max_retries == 4
        assert client._owns_client is True

    def test_base_url_trailing_slash_stripped(self) -> None:
        client = BaseAsyncClient(base_url="https://example.com/")
        assert client.base_url == "https://example.com"

    def test_injected_client_not_owned(self) -> None:
        http = httpx.AsyncClient(transport=mock_transport(200))
        client = BaseAsyncClient(base_url="https://x.com", client=http)
        assert client._owns_client is False

    def test_cache_disabled_when_client_injected(self) -> None:
        http = httpx.AsyncClient(transport=mock_transport(200))
        client = BaseAsyncClient(client=http)
        assert client.cache_enabled is False

    def test_injected_client_with_headers(self) -> None:
        """Lines 104-106: headers merged into injected client."""
        http = httpx.AsyncClient(transport=mock_transport(200))
        client = BaseAsyncClient(client=http, headers={"X-Custom": "value1"})
        assert client._client.headers.get("X-Custom") == "value1"

    def test_injected_client_headers_dont_overwrite(self) -> None:
        """setdefault should not overwrite existing headers."""
        http = httpx.AsyncClient(
            transport=mock_transport(200),
            headers={"X-Custom": "original"},
        )
        client = BaseAsyncClient(client=http, headers={"X-Custom": "new"})
        # setdefault keeps the original
        assert client._client.headers.get("X-Custom") == "original"


# ---------------------------------------------------------------------------
# _raise_for_status
# ---------------------------------------------------------------------------


class TestRaiseForStatus:
    """Tests for _raise_for_status status-code mapping."""

    def _response(self, status: int, body: str = "err") -> httpx.Response:
        request = httpx.Request("GET", "https://api.test/foo")
        return httpx.Response(status, text=body, request=request)

    def test_success_does_not_raise(self) -> None:
        client = make_client(mock_transport(200))
        client._raise_for_status(self._response(200))

    def test_404_raises_not_found(self) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(NotFoundError) as exc_info:
            client._raise_for_status(self._response(404))
        assert exc_info.value.status_code == 404
        assert "patent_client_agents.log" in str(exc_info.value)

    def test_429_raises_rate_limit(self) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(RateLimitError) as exc_info:
            client._raise_for_status(self._response(429))
        assert exc_info.value.status_code == 429

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_errors(self, status: int) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(AuthenticationError) as exc_info:
            client._raise_for_status(self._response(status))
        assert exc_info.value.status_code == status

    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_server_errors(self, status: int) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(ServerError) as exc_info:
            client._raise_for_status(self._response(status))
        assert exc_info.value.status_code == status

    def test_other_error_raises_api_error(self) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(ApiError) as exc_info:
            client._raise_for_status(self._response(418, "teapot"))
        assert exc_info.value.status_code == 418
        assert exc_info.value.response_body == "teapot"

    def test_context_in_message(self) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(ApiError, match="fetching widget"):
            client._raise_for_status(self._response(400), context="fetching widget")

    def test_response_body_captured(self) -> None:
        client = make_client(mock_transport(200))
        with pytest.raises(ApiError) as exc_info:
            client._raise_for_status(self._response(400, "bad request body"))
        assert exc_info.value.response_body == "bad request body"


# ---------------------------------------------------------------------------
# _request
# ---------------------------------------------------------------------------


class TestRequest:
    """Tests for _request with mock transport."""

    @pytest.mark.asyncio
    async def test_successful_get(self) -> None:
        client = make_client(mock_transport(200, "ok"))
        resp = await client._request("GET", "/items")
        assert resp.status_code == 200
        assert resp.text == "ok"

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self) -> None:
        """404 is not retryable and should raise on first attempt."""
        client = make_client(mock_transport(404, "gone"))
        with pytest.raises(NotFoundError):
            await client._request("GET", "/missing")

    @pytest.mark.asyncio
    async def test_server_error_not_retried(self) -> None:
        """ServerError (from _raise_for_status) is NOT retryable because
        it inherits from ApiError, not httpx.HTTPStatusError. The retry
        predicate only matches httpx.HTTPStatusError, TransportError, and
        RateLimitError."""
        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            call_count["n"] += 1
            return httpx.Response(500, text="fail")

        transport = httpx.MockTransport(handler)
        client = make_client(transport, max_retries=3)
        with pytest.raises(ServerError):
            await client._request("GET", "/flaky")
        # Should fail on first attempt — ServerError is not retryable
        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_retry_on_429_then_success(self) -> None:
        """RateLimitError IS retryable because is_retryable_error checks
        isinstance(exc, RateLimitError)."""
        transport = sequenced_transport([(429, "slow down"), (200, "ok")])
        client = make_client(transport, max_retries=3)
        resp = await client._request("GET", "/rate-limited")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_retry_exhaustion_on_rate_limit(self) -> None:
        """All attempts fail with RateLimitError -> raises after exhaustion."""
        transport = sequenced_transport([(429, "slow"), (429, "slow"), (429, "slow")])
        client = make_client(transport, max_retries=2)
        with pytest.raises(RateLimitError):
            await client._request("GET", "/always-limited")

    @pytest.mark.asyncio
    async def test_context_passed_to_error(self) -> None:
        client = make_client(mock_transport(400, "bad"))
        with pytest.raises(ApiError, match="loading patent"):
            await client._request("GET", "/x", context="loading patent")

    @pytest.mark.asyncio
    async def test_timeout_forwarded(self) -> None:
        """Line 261: timeout kwarg passed through to httpx."""

        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            # httpx doesn't expose timeout on the request object directly,
            # but the kwarg is forwarded — just verify no error
            return httpx.Response(200, text="ok")

        transport = httpx.MockTransport(handler)
        client = make_client(transport)
        resp = await client._request("GET", "/items", timeout=5.0)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_json_body_forwarded(self) -> None:
        """Line 258-259: json kwarg passed through."""
        seen_bodies: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_bodies.append(request.content)
            return httpx.Response(200, text="ok")

        transport = httpx.MockTransport(handler)
        client = make_client(transport)
        await client._request("POST", "/items", json={"key": "val"})
        assert b"key" in seen_bodies[0]

    @pytest.mark.asyncio
    async def test_params_forwarded(self) -> None:
        """Query params should appear in the request."""
        seen_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_urls.append(str(request.url))
            return httpx.Response(200, text="ok")

        transport = httpx.MockTransport(handler)
        client = make_client(transport)
        await client._request("GET", "/search", params={"q": "test"})
        assert "q=test" in seen_urls[0]


# ---------------------------------------------------------------------------
# _request_json
# ---------------------------------------------------------------------------


class TestRequestJson:
    """Tests for _request_json JSON parsing."""

    @pytest.mark.asyncio
    async def test_json_parsed(self) -> None:
        payload = {"results": [1, 2, 3]}
        transport = mock_transport(200, json.dumps(payload))
        client = make_client(transport)
        data = await client._request_json("GET", "/data")
        assert data == payload

    @pytest.mark.asyncio
    async def test_json_error_propagates(self) -> None:
        client = make_client(mock_transport(404, "not found"))
        with pytest.raises(NotFoundError):
            await client._request_json("GET", "/missing")


# ---------------------------------------------------------------------------
# Cache methods when disabled
# ---------------------------------------------------------------------------


class TestCacheMethodsDisabled:
    """Cache ops raise RuntimeError when caching is disabled."""

    def _client(self) -> BaseAsyncClient:
        http = httpx.AsyncClient(transport=mock_transport(200))
        return BaseAsyncClient(client=http)

    @pytest.mark.asyncio
    async def test_cache_stats_raises(self) -> None:
        with pytest.raises(RuntimeError, match="disabled"):
            await self._client().cache_stats()

    @pytest.mark.asyncio
    async def test_cache_clear_raises(self) -> None:
        with pytest.raises(RuntimeError, match="disabled"):
            await self._client().cache_clear()

    @pytest.mark.asyncio
    async def test_cache_clear_expired_raises(self) -> None:
        with pytest.raises(RuntimeError, match="disabled"):
            await self._client().cache_clear_expired()

    @pytest.mark.asyncio
    async def test_cache_invalidate_raises(self) -> None:
        with pytest.raises(RuntimeError, match="disabled"):
            await self._client().cache_invalidate(".*")


# ---------------------------------------------------------------------------
# Cache methods when enabled (lines 124, 137, 153, 169)
# ---------------------------------------------------------------------------


class TestCacheMethodsEnabled:
    """Cache ops delegate to CacheManager when caching is enabled."""

    def _patch_storage_close(self, client: BaseAsyncClient) -> None:
        """Patch storage aclose for compatibility."""
        if client._cache_manager and client._cache_manager._storage:
            storage = client._cache_manager._storage
            if not hasattr(storage, "aclose"):
                storage.aclose = storage.close  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_cache_stats_returns_stats(self, tmp_path) -> None:
        """Line 124: cache_stats returns result from manager."""
        client = BaseAsyncClient(
            base_url="https://x.com",
            cache_path=tmp_path,
            use_cache=True,
        )
        stats = await client.cache_stats()
        assert stats.entry_count == 0
        self._patch_storage_close(client)
        await client.close()

    @pytest.mark.asyncio
    async def test_cache_clear_returns_count(self, tmp_path) -> None:
        """Line 137: cache_clear returns cleared count."""
        client = BaseAsyncClient(
            base_url="https://x.com",
            cache_path=tmp_path,
            use_cache=True,
        )
        cleared = await client.cache_clear()
        assert cleared == 0
        self._patch_storage_close(client)
        await client.close()

    @pytest.mark.asyncio
    async def test_cache_clear_expired_returns_count(self, tmp_path) -> None:
        """Line 153: cache_clear_expired returns cleared count."""
        from datetime import timedelta

        client = BaseAsyncClient(
            base_url="https://x.com",
            cache_path=tmp_path,
            use_cache=True,
        )
        cleared = await client.cache_clear_expired(max_age=timedelta(hours=1))
        assert cleared == 0
        self._patch_storage_close(client)
        await client.close()

    @pytest.mark.asyncio
    async def test_cache_invalidate_returns_count(self, tmp_path) -> None:
        """Line 169: cache_invalidate returns cleared count."""
        client = BaseAsyncClient(
            base_url="https://x.com",
            cache_path=tmp_path,
            use_cache=True,
        )
        cleared = await client.cache_invalidate(".*")
        assert cleared == 0
        self._patch_storage_close(client)
        await client.close()


# ---------------------------------------------------------------------------
# Lifecycle (__aenter__ / __aexit__ / close)
# ---------------------------------------------------------------------------


class TestClientLifecycle:
    """Tests for async context manager and close."""

    @pytest.mark.asyncio
    async def test_context_manager_returns_self(self) -> None:
        client = make_client(mock_transport(200))
        async with client as ctx:
            assert ctx is client

    @pytest.mark.asyncio
    async def test_close_on_owned_client(self) -> None:
        """close() should close the underlying httpx client when owned."""
        client = BaseAsyncClient(base_url="https://x.com", use_cache=False)
        assert client._owns_client is True
        await client.close()
        assert client._client.is_closed

    @pytest.mark.asyncio
    async def test_close_not_owned_leaves_client_open(self) -> None:
        """close() should NOT close an injected client."""
        http = httpx.AsyncClient(transport=mock_transport(200))
        client = BaseAsyncClient(client=http)
        await client.close()
        assert not http.is_closed
        await http.aclose()

    @pytest.mark.asyncio
    async def test_close_with_cache_manager(self, tmp_path) -> None:
        """Line 176: close() also closes cache_manager when present."""
        client = BaseAsyncClient(
            base_url="https://x.com",
            cache_path=tmp_path,
            use_cache=True,
        )
        assert client._cache_manager is not None
        # Patch storage aclose for compatibility
        if client._cache_manager._storage:
            storage = client._cache_manager._storage
            if not hasattr(storage, "aclose"):
                storage.aclose = storage.close  # type: ignore[attr-defined]
        await client.close()
        assert client._client.is_closed


# ---------------------------------------------------------------------------
# is_retryable_error
# ---------------------------------------------------------------------------


class TestIsRetryableError:
    """Tests for resilience.is_retryable_error."""

    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    def test_retryable_http_status(self, status: int) -> None:
        request = httpx.Request("GET", "https://api.test/x")
        response = httpx.Response(status, request=request)
        exc = httpx.HTTPStatusError("err", request=request, response=response)
        assert is_retryable_error(exc) is True

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 418])
    def test_non_retryable_http_status(self, status: int) -> None:
        request = httpx.Request("GET", "https://api.test/x")
        response = httpx.Response(status, request=request)
        exc = httpx.HTTPStatusError("err", request=request, response=response)
        assert is_retryable_error(exc) is False

    def test_transport_error_is_retryable(self) -> None:
        assert is_retryable_error(httpx.ConnectError("timeout")) is True

    def test_rate_limit_error_is_retryable(self) -> None:
        assert is_retryable_error(RateLimitError("slow", 429, "")) is True

    def test_generic_exception_not_retryable(self) -> None:
        assert is_retryable_error(ValueError("nope")) is False

    def test_api_error_not_retryable(self) -> None:
        assert is_retryable_error(ApiError("bad", 400, "")) is False


# ---------------------------------------------------------------------------
# with_retry decorator
# ---------------------------------------------------------------------------


class TestWithRetryDecorator:
    """Tests for resilience.with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self) -> None:
        call_count = {"n": 0}

        @with_retry(max_attempts=3, initial_wait=0.01, max_wait=0.02)
        async def ok():
            call_count["n"] += 1
            return "done"

        result = await ok()
        assert result == "done"
        assert call_count["n"] == 1

    @pytest.mark.asyncio
    async def test_transient_failure_then_success(self) -> None:
        call_count = {"n": 0}

        @with_retry(max_attempts=3, initial_wait=0.01, max_wait=0.02)
        async def flaky():
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise RateLimitError("slow", 429, "")
            return "ok"

        result = await flaky()
        assert result == "ok"
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_exhaustion_raises(self) -> None:
        @with_retry(max_attempts=2, initial_wait=0.01, max_wait=0.02)
        async def always_fail():
            raise RateLimitError("slow", 429, "")

        with pytest.raises(RateLimitError):
            await always_fail()

    @pytest.mark.asyncio
    async def test_non_retryable_not_retried(self) -> None:
        call_count = {"n": 0}

        @with_retry(max_attempts=3, initial_wait=0.01, max_wait=0.02)
        async def bad():
            call_count["n"] += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await bad()
        assert call_count["n"] == 1
