"""Shared HTTP caching helpers for MCP clients.

This module provides a simple file-based cache for Google Patents HTML responses.
Since Google Patents doesn't send proper HTTP cache headers, we implement our own
application-level caching with configurable TTL.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from law_tools_core.cache import get_default_cache_dir

logger = logging.getLogger(__name__)

# Cache TTL: 30 days for patent pages (they rarely change)
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60


class PatentCache:
    """Simple SQLite-based cache for patent HTML responses.

    This provides reliable caching regardless of HTTP headers, with configurable TTL.
    """

    def __init__(self, db_path: Path, ttl_seconds: int = CACHE_TTL_SECONDS) -> None:
        self.db_path = db_path
        self.ttl_seconds = ttl_seconds
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS html_cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    html TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    cached_at REAL NOT NULL
                )
            """)
            self._conn.commit()
        return self._conn

    def _url_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()

    def get(self, url: str) -> tuple[str, int] | None:
        """Get cached HTML for URL if not expired.

        Returns:
            Tuple of (html, status_code) or None if not cached/expired
        """
        conn = self._get_conn()
        url_hash = self._url_hash(url)
        cursor = conn.execute(
            "SELECT html, status_code, cached_at FROM html_cache WHERE url_hash = ?",
            (url_hash,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        html, status_code, cached_at = row
        if time.time() - cached_at > self.ttl_seconds:
            # Expired - delete and return None
            conn.execute("DELETE FROM html_cache WHERE url_hash = ?", (url_hash,))
            conn.commit()
            return None

        logger.debug("Cache hit for %s", url)
        return html, status_code

    def set(self, url: str, html: str, status_code: int) -> None:
        """Store HTML in cache."""
        conn = self._get_conn()
        url_hash = self._url_hash(url)
        conn.execute(
            """
            INSERT OR REPLACE INTO html_cache (url_hash, url, html, status_code, cached_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (url_hash, url, html, status_code, time.time()),
        )
        conn.commit()
        logger.debug("Cached response for %s", url)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class CachingAsyncClient:
    """Async HTTP client wrapper with application-level caching.

    Wraps httpx.AsyncClient and adds file-based caching for GET requests.
    """

    def __init__(
        self,
        cache: PatentCache | None,
        headers: dict[str, str] | None = None,
        **client_kwargs: Any,
    ) -> None:
        self._cache = cache
        self._headers = headers or {}
        self._client_kwargs = client_kwargs
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> CachingAsyncClient:
        self._client = httpx.AsyncClient(headers=self._headers, **self._client_kwargs)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """GET request with caching.

        Supports all httpx.AsyncClient.get() kwargs like follow_redirects, timeout, etc.
        """
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        # Check cache first (only for the exact URL)
        if self._cache:
            cached = self._cache.get(url)
            if cached:
                html, status_code = cached
                logger.info("Cache HIT for %s", url)
                # Create a mock response from cache
                return httpx.Response(
                    status_code=status_code,
                    content=html.encode("utf-8"),
                    request=httpx.Request("GET", url),
                )
            else:
                logger.info("Cache MISS for %s", url)

        # Not cached - fetch from network
        response = await self._client.get(url, **kwargs)

        # Cache successful responses
        if self._cache and response.status_code == 200:
            self._cache.set(url, response.text, response.status_code)

        return response


def build_cached_http_client(
    *,
    use_cache: bool,
    cache_name: str,
    headers: Mapping[str, str] | None = None,
    **client_kwargs: Any,
) -> CachingAsyncClient:
    """Return an AsyncClient with application-level caching.

    Args:
        use_cache: Whether to enable caching
        cache_name: Name for the cache database file
        headers: HTTP headers to send with requests
        **client_kwargs: Additional kwargs for httpx.AsyncClient

    Returns:
        CachingAsyncClient that can be used as async context manager
    """
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    merged_headers = dict(default_headers)
    if headers:
        merged_headers.update(headers)

    cache = None
    if use_cache:
        cache_root = get_default_cache_dir()
        cache = PatentCache(cache_root / f"{cache_name}_html.db")

    return CachingAsyncClient(
        cache=cache,
        headers=merged_headers,
        **client_kwargs,
    )


__all__ = ["build_cached_http_client", "PatentCache", "CachingAsyncClient"]
