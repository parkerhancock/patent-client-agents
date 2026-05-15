"""Envelope-shape tests for the migrated CPC MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.5 (lean default +
``full=True`` opt-in for ``search_cpc``), §5.6 (cross-references), and
§5.13 (sharpened first sentences for the CPC trio).

Mocks the EPO OPS client at the boundary; the underlying CPC classifier
HTTP path is not exercised here.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance, ResponseEnvelope
from patent_client_agents.epo_ops.models import (
    ClassificationMapping,
    ClassificationMappingResponse,
    CpcClassificationItem,
    CpcRetrievalResponse,
    CpcScheme,
    CpcSearchResponse,
    CpcSearchResult,
)
from patent_client_agents.mcp.tools.international import (
    lookup_cpc,
    map_cpc_classification,
    search_cpc,
)

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


def _patch_client_from_env(monkeypatch_target: str, mock_client) -> MagicMock:
    """Patch ``client_from_env`` so its async-context-manager yields mock_client."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_client)
    cm.__aexit__ = AsyncMock(return_value=None)
    patcher = patch(monkeypatch_target, return_value=cm)
    return patcher


# ──────────────────────────────────────────────────────────────────────
# lookup_cpc — §5.9, §5.13
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lookup_cpc_returns_response_envelope_with_provenance():
    upstream = CpcRetrievalResponse(
        scheme=CpcScheme(
            items=[
                CpcClassificationItem(
                    symbol="H04L9/32",
                    title="including means for verifying the identity or authority of a user",
                    level=3,
                )
            ]
        )
    )
    mock_client = MagicMock()
    mock_client.retrieve_cpc = AsyncMock(return_value=upstream)

    with _patch_client_from_env(
        "patent_client_agents.mcp.tools.international.client_from_env", mock_client
    ):
        result = await lookup_cpc(symbol="H04L9/32")

    assert isinstance(result, ResponseEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Cooperative Patent Classification (CPC)"
    assert "/classification/cpc/H04L9/32" in result.provenance.source_url
    # Summary leads with the symbol + title.
    assert "H04L9/32" in result.summary
    assert "verifying the identity" in result.summary
    # Full payload flows through `details`.
    assert result.details["scheme"]["items"][0]["symbol"] == "H04L9/32"


@pytest.mark.asyncio
async def test_lookup_cpc_handles_empty_scheme():
    upstream = CpcRetrievalResponse(scheme=CpcScheme(items=[]))
    mock_client = MagicMock()
    mock_client.retrieve_cpc = AsyncMock(return_value=upstream)

    with _patch_client_from_env(
        "patent_client_agents.mcp.tools.international.client_from_env", mock_client
    ):
        result = await lookup_cpc(symbol="Z99Z99/99")

    assert isinstance(result, ResponseEnvelope)
    assert "Z99Z99/99" in result.summary
    assert "no title" in result.summary


# ──────────────────────────────────────────────────────────────────────
# search_cpc — §5.5 lean default + full=True opt-in, §5.9
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_cpc_returns_lean_list_envelope_by_default():
    upstream = CpcSearchResponse(
        query="machine learning",
        total_results=42,
        range_begin=1,
        range_end=10,
        results=[
            CpcSearchResult(
                classification_symbol="G06N3/04",
                percentage=99.5,
                title="Architectures, e.g. interconnection topology",
            ),
            CpcSearchResult(
                classification_symbol="G06N20/00",
                percentage=87.2,
                title="Machine learning",
            ),
        ],
    )
    mock_client = MagicMock()
    mock_client.search_cpc = AsyncMock(return_value=upstream)

    with _patch_client_from_env(
        "patent_client_agents.mcp.tools.international.client_from_env", mock_client
    ):
        result = await search_cpc(query="machine learning")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "Cooperative Patent Classification (CPC)"
    assert "/classification/cpc/search" in result.provenance.source_url
    # Lean projection keys only.
    assert set(result.items[0].keys()) == {"symbol", "title", "parent_symbol"}
    assert result.items[0]["symbol"] == "G06N3/04"
    assert "machine learning" in result.summary
    assert "2 of 42 hits" in result.summary
    assert result.more_available is True


@pytest.mark.asyncio
async def test_search_cpc_full_true_returns_upstream_shape():
    upstream = CpcSearchResponse(
        query="ml",
        total_results=1,
        results=[
            CpcSearchResult(classification_symbol="G06N20/00", percentage=87.2, title="ML"),
        ],
    )
    mock_client = MagicMock()
    mock_client.search_cpc = AsyncMock(return_value=upstream)

    with _patch_client_from_env(
        "patent_client_agents.mcp.tools.international.client_from_env", mock_client
    ):
        result = await search_cpc(query="ml", full=True)

    # Full shape uses upstream field names.
    assert "classification_symbol" in result.items[0]
    assert result.items[0]["percentage"] == 87.2
    assert result.more_available is False  # 1 of 1 with range_begin=1


# ──────────────────────────────────────────────────────────────────────
# map_cpc_classification — §5.9
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_map_cpc_classification_returns_response_envelope():
    upstream = ClassificationMappingResponse(
        input_schema="cpc",
        output_schema="ipc",
        mappings=[ClassificationMapping(cpc="H04L9/32", ipc="H04L9/32")],
    )

    with patch(
        "patent_client_agents.mcp.tools.international.map_classification",
        new=AsyncMock(return_value=upstream),
    ):
        result = await map_cpc_classification(symbol="H04L9/32", from_scheme="cpc", to_scheme="ipc")

    assert isinstance(result, ResponseEnvelope)
    assert result.provenance.source_name == "Cooperative Patent Classification (CPC)"
    assert "/classification/map/cpc/H04L9/32/ipc" in result.provenance.source_url
    assert "H04L9/32" in result.summary
    assert "CPC" in result.summary and "IPC" in result.summary
    assert result.details["mappings"][0]["ipc"] == "H04L9/32"


@pytest.mark.asyncio
async def test_map_cpc_classification_empty_mappings_summary():
    upstream = ClassificationMappingResponse(input_schema="cpc", output_schema="uscls", mappings=[])

    with patch(
        "patent_client_agents.mcp.tools.international.map_classification",
        new=AsyncMock(return_value=upstream),
    ):
        result = await map_cpc_classification(
            symbol="H04L9/32", from_scheme="cpc", to_scheme="uscls"
        )

    assert isinstance(result, ResponseEnvelope)
    assert "no cross-reference found" in result.summary
    assert result.details["mappings"] == []


# ──────────────────────────────────────────────────────────────────────
# Docstring discipline — §5.6 cross-references, §5.13 sharpened sentences
# ──────────────────────────────────────────────────────────────────────


def test_cpc_tools_cross_reference_siblings():
    """Every CPC tool must name the other two in its docstring (§5.6)."""
    for tool, siblings in [
        (lookup_cpc, ["search_cpc", "map_cpc_classification"]),
        (search_cpc, ["lookup_cpc", "map_cpc_classification"]),
        (map_cpc_classification, ["lookup_cpc", "search_cpc"]),
    ]:
        doc = tool.__doc__ or ""
        assert "Related tools:" in doc, f"{tool.__name__} missing Related tools line"
        for sibling in siblings:
            assert sibling in doc, f"{tool.__name__} docstring missing sibling {sibling}"


def test_cpc_tool_first_sentences_are_distinct():
    """Per §5.13, the three CPC tools' first sentences must not blur together."""
    firsts = {
        tool.__name__: (tool.__doc__ or "").strip().split("\n", 1)[0]
        for tool in (lookup_cpc, search_cpc, map_cpc_classification)
    }
    # All three start with a different verb; none is a substring of another.
    assert firsts["lookup_cpc"].startswith("Look up")
    assert firsts["search_cpc"].startswith("Search CPC titles")
    assert firsts["map_cpc_classification"].startswith("Convert")
    for a, b in [
        ("lookup_cpc", "search_cpc"),
        ("search_cpc", "map_cpc_classification"),
        ("lookup_cpc", "map_cpc_classification"),
    ]:
        assert firsts[a] != firsts[b]
