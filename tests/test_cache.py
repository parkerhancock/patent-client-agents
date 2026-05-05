"""Cache module tests for patent_client_agents."""

from __future__ import annotations

import sqlite3
import time
from datetime import timedelta
from pathlib import Path

import pytest

from law_tools_core.cache import CacheManager, CacheStats, build_cached_http_client


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_hit_rate_calculation(self) -> None:
        """Verify hit rate is calculated correctly."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_rate == 75.0

    def test_hit_rate_zero_total(self) -> None:
        """Verify hit rate is 0 when no requests made."""
        stats = CacheStats(hits=0, misses=0)
        assert stats.hit_rate == 0.0

    def test_size_mb_conversion(self) -> None:
        """Verify bytes to MB conversion."""
        stats = CacheStats(size_bytes=1024 * 1024 * 5)  # 5 MB
        assert stats.size_mb == 5.0


class TestCacheManager:
    """Tests for CacheManager."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "test_cache.db"

    @pytest.fixture
    def manager(self, temp_db: Path) -> CacheManager:
        """Create a CacheManager with temporary storage."""
        return CacheManager(database_path=temp_db)

    @pytest.fixture
    def populated_db(self, temp_db: Path) -> Path:
        """Create a database with test data."""
        conn = sqlite3.connect(str(temp_db))
        conn.execute("""
            CREATE TABLE cache (
                key TEXT PRIMARY KEY,
                data BLOB,
                created_at REAL
            )
        """)
        now = time.time()
        conn.executemany(
            "INSERT INTO cache (key, data, created_at) VALUES (?, ?, ?)",
            [
                ("https://api.example.com/resource/1", b"data1", now),
                ("https://api.example.com/resource/2", b"data2", now - 3600),  # 1 hour old
                ("https://api.other.com/item/abc", b"data3", now - 7200),  # 2 hours old
            ],
        )
        conn.commit()
        conn.close()
        return temp_db

    def test_manager_creates_parent_directory(self, tmp_path: Path) -> None:
        """Verify manager creates parent directories."""
        deep_path = tmp_path / "a" / "b" / "c" / "cache.db"
        CacheManager(database_path=deep_path)
        assert deep_path.parent.exists()

    def test_record_hit_increments_counter(self, manager: CacheManager) -> None:
        """Verify hit recording increments counter."""
        assert manager._hits == 0
        manager.record_hit()
        manager.record_hit()
        assert manager._hits == 2

    def test_record_miss_increments_counter(self, manager: CacheManager) -> None:
        """Verify miss recording increments counter."""
        assert manager._misses == 0
        manager.record_miss()
        assert manager._misses == 1

    @pytest.mark.asyncio
    async def test_get_stats_empty_db(self, manager: CacheManager) -> None:
        """Verify stats for non-existent database."""
        stats = await manager.get_stats()
        assert stats.entry_count == 0
        assert stats.size_bytes == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self, populated_db: Path) -> None:
        """Verify stats with populated database."""
        manager = CacheManager(database_path=populated_db)
        manager.record_hit()
        manager.record_hit()
        manager.record_miss()

        stats = await manager.get_stats()
        assert stats.entry_count == 3
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.size_bytes > 0
        assert stats.hit_rate == pytest.approx(66.67, rel=0.01)

    @pytest.mark.asyncio
    async def test_clear_all(self, populated_db: Path) -> None:
        """Verify clearing all cache entries."""
        manager = CacheManager(database_path=populated_db)
        cleared = await manager.clear_all()
        assert cleared == 3

        stats = await manager.get_stats()
        assert stats.entry_count == 0

    @pytest.mark.asyncio
    async def test_clear_all_empty_db(self, manager: CacheManager) -> None:
        """Verify clearing empty database returns 0."""
        cleared = await manager.clear_all()
        assert cleared == 0

    @pytest.mark.asyncio
    async def test_clear_expired(self, populated_db: Path) -> None:
        """Verify clearing expired entries."""
        manager = CacheManager(database_path=populated_db)

        # Clear entries older than 90 minutes
        cleared = await manager.clear_expired(max_age=timedelta(minutes=90))
        assert cleared == 1  # Only the 2-hour old entry

        stats = await manager.get_stats()
        assert stats.entry_count == 2

    @pytest.mark.asyncio
    async def test_clear_expired_all_old(self, populated_db: Path) -> None:
        """Verify clearing all entries when all are expired."""
        manager = CacheManager(database_path=populated_db)
        # Clear entries older than 30 minutes - only 2 are older
        cleared = await manager.clear_expired(max_age=timedelta(minutes=30))
        assert cleared == 2

    @pytest.mark.asyncio
    async def test_clear_expired_default_ttl(self, populated_db: Path) -> None:
        """Verify clear_expired uses ttl_seconds when max_age is None."""
        manager = CacheManager(database_path=populated_db, ttl_seconds=1800)
        # ttl_seconds=1800 (30 min) -> entries older than 30 min cleared
        cleared = await manager.clear_expired()
        assert cleared == 2

    @pytest.mark.asyncio
    async def test_clear_expired_default_24h(self, populated_db: Path) -> None:
        """Verify clear_expired uses 24h default when no ttl_seconds."""
        manager = CacheManager(database_path=populated_db)
        # No ttl_seconds -> defaults to 24 hours; all entries are recent
        cleared = await manager.clear_expired()
        assert cleared == 0

    @pytest.mark.asyncio
    async def test_clear_expired_nonexistent_db(self, tmp_path: Path) -> None:
        """Verify clear_expired returns 0 for nonexistent db."""
        manager = CacheManager(database_path=tmp_path / "nope.db")
        cleared = await manager.clear_expired()
        assert cleared == 0

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_db(self, tmp_path: Path) -> None:
        """Verify invalidate returns 0 for nonexistent db."""
        manager = CacheManager(database_path=tmp_path / "nope.db")
        cleared = await manager.invalidate_pattern(".*")
        assert cleared == 0

    @pytest.mark.asyncio
    async def test_close_with_storage_resets_to_none(self, temp_db: Path) -> None:
        """Verify close resets storage to None (storage.aclose may not exist in all versions)."""
        manager = CacheManager(database_path=temp_db)
        # Initialize storage
        storage = manager.get_storage()
        assert manager._storage is not None
        # Patch aclose to avoid AttributeError if it doesn't exist
        if not hasattr(storage, "aclose"):
            storage.aclose = storage.close  # type: ignore[attr-defined]
        await manager.close()
        assert manager._storage is None

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, populated_db: Path) -> None:
        """Verify invalidating by URL pattern."""
        manager = CacheManager(database_path=populated_db)

        # Invalidate all api.example.com entries
        cleared = await manager.invalidate_pattern(r"api\.example\.com")
        assert cleared == 2

        stats = await manager.get_stats()
        assert stats.entry_count == 1

    @pytest.mark.asyncio
    async def test_invalidate_pattern_no_match(self, populated_db: Path) -> None:
        """Verify invalidate returns 0 when no match."""
        manager = CacheManager(database_path=populated_db)
        cleared = await manager.invalidate_pattern(r"nonexistent\.domain")
        assert cleared == 0

    @pytest.mark.asyncio
    async def test_invalidate_specific_resource(self, populated_db: Path) -> None:
        """Verify invalidating specific resource."""
        manager = CacheManager(database_path=populated_db)
        cleared = await manager.invalidate_pattern(r"/resource/1$")
        assert cleared == 1

    @pytest.mark.asyncio
    async def test_close(self, manager: CacheManager) -> None:
        """Verify close method doesn't raise."""
        await manager.close()
        # Should be safe to call multiple times
        await manager.close()


class TestBuildCachedHttpClient:
    """Tests for build_cached_http_client function."""

    def test_cache_disabled_returns_none_manager(self, tmp_path: Path) -> None:
        """Verify no manager returned when cache disabled."""
        client, manager = build_cached_http_client(
            use_cache=False,
            cache_name="test",
            cache_dir=tmp_path,
        )
        assert manager is None

    def test_cache_enabled_returns_manager(self, tmp_path: Path) -> None:
        """Verify manager returned when cache enabled."""
        client, manager = build_cached_http_client(
            use_cache=True,
            cache_name="test",
            cache_dir=tmp_path,
        )
        assert manager is not None
        assert isinstance(manager, CacheManager)

    def test_ttl_passed_to_manager(self, tmp_path: Path) -> None:
        """Verify TTL is passed to cache manager."""
        client, manager = build_cached_http_client(
            use_cache=True,
            cache_name="test",
            cache_dir=tmp_path,
            ttl_seconds=3600,
        )
        assert manager is not None
        assert manager.ttl_seconds == 3600

    def test_creates_cache_directory(self, tmp_path: Path) -> None:
        """Verify cache directory is created."""
        cache_dir = tmp_path / "custom" / "cache"
        build_cached_http_client(
            use_cache=True,
            cache_name="test",
            cache_dir=cache_dir,
        )
        assert cache_dir.exists()

    def test_does_not_inject_chrome_user_agent_default(self, tmp_path: Path) -> None:
        """The default User-Agent must NOT be a Chrome impersonator.

        Akamai-protected govt sites (USITC EDIS, federalregister.gov,
        consumerfinance.gov) flag the combination of a browser UA with
        httpx's TLS fingerprint as a "browser impersonator" and 403 the
        request. Letting httpx send its native ``python-httpx/x.y.z``
        UA passes those WAFs cleanly.
        """
        client, _ = build_cached_http_client(
            use_cache=False,
            cache_name="test",
            cache_dir=tmp_path,
        )
        ua = client.headers.get("User-Agent", "")
        assert "Mozilla" not in ua, f"Chrome-impersonator UA leaked back: {ua!r}"
        assert "Chrome" not in ua, f"Chrome-impersonator UA leaked back: {ua!r}"
        assert "Accept-Language" not in client.headers, (
            "Accept-Language is a browser-only header; do not set by default"
        )

    def test_caller_can_still_set_user_agent(self, tmp_path: Path) -> None:
        """Callers that need a specific UA (e.g. SEC EDGAR mandates an
        email contact in the UA) must be able to pass one through."""
        client, _ = build_cached_http_client(
            use_cache=False,
            cache_name="test",
            cache_dir=tmp_path,
            headers={"User-Agent": "law-tools test@example.com"},
        )
        assert client.headers["User-Agent"] == "law-tools test@example.com"
