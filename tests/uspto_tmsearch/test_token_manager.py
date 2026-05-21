"""Tests for WAF token manager."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.uspto_tmsearch.token_manager import WafTokenManager

_FRESH = ("fresh-token", 9999999999.0)
_NEW = ("new-token", 9999999999.0)
_FORCED = ("forced-fresh", 9999999999.0)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_waf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Don't let the developer's shell env leak into cache-precedence tests."""
    monkeypatch.delenv("PCA_WAF_TOKEN_JSON", raising=False)
    monkeypatch.delenv("PCA_WAF_TOKEN_PATH", raising=False)


def _write_token(path: Path, token: str = "test-token", expires_in: float = 86400 * 4) -> None:
    """Write a token cache file."""
    expires = datetime.now(UTC).timestamp() + expires_in
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": token, "expires": expires}))


class TestCacheHit:
    async def test_returns_cached_token(self, tmp_path: Path) -> None:
        cache = tmp_path / "token.json"
        _write_token(cache, token="cached-abc")

        manager = WafTokenManager(token_path=cache)
        token = await manager.get_token()
        assert token == "cached-abc"

    async def test_does_not_launch_playwright(self, tmp_path: Path) -> None:
        cache = tmp_path / "token.json"
        _write_token(cache)

        manager = WafTokenManager(token_path=cache)
        with patch.object(manager, "_acquire_token", new_callable=AsyncMock) as mock:
            await manager.get_token()
            mock.assert_not_called()


class TestCacheExpired:
    async def test_acquires_new_token_when_expired(self, tmp_path: Path) -> None:
        cache = tmp_path / "token.json"
        _write_token(cache, token="old-token", expires_in=-1)  # already expired

        manager = WafTokenManager(token_path=cache)
        with patch.object(manager, "_acquire_token", new_callable=AsyncMock, return_value=_FRESH):
            token = await manager.get_token()
            assert token == "fresh-token"

    async def test_treats_near_expiry_as_expired(self, tmp_path: Path) -> None:
        """Token expiring within the 6-hour margin should be refreshed."""
        cache = tmp_path / "token.json"
        _write_token(cache, token="soon-expired", expires_in=3600 * 5)  # 5 hours < 6 hour margin

        manager = WafTokenManager(token_path=cache)
        with patch.object(manager, "_acquire_token", new_callable=AsyncMock, return_value=_FRESH):
            token = await manager.get_token()
            assert token == "fresh-token"


class TestCacheMissing:
    async def test_raises_without_playwright(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import patent_client_agents.uspto_tmsearch.token_manager as mod

        monkeypatch.setattr(mod, "PLAYWRIGHT_AVAILABLE", False)

        cache = tmp_path / "nonexistent" / "token.json"
        manager = WafTokenManager(token_path=cache)

        with pytest.raises(ConfigurationError, match="No valid WAF token"):
            await manager.get_token()

    async def test_acquires_with_playwright(self, tmp_path: Path) -> None:
        cache = tmp_path / "token.json"
        manager = WafTokenManager(token_path=cache)

        with patch.object(manager, "_acquire_token", new_callable=AsyncMock, return_value=_NEW):
            token = await manager.get_token()
            assert token == "new-token"

        # Verify cache was written
        assert cache.exists()
        data = json.loads(cache.read_text())
        assert data["token"] == "new-token"


class TestForceRefresh:
    async def test_ignores_valid_cache(self, tmp_path: Path) -> None:
        cache = tmp_path / "token.json"
        _write_token(cache, token="old-cached")

        manager = WafTokenManager(token_path=cache)
        with patch.object(manager, "_acquire_token", new_callable=AsyncMock, return_value=_FORCED):
            token = await manager.get_token(force_refresh=True)
            assert token == "forced-fresh"


class TestEnvPayload:
    """``PCA_WAF_TOKEN_JSON`` is the cloud-mode source of truth."""

    async def test_env_var_wins_when_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache = tmp_path / "token.json"
        _write_token(cache, token="cache-token")
        env_expires = datetime.now(UTC).timestamp() + 86400 * 4
        monkeypatch.setenv(
            "PCA_WAF_TOKEN_JSON",
            json.dumps({"token": "env-token", "expires": env_expires}),
        )

        manager = WafTokenManager(token_path=cache)
        token = await manager.get_token()
        assert token == "env-token"

    async def test_env_var_used_when_cache_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_expires = datetime.now(UTC).timestamp() + 86400 * 4
        monkeypatch.setenv(
            "PCA_WAF_TOKEN_JSON",
            json.dumps({"token": "env-only", "expires": env_expires}),
        )

        manager = WafTokenManager(token_path=tmp_path / "nonexistent.json")
        token = await manager.get_token()
        assert token == "env-only"

    async def test_expired_env_var_falls_through_to_acquire(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(
            "PCA_WAF_TOKEN_JSON",
            json.dumps({"token": "stale", "expires": 0.0}),
        )

        manager = WafTokenManager(token_path=tmp_path / "token.json")
        with patch.object(manager, "_acquire_token", new_callable=AsyncMock, return_value=_FRESH):
            token = await manager.get_token()
            assert token == "fresh-token"

    async def test_disk_wins_over_env_when_acquired_is_newer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After in-process Playwright mints a fresh token to disk, that
        token should win over a stale (Secret-Manager-mounted) env token.
        Both must parse successfully; the tiebreaker is the ``acquired``
        timestamp. Without this, every call after env-token exhaustion
        would re-mint via Playwright (10-20s each) instead of reusing
        the just-minted disk copy.
        """
        cache = tmp_path / "token.json"
        env_expires = datetime.now(UTC).timestamp() + 86400 * 4
        # Env token: older acquired timestamp.
        monkeypatch.setenv(
            "PCA_WAF_TOKEN_JSON",
            json.dumps(
                {
                    "token": "env-stale",
                    "expires": env_expires,
                    "acquired": "2026-05-06T15:16:53+00:00",
                }
            ),
        )
        # Disk token: newer acquired timestamp (just-minted).
        cache.write_text(
            json.dumps(
                {
                    "token": "disk-fresh",
                    "expires": env_expires,
                    "acquired": "2026-05-06T19:30:00+00:00",
                }
            )
        )

        manager = WafTokenManager(token_path=cache)
        token = await manager.get_token()
        assert token == "disk-fresh"
