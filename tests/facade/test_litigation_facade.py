"""Routing contract for the consolidated litigation facade dispatchers.

The facade tools hold no business logic — each branch forwards to an
existing per-forum function that is already tested for §5.9 envelope shape.
These tests pin the *routing*: that the right ``forum``/``ptab_type`` enum
value reaches the right underlying function with the right arguments, and
that the facade returns that function's result unchanged. The targets are
patched where the facade imports them (``...mcp.facade.litigation``), so no
upstream HTTP is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.facade.litigation import (
    get_litigation,
    search_litigation,
)

_MOD = "patent_client_agents.facade.litigation"


# ──────────────────────────────────────────────────────────────────────
# search_litigation — folds only the two free-text-query searches
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_litigation_routes_ptab_with_type():
    with patch(f"{_MOD}.search_ptab", new=AsyncMock(return_value="PTAB")) as m:
        out = await search_litigation(
            forum="ptab",
            query="q",
            limit=5,
            full=True,
            ptab_type="trial_decision",
        )
    assert out == "PTAB"
    m.assert_awaited_once_with(
        type="trial_decision", query="q", limit=5, full=True, offset=0, next_cursor=None
    )


@pytest.mark.asyncio
async def test_search_litigation_ptab_defaults_to_proceeding():
    with patch(f"{_MOD}.search_ptab", new=AsyncMock(return_value="PTAB")) as m:
        out = await search_litigation(forum="ptab", query="q")
    assert out == "PTAB"
    m.assert_awaited_once_with(
        type="proceeding", query="q", limit=25, full=False, offset=0, next_cursor=None
    )


@pytest.mark.asyncio
async def test_search_litigation_routes_cafc_with_patent_only():
    with patch(f"{_MOD}.search_cafc_opinions", new=AsyncMock(return_value="CAFC")) as m:
        out = await search_litigation(
            forum="cafc",
            query="q",
            limit=7,
            full=True,
            patent_only=True,
        )
    assert out == "CAFC"
    m.assert_awaited_once_with(
        query="q", patent_only=True, limit=7, full=True, offset=0, next_cursor=None
    )


# ──────────────────────────────────────────────────────────────────────
# get_litigation — three uniform identifier-in fetchers
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_litigation_routes_ptab_with_type():
    with patch(f"{_MOD}.get_ptab", new=AsyncMock(return_value="REC")) as m:
        out = await get_litigation(forum="ptab", identifier="IPR2024-00001", ptab_type="proceeding")
    assert out == "REC"
    m.assert_awaited_once_with(type="proceeding", identifier="IPR2024-00001")


@pytest.mark.asyncio
async def test_get_litigation_routes_usitc():
    with patch(f"{_MOD}.get_usitc_investigation", new=AsyncMock(return_value="REC")) as m:
        out = await get_litigation(forum="usitc", identifier="337-1234")
    assert out == "REC"
    m.assert_awaited_once_with(investigation_number="337-1234")


@pytest.mark.asyncio
async def test_get_litigation_routes_upc():
    with patch(f"{_MOD}.get_upc_decision", new=AsyncMock(return_value="REC")) as m:
        out = await get_litigation(forum="upc", identifier="UPC_CFI_1747/2025")
    assert out == "REC"
    m.assert_awaited_once_with(case_id="UPC_CFI_1747/2025")


@pytest.mark.asyncio
async def test_get_litigation_passes_list_identifier_through():
    ids = ["337-1234", "337-5678"]
    with patch(f"{_MOD}.get_usitc_investigation", new=AsyncMock(return_value="RECS")) as m:
        out = await get_litigation(forum="usitc", identifier=ids)
    assert out == "RECS"
    m.assert_awaited_once_with(investigation_number=ids)


# ──────────────────────────────────────────────────────────────────────
# Verbatim re-exposes are importable from the facade module (full schema
# preserved) — proves the standalone surface is wired, not dropped.
# ──────────────────────────────────────────────────────────────────────


def test_verbatim_reexposes_are_importable():
    from patent_client_agents.facade import litigation

    for name in (
        "search_cafc_patent_opinions",
        "search_usitc_investigations",
        "search_usitc_documents",
        "search_upc_decisions",
        "list_ptab_children",
        "list_usitc_attachments",
    ):
        assert callable(getattr(litigation, name))


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real per-source function → §5.9 envelope. Proves the
# envelope contract survives the dispatch (not just that routing is wired).
# ──────────────────────────────────────────────────────────────────────


class _FakePtabSearchResponse:
    def __init__(self, count, bag):
        self._count = count
        self._bag = bag

    def model_dump(self):
        return {"count": self._count, "patentTrialProceedingDataBag": self._bag}


@pytest.mark.asyncio
async def test_search_litigation_ptab_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance

    fake = _FakePtabSearchResponse(
        count=42,
        bag=[{"trialNumber": "IPR2024-00001", "proceedingStatusCategory": "Instituted"}],
    )
    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_trial_proceedings = AsyncMock(return_value=fake)
        out = await search_litigation(forum="ptab", query="patent owner:Acme", limit=1)

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "USPTO Open Data Portal"
    assert "/api/v1/ptab/proceedings/search" in out.provenance.source_url
    assert len(out.items) == 1
    assert out.more_available is True  # 42 total, 1 shown


@pytest.mark.asyncio
@pytest.mark.parametrize("pagination", [{"offset": 25}, {"next_cursor": "opaque-token"}])
async def test_search_litigation_forwards_cafc_pagination(pagination):
    with patch(f"{_MOD}.search_cafc_opinions", new=AsyncMock()) as source:
        await search_litigation(forum="cafc", query="q", **pagination)
    assert source.await_args is not None
    assert source.await_args.kwargs["offset"] == pagination.get("offset", 0)
    assert source.await_args.kwargs["next_cursor"] == pagination.get("next_cursor")


@pytest.mark.asyncio
async def test_search_litigation_ptab_continues_to_last_page():
    responses = [
        _FakePtabSearchResponse(2, [{"trialNumber": "IPR2024-00001"}]),
        _FakePtabSearchResponse(2, [{"trialNumber": "IPR2024-00002"}]),
    ]
    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search_trial_proceedings = AsyncMock(side_effect=responses)
        first = await search_litigation(forum="ptab", query="Acme", limit=1)
        last = await search_litigation(forum="ptab", query="Acme", next_cursor=first.next_cursor)

    assert first.more_available is True
    assert first.next_cursor is not None
    assert last.items[0]["trial_number"] == "IPR2024-00002"
    assert last.more_available is False
    assert last.next_cursor is None
    client.search_trial_proceedings.assert_awaited_with(query="Acme", limit=1, offset=1)


@pytest.mark.asyncio
async def test_search_litigation_ptab_forwards_offset():
    with patch(f"{_MOD}.search_ptab", new=AsyncMock()) as source:
        await search_litigation(forum="ptab", query="q", offset=25)
    assert source.await_args is not None
    assert source.await_args.kwargs["offset"] == 25


@pytest.mark.asyncio
async def test_search_litigation_schema_exposes_continuation():
    from patent_client_agents.facade.litigation import litigation_facade_mcp

    tool = next(
        tool
        for tool in await litigation_facade_mcp.list_tools()
        if tool.name == "search_litigation"
    )
    properties = tool.parameters["properties"]
    assert properties["offset"]["default"] == 0
    assert properties["next_cursor"]["default"] is None
