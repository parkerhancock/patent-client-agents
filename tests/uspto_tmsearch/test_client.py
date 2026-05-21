"""Tests for USPTO Trademark Search client.

Live tests hit the real USPTO API and require a valid WAF token.
Run with: pytest -m live_tmsearch
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from patent_client_agents.uspto_tmsearch import TmsearchClient

# Async fixtures + tests across the module; live_tmsearch is class-scoped
# below so the unit tests in TestTmsearchClientNoToken still run in CI.
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[TmsearchClient]:
    """Create a client for testing."""
    async with TmsearchClient() as c:
        yield c


@pytest.mark.live_tmsearch
class TestTmsearchClient:
    """Live tests for TmsearchClient."""

    async def test_search_wordmark(self, client: TmsearchClient) -> None:
        """Test searching by wordmark."""
        results = await client.search_wordmark("APPLE", size=5)
        assert results.total > 0
        assert len(results.results) > 0
        # All results should have a serial number
        for r in results.results:
            assert r.serial_number

    async def test_search_wordmark_live_only(self, client: TmsearchClient) -> None:
        """Test searching for live marks only."""
        results = await client.search_wordmark("APPLE", live_only=True, size=5)
        assert results.total > 0
        # All results should be live
        for r in results.results:
            assert r.is_live

    async def test_search_owner(self, client: TmsearchClient) -> None:
        """Test searching by owner."""
        results = await client.search_owner("TESLA", live_only=True, size=5)
        assert results.total > 0
        assert len(results.results) > 0

    async def test_search_goods_services(self, client: TmsearchClient) -> None:
        """Test searching by goods/services."""
        results = await client.search_goods_services("electric vehicles", size=5)
        assert results.total > 0
        assert len(results.results) > 0

    async def test_get_by_serial(self, client: TmsearchClient) -> None:
        """Test getting a trademark by serial number."""
        result = await client.get_by_serial("97123456")
        if result:
            assert result.serial_number == "97123456"

    async def test_combined_search(self, client: TmsearchClient) -> None:
        """Test combined search criteria."""
        results = await client.search(
            wordmark="MODEL",
            owner="TESLA",
            live_only=True,
            size=10,
        )
        assert results.total > 0
        for r in results.results:
            assert r.is_live

    async def test_pagination(self, client: TmsearchClient) -> None:
        """Test pagination with from_ parameter."""
        page1 = await client.search_wordmark("APPLE", size=10, from_=0)
        page2 = await client.search_wordmark("APPLE", size=10, from_=10)

        if page1.results and page2.results:
            assert page1.results[0].serial_number != page2.results[0].serial_number


class TestTmsearchClientNoToken:
    """Test that client handles missing token/Playwright gracefully."""

    @pytest.mark.asyncio
    async def test_raises_without_token_or_playwright(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """ConfigurationError raised when no cached token and no Playwright."""
        import patent_client_agents.uspto_tmsearch.token_manager as tm_module

        monkeypatch.setattr(tm_module, "PLAYWRIGHT_AVAILABLE", False)

        from mcp_data_core.exceptions import ConfigurationError

        client = TmsearchClient(token_path="/nonexistent/path/token.json")
        with pytest.raises(ConfigurationError, match="No valid WAF token"):
            await client._init_session()

    @pytest.mark.asyncio
    async def test_post_retry_surfaces_auth_error_when_no_playwright(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: object
    ) -> None:
        """When the cached token is rejected and Playwright is unavailable,
        _post raises AuthenticationError carrying the upstream status —
        not the misleading 'No valid WAF token cached' ConfigurationError.
        """
        import patent_client_agents.uspto_tmsearch.token_manager as tm_module
        from mcp_data_core.exceptions import AuthenticationError

        # Seed a valid cached token so _init_session succeeds.
        token_path = tmp_path / "waf_token.json"
        token_path.write_text(
            '{"token": "stale-but-parseable", '
            '"expires": 9999999999, '
            '"acquired": "2026-05-06T00:00:00+00:00"}'
        )
        monkeypatch.setattr(tm_module, "PLAYWRIGHT_AVAILABLE", False)

        client = TmsearchClient(token_path=token_path)
        await client._init_session()

        class _FakeResponse:
            status_code = 403

            def json(self) -> dict:  # pragma: no cover - not reached
                return {}

        async def _fake_post(*args, **kwargs):
            return _FakeResponse()

        assert client._session is not None
        monkeypatch.setattr(client._session, "post", _fake_post)

        with pytest.raises(AuthenticationError, match="403"):
            await client._post({"query": "stub"})
