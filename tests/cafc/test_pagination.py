"""Behavioral checks for bounded CAFC traversal and honest date filtering."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import decode_cursor, encode_cursor
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.cafc.client import CAFCClient, CAFCError
from patent_client_agents.cafc.models import CAFCOpinion
from patent_client_agents.mcp.tools.cafc import search_cafc_opinions, search_cafc_patent_opinions


def row(number="2026-1000"):
    return ["09/01/2026", number, "PTO", "OPINION", "Acme v. Widget", "Precedential", "a.pdf"]


@pytest.mark.asyncio
async def test_client_caps_fetch_and_starts_at_offset():
    client = CAFCClient()
    client._fetch_page = AsyncMock(return_value={"data": [row("second")], "recordsFiltered": 2})
    assert [o.appeal_number for o in await client.search(max_results=1, offset=1)] == ["second"]
    assert client._fetch_page.call_args.kwargs["length"] == 1
    assert client._fetch_page.call_args.kwargs["start"] == 1
    await client.close()


@pytest.mark.asyncio
async def test_client_continues_short_page_when_count_says_more():
    client = CAFCClient()
    client._fetch_page = AsyncMock(
        side_effect=[
            {"data": [row("first")], "recordsFiltered": 2},
            {"data": [row("second")], "recordsFiltered": 2},
        ]
    )
    assert len(await client.search(max_results=3)) == 2
    assert client._fetch_page.call_args.kwargs["start"] == 1
    assert client._fetch_page.call_args.kwargs["length"] == 2
    await client.close()


@pytest.mark.asyncio
async def test_client_uses_filtered_total_not_global_total():
    client = CAFCClient()
    client._fetch_page = AsyncMock(
        return_value={"data": [row()], "recordsFiltered": 1, "recordsTotal": 999}
    )
    assert len(await client.search()) == 1
    assert client._fetch_page.await_count == 1
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": None},
        {"data": [], "error": "source failed"},
        {"data": [[]]},
        {"data": ["bad"]},
        {"data": [], "recordsFiltered": 1},
        {"data": [row()], "recordsFiltered": 0},
        {"data": [], "recordsFiltered": "bad"},
        {"data": [], "recordsFiltered": True},
        {"data": [row()], "recordsFiltered": 2, "recordsTotal": 1},
        {"data": [row(), row()]},
    ],
)
async def test_client_rejects_malformed_or_contradictory_page(payload):
    client = CAFCClient()
    client._fetch_page = AsyncMock(return_value=payload)
    with pytest.raises(CAFCError):
        await client.search(max_results=1)
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_results": 0},
        {"max_results": -1},
        {"max_results": True},
        {"offset": -1},
        {"offset": True},
        {"date_to": date(2026, 1, 1)},
        {"date_from": date(2026, 2, 1), "date_to": date(2026, 1, 1)},
    ],
)
async def test_client_rejects_invalid_bounds_before_fetch(kwargs):
    client = CAFCClient()
    client._fetch_page = AsyncMock()
    with pytest.raises(ValidationError):
        await client.search(**kwargs)
    client._fetch_page.assert_not_awaited()
    await client.close()


@pytest.mark.asyncio
async def test_date_range_and_origin_forwarded():
    client = CAFCClient()
    client._fetch_page = AsyncMock(return_value={"data": [], "recordsFiltered": 0})
    await client.search_patent_opinions(
        date_from=date(2026, 1, 1), date_to=date(2026, 2, 1), max_results=4, offset=3
    )
    args = client._fetch_page.call_args.kwargs
    assert args["date_from"] == date(2026, 1, 1)
    assert args["date_to"] == date(2026, 2, 1)
    assert args["origins"] == ["PTO", "DCT", "ITC", "CFC"]
    assert args["start"] == 3
    form = client._build_form_data(**args)
    assert form["columns[0][search][value]"] == "01/01/2026|02/01/2026"
    await client.close()


@pytest.mark.asyncio
async def test_classifier_empty_page_keeps_source_continuation():
    rows = [CAFCOpinion(appeal_number=str(i), case_name="Ordinary v. Person") for i in range(3)]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search = AsyncMock(return_value=rows)
        first = await search_cafc_opinions(query="x", patent_only=True, limit=2)
        assert first.items == []
        assert first.more_available
        assert decode_cursor(first.next_cursor) == {"offset": 2, "limit": 2}
        assert "heuristic" in first.summary
        client.search = AsyncMock(return_value=[])
        last = await search_cafc_opinions(
            query="x", patent_only=True, next_cursor=first.next_cursor
        )
        client.search.assert_awaited_once_with(query="x", max_results=3, offset=2)
        assert not last.more_available and last.next_cursor is None


@pytest.mark.asyncio
async def test_origin_search_caps_items_and_consumes_cursor():
    rows = [CAFCOpinion(appeal_number=str(i), case_name="Case") for i in range(3)]
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_patent_opinions = AsyncMock(return_value=rows)
        first = await search_cafc_patent_opinions(max_results=2)
        assert len(first.items) == 2
        assert first.more_available
        assert decode_cursor(first.next_cursor) == {"offset": 2, "limit": 2}
        client.search_patent_opinions = AsyncMock(return_value=rows[:2])
        last = await search_cafc_patent_opinions(next_cursor=first.next_cursor)
        client.search_patent_opinions.assert_awaited_once_with(
            date_from=None, date_to=None, max_results=3, offset=2
        )
        assert len(last.items) == 2
        assert not last.more_available


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"next_cursor": "!"},
        {"next_cursor": encode_cursor({"offset": 0})},
        {"next_cursor": encode_cursor({"offset": True, "limit": 2})},
        {"next_cursor": encode_cursor({"offset": 0, "limit": -1})},
    ],
)
async def test_invalid_mcp_pagination_rejected_before_session(kwargs):
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as cls:
        with pytest.raises(ValidationError):
            await search_cafc_opinions(**kwargs)
        cls.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {"date_to": "2026-01-01"},
        {"date_from": "2026-02-01", "date_to": "2026-01-01"},
        {"date_from": "not-a-date"},
        {"date_from": ""},
        {"date_to": ""},
    ],
)
async def test_invalid_dates_rejected_before_session(kwargs):
    with patch("patent_client_agents.mcp.tools.cafc.CAFCClient") as cls:
        with pytest.raises(ValidationError):
            await search_cafc_patent_opinions(**kwargs)
        cls.assert_not_called()


@pytest.mark.asyncio
async def test_captured_live_response_accepts_string_counts():
    payload = json.loads((Path(__file__).parent / "fixtures" / "opinions_2024_01.json").read_text())
    client = CAFCClient()
    client._fetch_page = AsyncMock(return_value=payload)
    opinions = await client.search(
        max_results=1, date_from=date(2024, 1, 1), date_to=date(2024, 1, 31)
    )
    assert opinions[0].appeal_number == "23-1822"
    assert opinions[0].release_date == date(2024, 1, 31)
    await client.close()
