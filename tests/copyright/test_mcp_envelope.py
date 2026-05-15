"""Envelope-shape tests for the migrated Copyright MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.5 (lean default +
``full=True`` opt-in), §5.4 (list-accepting ``get_*``), §5.6
(cross-references in docstrings), and the §5.4 invariant that no
``batch_*`` tool exists.

Mocks ``CopyrightClient`` at the boundary.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.copyright import (
    CopyrightRecord,
    Histogram,
    SearchMetadata,
    SearchResponse,
)
from patent_client_agents.mcp.tools.copyright import (
    get_copyright_record,
    search_copyright,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes
# ──────────────────────────────────────────────────────────────────────


def _make_record(
    prid: str,
    *,
    title: str = "TEST WORK",
    reg: str = "TX 1234567",
    claimant: str = "Test Claimant LLC",
    rclass: str = "TX",
) -> CopyrightRecord:
    return CopyrightRecord(
        public_records_id=prid,
        title_of_work=[title],
        registration_number=[reg],
        copyright_number_for_display=reg,
        type_of_record="registration",
        registration_status="published",
        registration_class=[rclass],
        claimant=[claimant],
        claimants=[],
        publisher_name=[],
        type_of_work="text",
        all_type_of_work=["text"],
        system_of_origin="voyager",
        application_date=["2020-01-15"],
        first_published_date=["2020-01-10"],
        fee_date=["2020-01-15"],
        deposit_received_date=["2020-01-20"],
        representative_date="2020-01-15",
        link_to_image_url=[],
        score=10.0,
    )


def _make_search_response(records: list[CopyrightRecord], *, hit_count: int = 0) -> SearchResponse:
    return SearchResponse(
        metadata=SearchMetadata(hit_count=hit_count or len(records), query="test"),
        histogram=Histogram(),
        records=records,
    )


# ──────────────────────────────────────────────────────────────────────
# search_copyright — §5.9 envelope, §5.5 lean default
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_copyright_returns_lean_list_envelope_by_default():
    response = _make_search_response(
        [
            _make_record("voyager_111", title="ALPHA"),
            _make_record("voyager_222", title="BETA"),
        ],
        hit_count=2,
    )
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=response)

        result = await search_copyright(query="ALPHA")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert len(result.items) == 2
    # Lean projection — exactly the chosen scalar fields, nothing more.
    assert set(result.items[0].keys()) == {
        "public_records_id",
        "title",
        "registration_number",
        "registration_class",
        "type_of_record",
        "type_of_work",
        "claimant",
        "representative_date",
    }
    assert result.items[0]["public_records_id"] == "voyager_111"
    assert result.items[0]["title"] == "ALPHA"
    assert result.items[0]["registration_number"] == "TX 1234567"
    # Summary contains identifying text from the query.
    assert "ALPHA" in result.summary


@pytest.mark.asyncio
async def test_search_copyright_full_true_returns_upstream_shape():
    response = _make_search_response([_make_record("voyager_111")], hit_count=1)
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=response)

        result = await search_copyright(query="anything", full=True)

    # Full mode preserves the upstream model_dump shape (list-valued
    # fields like title_of_work, claimant, etc.).
    item = result.items[0]
    assert item["title_of_work"] == ["TEST WORK"]
    assert item["claimant"] == ["Test Claimant LLC"]
    assert "score" in item


@pytest.mark.asyncio
async def test_search_copyright_provenance_source_name():
    response = _make_search_response([], hit_count=0)
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=response)

        result = await search_copyright(query="zzz")

    assert result.provenance.source_name == "U.S. Copyright Office — Public Records"
    assert "publicrecords.copyright.gov" in result.provenance.source_url
    assert "/simple_search_dsl" in result.provenance.source_url


@pytest.mark.asyncio
async def test_search_copyright_more_available_when_total_exceeds_page():
    # 20 hits total, page_size=10, page=1 → more_available True.
    response = _make_search_response(
        [_make_record(f"voyager_{i}") for i in range(10)], hit_count=20
    )
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=response)

        result = await search_copyright(query="q", page=1, page_size=10)

    assert result.more_available is True


# ──────────────────────────────────────────────────────────────────────
# get_copyright_record — §5.4 list-accepting, §5.9 envelope
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_copyright_record_accepts_single_string():
    record = _make_record("voyager_42", title="SOLO WORK")
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_record = AsyncMock(return_value=record)

        result = await get_copyright_record(public_records_id="voyager_42")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["public_records_id"] == "voyager_42"
    # Summary should contain the identifier and title.
    assert "voyager_42" in result.summary
    assert "SOLO WORK" in result.summary


@pytest.mark.asyncio
async def test_get_copyright_record_accepts_list_and_preserves_order():
    ids = ["voyager_a", "voyager_b", "voyager_c"]
    records = [_make_record(i) for i in ids]
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_record = AsyncMock(side_effect=records)

        result = await get_copyright_record(public_records_id=ids)

    assert isinstance(result, ListEnvelope)
    assert [r["public_records_id"] for r in result.items] == ids
    assert "3 of 3" in result.summary


@pytest.mark.asyncio
async def test_get_copyright_record_handles_not_found():
    with patch("patent_client_agents.mcp.tools.copyright.CopyrightClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_record = AsyncMock(return_value=None)

        result = await get_copyright_record(public_records_id="voyager_missing")

    assert isinstance(result, ListEnvelope)
    assert result.items == []
    assert "not found" in result.summary
    assert result.provenance.source_name == "U.S. Copyright Office — Public Records"


# ──────────────────────────────────────────────────────────────────────
# §5.4 invariant — no batch_* tool
# ──────────────────────────────────────────────────────────────────────


def test_no_batch_tool_present():
    """§5.4 forbids ``batch_*`` siblings; the get_* tool list-accepts instead."""
    from patent_client_agents.mcp.tools import copyright as cp_module

    batch_attrs = [name for name in dir(cp_module) if name.startswith("batch_")]
    assert batch_attrs == []
