"""Routing contract for the classification, fees & copyright facade dispatchers.

The facade tools hold no business logic — each branch forwards to an existing
per-source function that is already tested for §5.9 envelope shape. These
tests pin the *routing*: that the right ``mode`` enum value reaches the right
underlying function with the right arguments, and that the facade returns that
function's result unchanged. The targets are patched where the facade imports
them (``...mcp.facade.reference``), so no upstream HTTP is touched.

One end-to-end test mocks the upstream CopyrightClient and asserts a real §5.9
``ListEnvelope`` comes back through the facade — proving the envelope contract
survives the dispatch, not just that routing is wired.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.facade.reference import (
    classify_cpc,
    copyright,
    get_fees,
)

_MOD = "patent_client_agents.facade.reference"


# ──────────────────────────────────────────────────────────────────────
# classify_cpc — mode = search · lookup · map
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_classify_cpc_routes_search():
    with patch(f"{_MOD}.search_cpc", new=AsyncMock(return_value="SEARCH")) as m:
        out = await classify_cpc(mode="search", query="machine learning", range_end=5, full=True)
    assert out == "SEARCH"
    m.assert_awaited_once_with(query="machine learning", range_begin=1, range_end=5, full=True)


@pytest.mark.asyncio
async def test_classify_cpc_routes_lookup():
    with patch(f"{_MOD}.lookup_cpc", new=AsyncMock(return_value="LOOKUP")) as m:
        out = await classify_cpc(mode="lookup", symbol="H04L9/32")
    assert out == "LOOKUP"
    m.assert_awaited_once_with(symbol="H04L9/32")


@pytest.mark.asyncio
async def test_classify_cpc_routes_map():
    with patch(f"{_MOD}.map_cpc_classification", new=AsyncMock(return_value="MAP")) as m:
        out = await classify_cpc(mode="map", symbol="H04L9/32", from_scheme="cpc", to_scheme="ipc")
    assert out == "MAP"
    m.assert_awaited_once_with(symbol="H04L9/32", from_scheme="cpc", to_scheme="ipc")


@pytest.mark.asyncio
async def test_classify_cpc_lookup_requires_symbol():
    with pytest.raises(ValueError, match="symbol"):
        await classify_cpc(mode="lookup")


@pytest.mark.asyncio
async def test_classify_cpc_search_requires_query():
    with pytest.raises(ValueError, match="query"):
        await classify_cpc(mode="search")


# ──────────────────────────────────────────────────────────────────────
# get_fees — mode = schedule · lookup · jurisdictions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_fees_routes_schedule():
    with patch(f"{_MOD}.get_fee_schedule", new=AsyncMock(return_value="SCHED")) as m:
        out = await get_fees(mode="schedule", jurisdiction="USPTO", right="trademark")
    assert out == "SCHED"
    m.assert_awaited_once_with(jurisdiction="USPTO", right="trademark")


@pytest.mark.asyncio
async def test_get_fees_routes_lookup():
    with patch(f"{_MOD}.lookup_fee", new=AsyncMock(return_value="FEE")) as m:
        out = await get_fees(
            mode="lookup", jurisdiction="EPO", category="renewal", tier="small", year=10
        )
    assert out == "FEE"
    m.assert_awaited_once_with(
        jurisdiction="EPO", category="renewal", tier="small", year=10, right="patent"
    )


@pytest.mark.asyncio
async def test_get_fees_routes_jurisdictions():
    with patch(f"{_MOD}.list_fee_jurisdictions", new=AsyncMock(return_value="JX")) as m:
        out = await get_fees(mode="jurisdictions")
    assert out == "JX"
    m.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_fees_schedule_requires_jurisdiction():
    with pytest.raises(ValueError, match="jurisdiction"):
        await get_fees(mode="schedule")


@pytest.mark.asyncio
async def test_get_fees_lookup_requires_jurisdiction():
    with pytest.raises(ValueError, match="jurisdiction"):
        await get_fees(mode="lookup")


# ──────────────────────────────────────────────────────────────────────
# copyright — mode = search · get
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_copyright_routes_search():
    with patch(f"{_MOD}.search_copyright", new=AsyncMock(return_value="CSEARCH")) as m:
        out = await copyright(mode="search", query="moby dick", field="title", page=2)
    assert out == "CSEARCH"
    m.assert_awaited_once_with(query="moby dick", field="title", page=2, page_size=10, full=False)


@pytest.mark.asyncio
async def test_copyright_routes_get_single():
    with patch(f"{_MOD}.get_copyright_record", new=AsyncMock(return_value="CGET")) as m:
        out = await copyright(mode="get", public_records_id="voyager_12345")
    assert out == "CGET"
    m.assert_awaited_once_with(public_records_id="voyager_12345")


@pytest.mark.asyncio
async def test_copyright_routes_get_list():
    ids = ["voyager_1", "voyager_2"]
    with patch(f"{_MOD}.get_copyright_record", new=AsyncMock(return_value="CGETS")) as m:
        out = await copyright(mode="get", public_records_id=ids)
    assert out == "CGETS"
    m.assert_awaited_once_with(public_records_id=ids)


@pytest.mark.asyncio
async def test_copyright_get_requires_public_records_id():
    with pytest.raises(ValueError, match="public_records_id"):
        await copyright(mode="get")


@pytest.mark.asyncio
async def test_copyright_search_requires_query():
    with pytest.raises(ValueError, match="query"):
        await copyright(mode="search")


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real search_copyright → §5.9 envelope. Proves the
# envelope contract survives the dispatch (not just that routing is wired).
# ──────────────────────────────────────────────────────────────────────


class _FakeModel:
    def __init__(self, payload):
        self._payload = payload

    def model_dump(self):
        return self._payload


class _FakeSearchResponse:
    def __init__(self, hit_count, records):
        self.metadata = _FakeModel({"hit_count": hit_count})
        self.records = [_FakeModel(r) for r in records]


@pytest.mark.asyncio
async def test_copyright_search_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance

    fake = _FakeSearchResponse(
        hit_count=42,
        records=[
            {
                "public_records_id": "voyager_12345",
                "title_of_work": ["Test Work"],
                "copyright_number_for_display": "TX0001234567",
                "type_of_record": "registration",
            }
        ],
    )
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search = AsyncMock(return_value=fake)
        out = await copyright(mode="search", query="test", page_size=1)

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "U.S. Copyright Office — Public Records"
    assert len(out.items) == 1
    assert out.items[0]["public_records_id"] == "voyager_12345"
    assert out.more_available is True  # 42 total, 1 shown


@pytest.mark.asyncio
async def test_fee_refresh_forwarding():
    with patch(
        "patent_client_agents.facade.reference.get_fee_schedule",
        new=AsyncMock(return_value="SCHEDULE"),
    ) as mocked:
        await get_fees(mode="schedule", jurisdiction="USPTO", refresh=True)
    mocked.assert_awaited_once_with(jurisdiction="USPTO", right="patent", refresh=True)
    with pytest.raises(ValueError, match="requires mode"):
        await get_fees(mode="jurisdictions", refresh=True)
