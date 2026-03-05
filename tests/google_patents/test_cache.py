"""Tests for Google Patents cache module."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
import pytest

from ip_tools.google_patents.cache import (
    CachingAsyncClient,
    PatentCache,
    build_cached_http_client,
)

# ---------------------------------------------------------------------------
# PatentCache tests
# ---------------------------------------------------------------------------


class TestPatentCache:
    """Unit tests for the SQLite-based PatentCache."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> PatentCache:
        db = tmp_path / "test_cache.db"
        return PatentCache(db, ttl_seconds=60)

    def test_init_attributes(self, tmp_path: Path) -> None:
        db = tmp_path / "cache.db"
        cache = PatentCache(db, ttl_seconds=120)
        assert cache.db_path == db
        assert cache.ttl_seconds == 120
        assert cache._conn is None

    def test_get_conn_creates_table(self, cache: PatentCache) -> None:
        conn = cache._get_conn()
        assert conn is not None
        # Verify table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='html_cache'"
        )
        assert cursor.fetchone() is not None

    def test_get_conn_is_idempotent(self, cache: PatentCache) -> None:
        conn1 = cache._get_conn()
        conn2 = cache._get_conn()
        assert conn1 is conn2

    def test_get_conn_creates_parent_dirs(self, tmp_path: Path) -> None:
        db = tmp_path / "nested" / "dir" / "cache.db"
        cache = PatentCache(db)
        conn = cache._get_conn()
        assert conn is not None
        assert db.parent.exists()
        cache.close()

    def test_url_hash_deterministic(self, cache: PatentCache) -> None:
        h1 = cache._url_hash("https://example.com")
        h2 = cache._url_hash("https://example.com")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_url_hash_different_for_different_urls(self, cache: PatentCache) -> None:
        h1 = cache._url_hash("https://a.com")
        h2 = cache._url_hash("https://b.com")
        assert h1 != h2

    def test_set_and_get(self, cache: PatentCache) -> None:
        url = "https://patents.google.com/patent/US1234567B2/en"
        cache.set(url, "<html>content</html>", 200)
        result = cache.get(url)
        assert result is not None
        html, status_code = result
        assert html == "<html>content</html>"
        assert status_code == 200

    def test_get_miss(self, cache: PatentCache) -> None:
        result = cache.get("https://nonexistent.com")
        assert result is None

    def test_get_expired(self, tmp_path: Path) -> None:
        db = tmp_path / "expire_test.db"
        cache = PatentCache(db, ttl_seconds=1)
        url = "https://example.com/expired"
        cache.set(url, "<html>old</html>", 200)
        # Manually backdate the cached_at
        conn = cache._get_conn()
        url_hash = cache._url_hash(url)
        conn.execute(
            "UPDATE html_cache SET cached_at = ? WHERE url_hash = ?",
            (time.time() - 100, url_hash),
        )
        conn.commit()
        result = cache.get(url)
        assert result is None

    def test_set_replaces_existing(self, cache: PatentCache) -> None:
        url = "https://example.com/replace"
        cache.set(url, "<html>v1</html>", 200)
        cache.set(url, "<html>v2</html>", 200)
        result = cache.get(url)
        assert result is not None
        assert result[0] == "<html>v2</html>"

    def test_close(self, cache: PatentCache) -> None:
        cache._get_conn()
        assert cache._conn is not None
        cache.close()
        assert cache._conn is None

    def test_close_when_not_open(self, cache: PatentCache) -> None:
        # Should not raise
        cache.close()
        assert cache._conn is None


# ---------------------------------------------------------------------------
# CachingAsyncClient tests
# ---------------------------------------------------------------------------


class TestCachingAsyncClient:
    """Tests for the async HTTP client wrapper with caching."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> PatentCache:
        db = tmp_path / "async_cache.db"
        return PatentCache(db, ttl_seconds=3600)

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        client = CachingAsyncClient(cache=None)
        async with client as c:
            assert c is client
            assert c._client is not None
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_without_context_raises(self) -> None:
        client = CachingAsyncClient(cache=None)
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.get("https://example.com")

    @pytest.mark.asyncio
    async def test_get_returns_cached_response(self, cache: PatentCache) -> None:
        url = "https://patents.google.com/patent/TEST/en"
        cache.set(url, "<html>cached</html>", 200)
        client = CachingAsyncClient(cache=cache)
        async with client:
            response = await client.get(url)
        assert response.status_code == 200
        assert response.text == "<html>cached</html>"

    @pytest.mark.asyncio
    async def test_get_cache_miss_fetches_network(self, cache: PatentCache) -> None:
        """On cache miss, the client fetches from the network and caches 200 responses."""

        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(200, text="<html>fresh</html>")

        transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=cache, transport=transport)
        url = "https://example.com/patent"
        async with client:
            response = await client.get(url)
        assert response.status_code == 200
        assert response.text == "<html>fresh</html>"
        # Verify it was cached
        cached = cache.get(url)
        assert cached is not None
        assert cached[0] == "<html>fresh</html>"

    @pytest.mark.asyncio
    async def test_get_non_200_not_cached(self, cache: PatentCache) -> None:
        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(404, text="Not found")

        transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=cache, transport=transport)
        url = "https://example.com/missing"
        async with client:
            response = await client.get(url)
        assert response.status_code == 404
        assert cache.get(url) is None

    @pytest.mark.asyncio
    async def test_get_no_cache(self) -> None:
        """When cache is None, requests go straight to network."""

        def handler(request: httpx.Request) -> httpx.Response:  # noqa: ARG001
            return httpx.Response(200, text="<html>no-cache</html>")

        transport = httpx.MockTransport(handler)
        client = CachingAsyncClient(cache=None, transport=transport)
        async with client:
            response = await client.get("https://example.com")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# build_cached_http_client tests
# ---------------------------------------------------------------------------


class TestBuildCachedHttpClient:
    """Tests for the factory function."""

    def test_returns_caching_client_no_cache(self) -> None:
        client = build_cached_http_client(use_cache=False, cache_name="test")
        assert isinstance(client, CachingAsyncClient)
        assert client._cache is None

    def test_returns_caching_client_with_cache(self) -> None:
        client = build_cached_http_client(use_cache=True, cache_name="test_build")
        assert isinstance(client, CachingAsyncClient)
        assert client._cache is not None
        assert isinstance(client._cache, PatentCache)
        # Clean up
        client._cache.close()

    def test_headers_merged(self) -> None:
        client = build_cached_http_client(
            use_cache=False,
            cache_name="test",
            headers={"X-Custom": "value"},
        )
        assert "User-Agent" in client._headers
        assert client._headers["X-Custom"] == "value"

    def test_default_headers_present(self) -> None:
        client = build_cached_http_client(use_cache=False, cache_name="test")
        assert "User-Agent" in client._headers
        assert "Accept-Language" in client._headers
