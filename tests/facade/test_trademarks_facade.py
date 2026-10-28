"""Routing contract for the consolidated Trademarks facade dispatchers.

The facade tools hold no business logic — each branch forwards to an
existing per-source function that is already tested for §5.9 envelope
shape. These tests pin the *routing*: that the right ``search_by``/``view``
enum value reaches the right underlying function with the right arguments,
and that the facade returns that function's result unchanged. The targets are
patched where the facade imports them (``...mcp.facade.trademarks``), so no
upstream HTTP is touched. One end-to-end test mocks the upstream client and
asserts a real §5.9 ``ListEnvelope`` with ``Provenance`` survives the dispatch.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.facade.trademarks import (
    get_trademark,
    search_trademarks,
)

_MOD = "patent_client_agents.facade.trademarks"


# ──────────────────────────────────────────────────────────────────────
# search_trademarks — forwards to the TESS search verbatim
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_trademarks_forwards_all_args():
    with patch(f"{_MOD}._search_trademarks", new=AsyncMock(return_value="TM")) as m:
        out = await search_trademarks(
            query="APPLE",
            search_by="owner",
            paginate_all=True,
            max_results=50,
            full=True,
        )
    assert out == "TM"
    m.assert_awaited_once_with(
        query="APPLE",
        search_by="owner",
        paginate_all=True,
        max_results=50,
        full=True,
    )


@pytest.mark.asyncio
async def test_search_trademarks_defaults():
    with patch(f"{_MOD}._search_trademarks", new=AsyncMock(return_value="TM")) as m:
        out = await search_trademarks(query="NEURAL")
    assert out == "TM"
    m.assert_awaited_once_with(
        query="NEURAL",
        search_by="wordmark",
        paginate_all=False,
        max_results=500,
        full=False,
    )


# ──────────────────────────────────────────────────────────────────────
# get_trademark — view dispatch across TESS + TSDR facets
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("view", "target"),
    [
        ("record", "_get_trademark"),
        ("status", "get_trademark_status"),
        ("last_update", "get_trademark_last_update"),
    ],
)
async def test_get_trademark_routes_each_view(view, target):
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="REC")) as m:
        out = await get_trademark(identifier="97123456", view=view)
    assert out == "REC"
    m.assert_awaited_once_with("97123456")


@pytest.mark.asyncio
async def test_get_trademark_record_is_default():
    with patch(f"{_MOD}._get_trademark", new=AsyncMock(return_value="REC")) as m:
        out = await get_trademark(identifier="97123456")
    assert out == "REC"
    m.assert_awaited_once_with("97123456")


@pytest.mark.asyncio
async def test_get_trademark_passes_list_identifier_through():
    ids = ["97123456", "97654321"]
    with patch(f"{_MOD}._get_trademark", new=AsyncMock(return_value="RECS")) as m:
        out = await get_trademark(identifier=ids, view="record")
    assert out == "RECS"
    m.assert_awaited_once_with(ids)


@pytest.mark.asyncio
async def test_get_trademark_documents_routes_single_serial():
    with patch(f"{_MOD}.get_trademark_documents", new=AsyncMock(return_value="DOCS")) as m:
        out = await get_trademark(identifier="97123456", view="documents")
    assert out == "DOCS"
    m.assert_awaited_once_with("97123456")


@pytest.mark.asyncio
async def test_get_trademark_documents_rejects_list():
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await get_trademark(identifier=["97123456", "97654321"], view="documents")


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real per-source function → §5.9 envelope. Proves the
# envelope contract survives the dispatch (not just that routing is wired).
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_trademarks_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance
    from patent_client_agents.uspto_tmsearch.models import (
        TrademarkSearchResponse,
        TrademarkSearchResult,
    )

    response = TrademarkSearchResponse(
        total=1,
        results=[
            TrademarkSearchResult.model_validate(
                {
                    "serialNumber": "97123456",
                    "wordmark": "TESTMARK",
                    "alive": True,
                    "ownerName": ["Test Co"],
                }
            )
        ],
    )
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search = AsyncMock(return_value=response)
        out = await search_trademarks(query="TESTMARK", search_by="wordmark")

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "USPTO Trademark Search (TESS)"
    assert "/prod-stage-v1-0-0/tmsearch" in out.provenance.source_url
    assert len(out.items) == 1
    assert out.items[0]["wordmark"] == "TESTMARK"
