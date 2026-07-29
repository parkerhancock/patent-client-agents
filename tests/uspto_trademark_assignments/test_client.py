"""Tests for USPTO Trademark Assignment client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient


def _search_response(data: list[dict]) -> httpx.Response:
    return httpx.Response(
        200,
        request=httpx.Request(
            "POST",
            "https://assignmentcenter.uspto.gov/ipas/search/api/v3/public/search/trademark",
        ),
        json={
            "status": "Success",
            "statusCode": 200,
            "error": None,
            "successResponse": {
                "data": data,
                "totalRows": len(data),
                "filteredRowsCount": len(data),
                "backendPagination": False,
                "message": "",
            },
        },
    )


def _assignment(reel_number: int) -> dict:
    return {
        "reelNumber": reel_number,
        "frameNumber": "0093",
        "assignors": [],
        "assignees": ["APPLE INC."],
        "noOfProperties": 0,
        "properties": [],
    }


class TestTrademarkAssignmentClient:
    """Tests for TrademarkAssignmentClient."""

    def test_default_base_url(self) -> None:
        """Test default base URL is set correctly."""
        client = TrademarkAssignmentClient.__new__(TrademarkAssignmentClient)
        assert client.DEFAULT_BASE_URL == "https://assignmentcenter.uspto.gov"

    @pytest.mark.asyncio
    async def test_search_uses_v3_advanced_endpoint_and_schema(self) -> None:
        """The retired v2 export endpoint must not be used for searches."""
        response = _search_response([_assignment(9006)])

        async with TrademarkAssignmentClient() as client:
            with patch.object(client, "_request", AsyncMock(return_value=response)) as request:
                records = await client.search(assignee_name="Apple", serial_number="88874668")

        assert [record.reel_number for record in records] == [9006]
        request.assert_awaited_once_with(
            "POST",
            "/ipas/search/api/v3/public/search/trademark",
            json={
                "searchCriteria": [
                    {
                        "property": "Apple",
                        "searchBy": "assigneeName",
                        "matchType": "Contains",
                        "order": 1,
                        "relation": "",
                    },
                    {
                        "property": "88874668",
                        "searchBy": "serialNumber",
                        "matchType": "Exact",
                        "order": 2,
                        "relation": "AND",
                    },
                ],
                "dataFilter": {
                    "filterBy": [],
                    "rowsPerPage": 1000,
                    "currentPage": 1,
                },
            },
            context="Trademark assignment search",
            timeout=60.0,
        )

    @pytest.mark.asyncio
    async def test_search_applies_requested_window_to_unpaginated_response(self) -> None:
        """The v3 public API returns all rows, so the client slices locally."""
        response = _search_response([_assignment(1), _assignment(2), _assignment(3)])

        async with TrademarkAssignmentClient() as client:
            with patch.object(client, "_request", AsyncMock(return_value=response)):
                records = await client.search(assignee_name="Apple", start_row=2, limit=1)

        assert [record.reel_number for record in records] == [2]


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
