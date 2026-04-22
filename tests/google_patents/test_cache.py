"""Tests for Google Patents cache module."""

from __future__ import annotations

import tempfile
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest

from ip_tools.google_patents.cache import (
    CACHE_TTL_SECONDS,
    CachingAsyncClient,
    PatentCache,
    build_cached_http_client,
)


class TestCacheTtlSeconds:
    """Tests for CACHE_TTL_SECONDS constant."""

    def test_is_30_days(self) -> None:
        expected = 30 * 24 * 60 * 60
        assert CACHE_TTL_SECONDS == expected

    def test_is_positive(self) -> None:
        assert CACHE_TTL_SECONDS > 0


class TestPatentCache:
    """Tests for PatentCache class."""

    @pytest.fixture
    def temp_cache(self) -> Generator[PatentCache, None, None]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_cache.db"
            cache = PatentCache(db_path, ttl_seconds=3600)
            yield cache
            cache.close()

    def test_init(self, temp_cache: PatentCache) -> None:
        assert temp_cache.ttl_seconds == 3600
        assert temp_cache._conn is None

    def test_creates_db_on_first_access(self, temp_cache: PatentCache) -> None:
        assert temp_cache._conn is None
        temp_cache._get_conn()
        assert temp_cache._conn is not None

    def test_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            nested_path = Path(tmp_dir) / "nested" / "dir" / "cache.db"
            cache = PatentCache(nested_path)
            cache._get_conn()
            assert nested_path.parent.exists()
            cache.close()

    def test_set_and_get(self, temp_cache: PatentCache) -> None:
        url = "https://patents.google.com/patent/US10123456"
        html = "<html>Test content</html>"
        temp_cache.set(url, html, 200)
        result = temp_cache.get(url)
        assert result is not None
        assert result[0] == html
        assert result[1] == 200

    def test_get_returns_none_for_missing(self, temp_cache: PatentCache) -> None:
        result = temp_cache.get("https://example.com/not-cached")
        assert result is None

    def test_set_overwrites_existing(self, temp_cache: PatentCache) -> None:
        url = "https://example.com/test"
        temp_cache.set(url, "old content", 200)
        temp_cache.set(url, "new content", 200)
        result = temp_cache.get(url)
        assert result is not None
        assert result[0] == "new content"

    def test_expired_entries_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "expired_cache.db"
            cache = PatentCache(db_path, ttl_seconds=1)
            url = "https://example.com/expires"
            cache.set(url, "content", 200)
            time.sleep(1.1)
            result = cache.get(url)
            assert result is None
            cache.close()

    def test_url_hash_consistent(self, temp_cache: PatentCache) -> None:
        url = "https://patents.google.com/patent/US12345678"
        hash1 = temp_cache._url_hash(url)
        hash2 = temp_cache._url_hash(url)
        assert hash1 == hash2

    def test_url_hash_different_for_different_urls(self, temp_cache: PatentCache) -> None:
        hash1 = temp_cache._url_hash("https://example.com/a")
        hash2 = temp_cache._url_hash("https://example.com/b")
        assert hash1 != hash2

    def test_close(self, temp_cache: PatentCache) -> None:
        temp_cache._get_conn()
        assert temp_cache._conn is not None
        temp_cache.close()
        assert temp_cache._conn is None

    def test_close_when_not_connected(self, temp_cache: PatentCache) -> None:
        assert temp_cache._conn is None
        temp_cache.close()
        assert temp_cache._conn is None


class TestCachingAsyncClient:
    """Tests for CachingAsyncClient class."""

    @pytest.fixture
    def temp_cache(self) -> Generator[PatentCache, None, None]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "client_cache.db"
            cache = PatentCache(db_path)
            yield cache
            cache.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_cache: PatentCache) -> None:
        client = CachingAsyncClient(cache=temp_cache)
        async with client:
            assert client._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_without_context_raises(self, temp_cache: PatentCache) -> None:
        client = CachingAsyncClient(cache=temp_cache)
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.get("https://example.com")

    @pytest.mark.asyncio
    async def test_get_caches_successful_response(self, temp_cache: PatentCache) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>Mocked response</html>")

        mock_transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=temp_cache, transport=mock_transport)

        async with client:
            url = "https://patents.google.com/patent/US10123456"
            response = await client.get(url)
            assert response.status_code == 200
            cached = temp_cache.get(url)
            assert cached is not None
            assert cached[0] == "<html>Mocked response</html>"

    @pytest.mark.asyncio
    async def test_get_returns_cached_response(self, temp_cache: PatentCache) -> None:
        url = "https://patents.google.com/patent/US10123456"
        temp_cache.set(url, "<html>Cached content</html>", 200)

        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, text="<html>Fresh content</html>")

        mock_transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=temp_cache, transport=mock_transport)

        async with client:
            response = await client.get(url)
            assert response.status_code == 200
            assert response.text == "<html>Cached content</html>"
            assert call_count == 0

    @pytest.mark.asyncio
    async def test_get_without_cache(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="Response without caching")

        mock_transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=None, transport=mock_transport)

        async with client:
            response = await client.get("https://example.com")
            assert response.status_code == 200
            assert response.text == "Response without caching"

    @pytest.mark.asyncio
    async def test_get_does_not_cache_non_200(self, temp_cache: PatentCache) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Not found")

        mock_transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=temp_cache, transport=mock_transport)

        async with client:
            url = "https://example.com/not-found"
            response = await client.get(url)
            assert response.status_code == 404
            cached = temp_cache.get(url)
            assert cached is None

    @pytest.mark.asyncio
    async def test_custom_headers(self, temp_cache: PatentCache) -> None:
        captured_headers = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(request.headers)
            return httpx.Response(200, text="OK")

        mock_transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(
            cache=temp_cache,
            headers={"X-Custom-Header": "test-value"},
            transport=mock_transport,
        )

        async with client:
            await client.get("https://example.com")
            assert captured_headers.get("x-custom-header") == "test-value"


class TestBuildCachedHttpClient:
    """Tests for build_cached_http_client function."""

    def test_returns_caching_async_client(self) -> None:
        client = build_cached_http_client(use_cache=False, cache_name="test")
        assert isinstance(client, CachingAsyncClient)

    def test_with_cache_enabled(self) -> None:
        client = build_cached_http_client(use_cache=True, cache_name="test_cache")
        assert client._cache is not None
        if client._cache:
            client._cache.close()

    def test_with_cache_disabled(self) -> None:
        client = build_cached_http_client(use_cache=False, cache_name="test")
        assert client._cache is None

    def test_includes_default_headers(self) -> None:
        client = build_cached_http_client(use_cache=False, cache_name="test")
        assert "User-Agent" in client._headers
        assert "Accept-Language" in client._headers

    def test_custom_headers_merged(self) -> None:
        custom_headers = {"X-Custom": "value"}
        client = build_cached_http_client(
            use_cache=False, cache_name="test", headers=custom_headers
        )
        assert client._headers.get("X-Custom") == "value"
        assert "User-Agent" in client._headers

    def test_custom_headers_override_defaults(self) -> None:
        custom_headers = {"Accept-Language": "fr-FR"}
        client = build_cached_http_client(
            use_cache=False, cache_name="test", headers=custom_headers
        )
        assert client._headers.get("Accept-Language") == "fr-FR"
