"""Tests for USPTO Trademark Assignment client."""

import pytest

from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient


class TestTrademarkAssignmentClient:
    """Tests for TrademarkAssignmentClient."""

    def test_default_base_url(self) -> None:
        """Test default base URL is set correctly."""
        client = TrademarkAssignmentClient.__new__(TrademarkAssignmentClient)
        assert client.DEFAULT_BASE_URL == "https://assignmentcenter.uspto.gov"


@pytest.mark.live_trademark_assignments
class TestTrademarkAssignmentClientLive:
    """Live tests for TrademarkAssignmentClient."""

    @pytest.mark.asyncio
    async def test_search_by_assignee(self, vcr_cassette) -> None:
        """Test searching by assignee name."""
        async with TrademarkAssignmentClient() as client:
            results = await client.search_by_assignee("Apple", limit=5)
            assert isinstance(results, list)
            assert len(results) > 0
            # Verify structure
            record = results[0]
            assert record.reel_number > 0
            assert record.frame_number
            assert "APPLE" in " ".join(record.assignees).upper()

    @pytest.mark.asyncio
    async def test_search_by_assignor(self, vcr_cassette) -> None:
        """Test searching by assignor name."""
        async with TrademarkAssignmentClient() as client:
            results = await client.search_by_assignor("Pixelmator", limit=5)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_by_serial(self, vcr_cassette) -> None:
        """Test searching by serial number."""
        async with TrademarkAssignmentClient() as client:
            results = await client.search_by_serial("88874668")
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_by_registration(self, vcr_cassette) -> None:
        """Test searching by registration number."""
        async with TrademarkAssignmentClient() as client:
            results = await client.search_by_registration("6204399")
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_combined(self, vcr_cassette) -> None:
        """Test combined search criteria."""
        async with TrademarkAssignmentClient() as client:
            results = await client.search(assignee_name="Apple", limit=3)
            assert isinstance(results, list)
