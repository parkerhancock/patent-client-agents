"""Tests for server-side date filtering in search_usitc_documents MCP tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.mcp.tools.usitc import _parse_edis_date, search_usitc_documents
from patent_client_agents.usitc.models import EdisDocument


class TestParseEdisDate:
    """Tests for _parse_edis_date helper."""

    def test_standard_format(self) -> None:
        assert _parse_edis_date("2024-06-15 00:00:00.0") == "2024-06-15"

    def test_date_only(self) -> None:
        assert _parse_edis_date("2024-06-15") == "2024-06-15"

    def test_none(self) -> None:
        assert _parse_edis_date(None) is None

    def test_empty_string(self) -> None:
        assert _parse_edis_date("") is None

    def test_short_string(self) -> None:
        assert _parse_edis_date("2024") is None

    def test_slash_format(self) -> None:
        """EDIS production uses forward slashes: '2024/05/16 00:00:00'."""
        assert _parse_edis_date("2024/05/16 00:00:00") == "2024-05-16"

    def test_slash_date_only(self) -> None:
        assert _parse_edis_date("2024/05/16") == "2024-05-16"


def _doc(doc_id: int, title: str, date: str | None) -> EdisDocument:
    payload: dict = {
        "id": doc_id,
        "documentTitle": title,
        "documentType": "Order",
        "investigationNumber": "337-1234",
        "securityLevel": "Public",
    }
    if date is not None:
        payload["documentDate"] = date
    return EdisDocument(**payload)


async def _search(docs: list[EdisDocument], **kwargs) -> tuple[list, AsyncMock]:
    """Run ``search_usitc_documents`` against an EDIS client that serves
    ``docs`` on page 1 and an empty page 2."""
    with patch("patent_client_agents.mcp.tools.usitc.EdisClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.list_documents = AsyncMock(side_effect=[docs, []])
        result = await search_usitc_documents(investigation_number="337-1234", **kwargs)
    return result, mock_client.list_documents


class TestSearchUsitcDocumentsDateFiltering:
    """Tests for the date filtering in ``search_usitc_documents``."""

    @pytest.mark.asyncio
    async def test_date_from_filters_older_docs(self) -> None:
        """Documents before date_from should be excluded."""
        docs = [
            _doc(1, "Old", "2023-06-01 00:00:00.0"),
            _doc(2, "New", "2024-06-01 00:00:00.0"),
            _doc(3, "Newer", "2024/09/15 00:00:00"),
        ]

        result, list_documents = await _search(docs, date_from="2024-01-01")

        assert [item["id"] for item in result.items] == [2, 3]
        assert "2 of 2 matched" in result.summary
        assert result.more_available is False
        # Date filtering pages through EDIS until an empty page.
        assert list_documents.await_count == 2
        assert list_documents.await_args_list[0].kwargs == {
            "investigationNumber": "337-1234",
            "pageNumber": 1,
        }

    @pytest.mark.asyncio
    async def test_date_to_filters_newer_docs(self) -> None:
        """Documents after date_to should be excluded."""
        docs = [
            _doc(1, "Old", "2023-06-01 00:00:00.0"),
            _doc(2, "New", "2024-06-01 00:00:00.0"),
            _doc(3, "Newer", "2024-09-15 00:00:00.0"),
        ]

        result, _ = await _search(docs, date_to="2024-06-30")

        assert [item["id"] for item in result.items] == [1, 2]
        assert [item["title"] for item in result.items] == ["Old", "New"]

    @pytest.mark.asyncio
    async def test_date_range_filters_both(self) -> None:
        """Both date_from and date_to should be applied."""
        docs = [
            _doc(1, "Too Old", "2023-06-01 00:00:00.0"),
            _doc(2, "In Range", "2024-03-15 00:00:00.0"),
            _doc(3, "Too New", "2024-09-15 00:00:00.0"),
        ]

        result, _ = await _search(docs, date_from="2024-01-01", date_to="2024-06-30")

        assert [item["id"] for item in result.items] == [2]
        assert result.summary == (
            "USITC documents — page 1: 1 of 1 matched "
            "(date_from='2024-01-01', date_to='2024-06-30')."
        )

    @pytest.mark.asyncio
    async def test_null_dates_excluded(self) -> None:
        """Documents with no document_date should be excluded when filtering."""
        docs = [
            _doc(1, "No Date", None),
            _doc(2, "Has Date", "2024-06-01 00:00:00.0"),
        ]

        result, _ = await _search(docs, date_from="2024-01-01")

        assert [item["id"] for item in result.items] == [2]

    @pytest.mark.asyncio
    async def test_boundary_dates_inclusive(self) -> None:
        """date_from and date_to should be inclusive."""
        docs = [
            _doc(1, "Before", "2023-12-31 00:00:00.0"),
            _doc(2, "Start", "2024-01-01 00:00:00.0"),
            _doc(3, "End", "2024-12-31 00:00:00.0"),
            _doc(4, "After", "2025-01-01 00:00:00.0"),
        ]

        result, _ = await _search(docs, date_from="2024-01-01", date_to="2024-12-31")

        assert [item["id"] for item in result.items] == [2, 3]
