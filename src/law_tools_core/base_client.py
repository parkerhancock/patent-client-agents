"""Base async HTTP client with standardized patterns."""

from __future__ import annotations

import contextlib
import logging
from datetime import timedelta
from pathlib import Path
from typing import Any, Self

import httpx

from .cache import CacheManager, CacheStats, build_cached_http_client, get_default_cache_dir
from .exceptions import (
    ApiError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from .resilience import default_retryer

logger = logging.getLogger(__name__)


class BaseAsyncClient:
    """Base class for async API clients with caching and retry support.

    Subclasses should override:
        - DEFAULT_BASE_URL: The default API base URL
        - CACHE_NAME: Name for the cache database file

    Example:
        class MyApiClient(BaseAsyncClient):
            DEFAULT_BASE_URL = "https://api.example.com"
            CACHE_NAME = "my_api"

            async def get_resource(self, id: str) -> dict:
                return await self._request_json("GET", f"/resources/{id}")

    Cache Management:
        async with MyApiClient() as client:
            # Make requests...
            result = await client.get_resource("123")

            # Get cache statistics
            stats = await client.cache_stats()
            print(f"Hit rate: {stats.hit_rate:.1f}%")
            print(f"Cache size: {stats.size_mb:.2f} MB")

            # Clear all cached data
            cleared = await client.cache_clear()
            print(f"Cleared {cleared} entries")

            # Clear entries older than 1 hour
            cleared = await client.cache_clear_expired(max_age=timedelta(hours=1))

            # Invalidate specific URLs by pattern
            cleared = await client.cache_invalidate(r"/resources/123")
    """

    DEFAULT_BASE_URL: str = ""
    CACHE_NAME: str = "default"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(
        self,
        *,
        base_url: str | None = None,
        cache_path: Path | None = None,
        client: httpx.AsyncClient | None = None,
        use_cache: bool = True,
        ttl_seconds: int | None = None,
        max_retries: int = 4,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        auth: httpx.Auth | None = None,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Override the default base URL.
            cache_path: Custom path for the cache directory.
            client: Existing httpx.AsyncClient to use (for testing).
            use_cache: Whether to enable HTTP caching.
            ttl_seconds: Default TTL for cache entries. None uses HTTP headers.
            max_retries: Maximum retry attempts for transient failures.
            headers: Additional headers to include in requests.
            timeout: Request timeout in seconds (defaults to ``DEFAULT_TIMEOUT``).
            auth: httpx Auth handler (e.g. for OAuth2 token refresh).
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._owns_client = client is None
        self._max_retries = max_retries
        self._timeout = timeout or self.DEFAULT_TIMEOUT
        self._cache_manager: CacheManager | None = None

        if client is None:
            cache_dir = cache_path or get_default_cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._client, self._cache_manager = build_cached_http_client(
                use_cache=use_cache,
                cache_name=self.CACHE_NAME,
                cache_dir=cache_dir,
                ttl_seconds=ttl_seconds,
                headers=headers or {},
                follow_redirects=True,
                timeout=self._timeout,
                auth=auth,
            )
        else:
            self._client = client
            if headers:
                for key, value in headers.items():
                    self._client.headers.setdefault(key, value)

    @property
    def cache_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._cache_manager is not None

    async def cache_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats with hits, misses, entry count, and size.

        Raises:
            RuntimeError: If caching is disabled.
        """
        if self._cache_manager is None:
            raise RuntimeError("Caching is disabled for this client")
        return await self._cache_manager.get_stats()

    async def cache_clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.

        Raises:
            RuntimeError: If caching is disabled.
        """
        if self._cache_manager is None:
            raise RuntimeError("Caching is disabled for this client")
        return await self._cache_manager.clear_all()

    async def cache_clear_expired(self, max_age: timedelta | None = None) -> int:
        """Clear expired cache entries.

        Args:
            max_age: Maximum age for entries. Defaults to TTL or 24 hours.

        Returns:
            Number of entries cleared.

        Raises:
            RuntimeError: If caching is disabled.
        """
        if self._cache_manager is None:
            raise RuntimeError("Caching is disabled for this client")
        return await self._cache_manager.clear_expired(max_age)

    async def cache_invalidate(self, url_pattern: str) -> int:
        """Invalidate cache entries matching a URL pattern.

        Args:
            url_pattern: Regex pattern to match against cached URLs.

        Returns:
            Number of entries invalidated.

        Raises:
            RuntimeError: If caching is disabled.
        """
        if self._cache_manager is None:
            raise RuntimeError("Caching is disabled for this client")
        return await self._cache_manager.invalidate_pattern(url_pattern)

    async def close(self) -> None:
        """Close the underlying HTTP client if we own it."""
        if self._owns_client:
            await self._client.aclose()
            if self._cache_manager is not None:
                await self._cache_manager.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _build_url(self, path: str) -> str:
        """Build a full URL from a path."""
        return f"{self.base_url}{path}"

    def _raise_for_status(self, response: httpx.Response, context: str = "") -> None:
        """Convert HTTP errors to typed exceptions.

        Args:
            response: The HTTP response to check.
            context: Optional context string for error messages.

        Raises:
            NotFoundError: For 404 responses.
            RateLimitError: For 429 responses.
            AuthenticationError: For 401/403 responses.
            ServerError: For 5xx responses.
            ApiError: For other non-success responses.
        """
        if response.is_success:
            return

        status = response.status_code
        body = response.text[:500] if response.text else ""
        msg = f"{context}: HTTP {status}" if context else f"HTTP {status}"

        # Log full response details to file for debugging
        logger.error(
            "%s %s -> %s\nResponse body: %s",
            response.request.method,
            response.request.url,
            status,
            body,
        )

        if status == 404:
            raise NotFoundError(msg, status, body)
        if status == 429:
            retry_after: float | None = None
            raw = response.headers.get("Retry-After")
            if raw is not None:
                with contextlib.suppress(ValueError):
                    retry_after = float(raw)
            raise RateLimitError(msg, status, body, retry_after=retry_after)
        if status in (401, 403):
            raise AuthenticationError(msg, status, body)
        if 500 <= status < 600:
            raise ServerError(msg, status, body)
        raise ApiError(msg, status, body)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        context: str = "",
        timeout: float | None = None,
    ) -> httpx.Response:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: URL path (will be appended to base_url).
            params: Query parameters.
            json: JSON body for POST/PUT requests.
            data: Form-encoded body.
            content: Raw bytes body.
            headers: Per-request header overrides (merged on top of client headers).
            context: Context string for error messages.
            timeout: Optional per-request timeout in seconds.

        Returns:
            The HTTP response.

        Raises:
            ApiError: On non-retryable HTTP errors.
        """
        url = self._build_url(path)
        request_kwargs: dict[str, Any] = {}
        if params:
            request_kwargs["params"] = params
        if json is not None:
            request_kwargs["json"] = json
        if data is not None:
            request_kwargs["data"] = data
        if content is not None:
            request_kwargs["content"] = content
        if headers:
            request_kwargs["headers"] = headers
        if timeout:
            request_kwargs["timeout"] = timeout

        async for attempt in default_retryer(max_attempts=self._max_retries):
            with attempt:
                response = await self._client.request(method, url, **request_kwargs)
                self._raise_for_status(response, context)
                return response

        # Should not reach here due to reraise=True in retryer
        raise RuntimeError("Unexpected retry exhaustion")

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        context: str = "",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Make an HTTP request and return JSON response.

        Args:
            method: HTTP method.
            path: URL path.
            params: Query parameters.
            json: JSON body.
            data: Form-encoded body.
            content: Raw bytes body.
            headers: Per-request header overrides.
            context: Context string for error messages.
            timeout: Optional per-request timeout.

        Returns:
            Parsed JSON response as a dictionary.
        """
        response = await self._request(
            method,
            path,
            params=params,
            json=json,
            data=data,
            content=content,
            headers=headers,
            context=context,
            timeout=timeout,
        )
        return response.json()


__all__ = ["BaseAsyncClient"]
