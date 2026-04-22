"""Shared HTTP caching helpers for consumer clients."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from hishel import AsyncSqliteStorage  # type: ignore[attr-defined]
from hishel.httpx import AsyncCacheClient  # type: ignore[attr-defined]
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential_jitter


class RetryingAsyncSqliteStorage(AsyncSqliteStorage):
    """SQLite-backed cache storage with WAL pragmas and lock-retry.

    Applies ``journal_mode=WAL``, ``synchronous=NORMAL``, and ``busy_timeout=5000``
    on first connection so concurrent readers/writers don't block each other.
    Wraps the mutating operations in a tenacity retryer to absorb the remaining
    ``database is locked`` errors that can still occur under contention.
    """

    def __init__(self, *args: Any, max_attempts: int = 5, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._max_attempts = max_attempts
        self._pragmas_set = False

    def _retryer(self) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential_jitter(initial=0.1, max=2.0),
            reraise=True,
        )

    async def _ensure_connection(self):  # type: ignore[override]
        connection = await super()._ensure_connection()
        if not self._pragmas_set:
            cursor = await connection.cursor()
            await cursor.execute("PRAGMA journal_mode=WAL")
            await cursor.execute("PRAGMA synchronous=NORMAL")
            await cursor.execute("PRAGMA busy_timeout=5000")
            await connection.commit()
            self._pragmas_set = True
        return connection

    async def create_entry(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        async for attempt in self._retryer():
            with attempt:
                return await super().create_entry(*args, **kwargs)

    async def get_entries(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        async for attempt in self._retryer():
            with attempt:
                return await super().get_entries(*args, **kwargs)

    async def _batch_cleanup(self, *args: Any, **kwargs: Any):  # type: ignore[override]
        async for attempt in self._retryer():
            with attempt:
                return await super()._batch_cleanup(*args, **kwargs)


@dataclass
class CacheStats:
    """Statistics about cache usage and storage."""

    hits: int = 0
    misses: int = 0
    entry_count: int = 0
    size_bytes: int = 0
    database_path: str = ""

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def size_mb(self) -> float:
        """Return cache size in megabytes."""
        return self.size_bytes / (1024 * 1024)


@dataclass
class CacheManager:
    """Manages cache storage, statistics, and invalidation.

    Example:
        manager = CacheManager(database_path="/path/to/cache.db")

        # After using client...
        stats = await manager.get_stats()
        print(f"Hit rate: {stats.hit_rate:.1f}%")

        # Clear old entries
        await manager.clear_expired()

        # Clear everything
        await manager.clear_all()
    """

    database_path: Path
    ttl_seconds: int | None = None
    max_retries: int = 5
    _hits: int = field(default=0, init=False, repr=False)
    _misses: int = field(default=0, init=False, repr=False)
    _storage: AsyncSqliteStorage | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.database_path = Path(self.database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def _retryer(self) -> AsyncRetrying:
        return AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential_jitter(initial=0.1, max=2.0),
            reraise=True,
        )

    def get_storage(self) -> AsyncSqliteStorage:
        """Get or create the storage instance (WAL-enabled, lock-retrying)."""
        if self._storage is None:
            self._storage = RetryingAsyncSqliteStorage(
                database_path=str(self.database_path),
                max_attempts=self.max_retries,
            )
        return self._storage

    def record_hit(self) -> None:
        """Record a cache hit."""
        self._hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self._misses += 1

    async def get_stats(self) -> CacheStats:
        """Get current cache statistics.

        Returns:
            CacheStats with hit/miss counts, entry count, and storage size.
        """
        entry_count = 0
        size_bytes = 0

        if self.database_path.exists():
            size_bytes = self.database_path.stat().st_size

            # Query entry count from database
            async for attempt in self._retryer():
                with attempt:
                    # Use synchronous sqlite3 for simple queries
                    conn = sqlite3.connect(str(self.database_path))
                    try:
                        cursor = conn.execute("SELECT COUNT(*) FROM cache WHERE 1=1")
                        row = cursor.fetchone()
                        entry_count = row[0] if row else 0
                    except sqlite3.OperationalError:
                        # Table might not exist yet
                        entry_count = 0
                    finally:
                        conn.close()

        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            entry_count=entry_count,
            size_bytes=size_bytes,
            database_path=str(self.database_path),
        )

    async def clear_all(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared.
        """
        if not self.database_path.exists():
            return 0

        cleared = 0
        async for attempt in self._retryer():
            with attempt:
                conn = sqlite3.connect(str(self.database_path))
                try:
                    cursor = conn.execute("SELECT COUNT(*) FROM cache")
                    row = cursor.fetchone()
                    cleared = row[0] if row else 0
                    conn.execute("DELETE FROM cache")
                    conn.commit()
                except sqlite3.OperationalError:
                    cleared = 0
                finally:
                    conn.close()

        return cleared

    async def clear_expired(self, max_age: timedelta | None = None) -> int:
        """Clear expired cache entries.

        Args:
            max_age: Maximum age for entries. If None, uses ttl_seconds or 24 hours.

        Returns:
            Number of entries cleared.
        """
        if not self.database_path.exists():
            return 0

        if max_age is None:
            if self.ttl_seconds:
                max_age = timedelta(seconds=self.ttl_seconds)
            else:
                max_age = timedelta(hours=24)

        cutoff = datetime.now() - max_age
        cutoff_ts = cutoff.timestamp()

        cleared = 0
        async for attempt in self._retryer():
            with attempt:
                conn = sqlite3.connect(str(self.database_path))
                try:
                    # hishel stores created_at as a float timestamp
                    cursor = conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff_ts,))
                    cleared = cursor.rowcount
                    conn.commit()
                except sqlite3.OperationalError:
                    cleared = 0
                finally:
                    conn.close()

        return cleared

    async def invalidate_pattern(self, url_pattern: str) -> int:
        """Invalidate cache entries matching a URL pattern.

        Args:
            url_pattern: Regex pattern to match against cached URLs.

        Returns:
            Number of entries invalidated.
        """
        if not self.database_path.exists():
            return 0

        pattern = re.compile(url_pattern)
        cleared = 0

        async for attempt in self._retryer():
            with attempt:
                conn = sqlite3.connect(str(self.database_path))
                try:
                    # Get all keys and filter by pattern
                    cursor = conn.execute("SELECT key FROM cache")
                    keys_to_delete = [row[0] for row in cursor.fetchall() if pattern.search(row[0])]

                    if keys_to_delete:
                        placeholders = ",".join("?" * len(keys_to_delete))
                        conn.execute(
                            f"DELETE FROM cache WHERE key IN ({placeholders})",
                            keys_to_delete,
                        )
                        conn.commit()
                        cleared = len(keys_to_delete)
                except sqlite3.OperationalError:
                    cleared = 0
                finally:
                    conn.close()

        return cleared

    async def close(self) -> None:
        """Close the storage connection."""
        if self._storage is not None:
            await self._storage.close()
            self._storage = None


def get_default_cache_dir() -> Path:
    """Get the default cache directory, scoped to the first-configured app."""
    from .logging import default_app_name

    return Path.home() / ".cache" / default_app_name()


def build_cached_http_client(
    *,
    use_cache: bool,
    cache_name: str,
    cache_dir: Path | None = None,
    ttl_seconds: int | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float | None = None,
    auth: httpx.Auth | None = None,
    **client_kwargs: Any,
) -> tuple[httpx.AsyncClient, CacheManager | None]:
    """Return an AsyncClient with optional caching and a CacheManager.

    Args:
        use_cache: Whether to enable HTTP caching.
        cache_name: Name for the cache database file.
        cache_dir: Custom cache directory. Defaults to the configured app's
            cache dir (``~/.cache/{app_name}``).
        ttl_seconds: Default TTL for cache entries. None uses HTTP headers.
        headers: Additional headers to include in requests.
        timeout: Request timeout in seconds (passes through to httpx).
        auth: httpx Auth handler (e.g. for OAuth2 token refresh).
        **client_kwargs: Additional arguments for httpx.AsyncClient.

    Returns:
        Tuple of (client, cache_manager). cache_manager is None if use_cache=False.
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

    extra: dict[str, Any] = {}
    if timeout is not None:
        extra["timeout"] = httpx.Timeout(timeout)
    if auth is not None:
        extra["auth"] = auth

    if not use_cache:
        return httpx.AsyncClient(headers=merged_headers, **extra, **client_kwargs), None

    cache_root = cache_dir or get_default_cache_dir()
    cache_root.mkdir(parents=True, exist_ok=True)
    db_path = cache_root / f"{cache_name}.db"

    manager = CacheManager(database_path=db_path, ttl_seconds=ttl_seconds)
    storage = manager.get_storage()

    client = AsyncCacheClient(  # type: ignore[misc]
        headers=merged_headers,
        storage=storage,
        **extra,
        **client_kwargs,
    )

    return client, manager


__all__ = [
    "CacheManager",
    "CacheStats",
    "RetryingAsyncSqliteStorage",
    "build_cached_http_client",
    "get_default_cache_dir",
]
