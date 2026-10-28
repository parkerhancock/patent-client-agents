"""Routing contract for the consolidated EPO facade dispatchers.

The facade tools hold no business logic — each branch forwards to an
existing per-source function that is already tested for §5.9 envelope
shape (see the EPO OPS tests). These tests pin the *routing*: that the
right ``view`` enum value reaches the right underlying function with the
right argument, and that the facade returns that function's result
unchanged. The targets are patched where the facade imports them
(``...mcp.facade.epo``), so no upstream HTTP is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_data_core.exceptions import ValidationError
from patent_client_agents.facade.epo import epo_facade_mcp, get_epo

_MOD = "patent_client_agents.facade.epo"


# ──────────────────────────────────────────────────────────────────────
# get_epo — uniform identifier-in across all five views
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("view", "target"),
    [
        ("biblio", "get_epo_biblio"),
        ("citations", "get_epo_citations"),
        ("equivalents", "get_epo_equivalents"),
        ("family", "get_epo_family"),
        ("family_intelligence", "get_epo_family_intelligence"),
        ("fulltext", "get_epo_fulltext"),
        ("legal_events", "get_epo_legal_events"),
        ("procedural_steps", "get_epo_procedural_steps"),
        ("register_biblio", "get_epo_register_biblio"),
        ("register_events", "get_epo_register_events"),
        ("unitary_status", "get_epo_unitary_patent_status"),
    ],
)
async def test_get_epo_routes_each_view(view, target):
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="REC")) as m:
        out = await get_epo(view=view, identifier="EP1234567A1")
    assert out == "REC"
    m.assert_awaited_once_with("EP1234567A1")


@pytest.mark.asyncio
async def test_get_epo_passes_list_identifier_through():
    ids = ["EP1234567A1", "US10123456B2"]
    with patch(f"{_MOD}.get_epo_biblio", new=AsyncMock(return_value="RECS")) as m:
        out = await get_epo(view="biblio", identifier=ids)
    assert out == "RECS"
    m.assert_awaited_once_with(ids)


@pytest.mark.asyncio
async def test_get_epo_rejects_list_for_unitary_status():
    with pytest.raises(ValidationError, match="requires a single EP publication number"):
        await get_epo(view="unitary_status", identifier=["EP4108782B1"])


@pytest.mark.asyncio
async def test_get_epo_rejects_list_for_family_intelligence():
    with pytest.raises(ValidationError, match="requires a single publication number"):
        await get_epo(view="family_intelligence", identifier=["EP4108782B1"])


@pytest.mark.asyncio
async def test_get_epo_passes_list_to_register_biblio():
    ids = ["EP1000000", "EP4108782"]
    with patch(f"{_MOD}.get_epo_register_biblio", new=AsyncMock(return_value="RECS")) as m:
        out = await get_epo(view="register_biblio", identifier=ids)
    assert out == "RECS"
    m.assert_awaited_once_with(ids)


@pytest.mark.asyncio
async def test_get_epo_schema_exposes_all_supported_views():
    tools = {tool.name: tool for tool in await epo_facade_mcp.list_tools()}
    view_schema = tools["get_epo"].parameters["properties"]["view"]
    assert set(view_schema["enum"]) == {
        "biblio",
        "citations",
        "equivalents",
        "family",
        "family_intelligence",
        "fulltext",
        "legal_events",
        "procedural_steps",
        "register_biblio",
        "register_events",
        "unitary_status",
    }
    assert "one or more EP publications" in view_schema["description"]


# ──────────────────────────────────────────────────────────────────────
# search_epo — re-exposed verbatim. Importing it off the facade module
# proves it is registered there (the one-liner ran at import time).
# ──────────────────────────────────────────────────────────────────────


def test_search_epo_reexposed_on_facade():
    from patent_client_agents.facade import epo as facade
    from patent_client_agents.mcp.tools.epo_ops import search_epo as upstream

    assert facade.search_epo is upstream


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real per-source function → §5.9 envelope. Proves the
# envelope contract survives the dispatch (not just that routing is wired).
# ──────────────────────────────────────────────────────────────────────


class _FakeBiblioResponse:
    def __init__(self, documents):
        self._documents = documents

    def model_dump(self):
        return {"documents": self._documents}


@pytest.mark.asyncio
async def test_get_epo_biblio_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance

    fake = _FakeBiblioResponse(documents=[{"publication_number": "EP1234567A1", "title": "Test"}])
    client = MagicMock()
    client.fetch_biblio = AsyncMock(return_value=fake)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("patent_client_agents.mcp.tools.epo_ops.client_from_env", return_value=ctx):
        out = await get_epo(view="biblio", identifier="EP1234567A1")

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "European Patent Office Open Patent Services (EPO OPS)"
    assert "/published-data/publication/docdb/EP1234567A1/biblio" in out.provenance.source_url
    assert len(out.items) == 1
    client.fetch_biblio.assert_awaited_once_with(number="EP1234567A1")
