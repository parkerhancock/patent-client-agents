"""Envelope-shape tests for the DPMA Germany statutes MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + ``full=True`` opt-in),
and §4 (substantive-law Provenance carries ``corpus_synced_at`` +
``corpus_version`` from the bundled corpus).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.dpma_statutes import (
    get_dpma_section,
    search_dpma_statutes,
)

# ──────────────────────────────────────────────────────────────────────
# search_dpma_statutes — §5.9, §5.5, §4
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default(
    dpma_statutes_corpus_env: Path,
) -> None:
    result = await search_dpma_statutes(query="Patent")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "DPMA Germany — IP statutes"
    assert len(result.items) >= 1
    assert set(result.items[0].keys()) == {
        "statute",
        "section",
        "title",
        "snippet",
    }
    assert "Patent" in result.summary
    assert "DPMA Germany statutes" in result.summary


async def test_search_full_true_returns_upstream_shape(
    dpma_statutes_corpus_env: Path,
) -> None:
    result = await search_dpma_statutes(query="Patent", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full mode preserves the rank/snippet shape
    assert "rank" in result.items[0]


async def test_search_with_statute_filter(dpma_statutes_corpus_env: Path) -> None:
    result = await search_dpma_statutes(query="Marke", statute="MarkenG")
    for item in result.items:
        assert item["statute"] == "MarkenG"
    assert "MarkenG" in result.summary


async def test_search_provenance_carries_corpus_fields(
    dpma_statutes_corpus_env: Path,
) -> None:
    result = await search_dpma_statutes(query="Patent")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_search_limit_validation(dpma_statutes_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_dpma_statutes(query="x", limit=0)
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_dpma_statutes(query="x", limit=999)


async def test_search_pagination_summary(dpma_statutes_corpus_env: Path) -> None:
    result = await search_dpma_statutes(query="die", limit=1, offset=0, syntax="or")
    # With a small per-page, there should be more available
    assert result.more_available is True
    assert "more available" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_dpma_section — §5.4 list-accepting + envelope
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_citation_returns_list_envelope(
    dpma_statutes_corpus_env: Path,
) -> None:
    result = await get_dpma_section(citation="§ 139 PatG")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "DPMA Germany — IP statutes"
    assert len(result.items) == 1
    item = result.items[0]
    assert item["statute"] == "PatG"
    assert item["section"] == "139"
    assert "PatG" in result.summary
    assert "139" in result.summary


async def test_get_list_preserves_order(dpma_statutes_corpus_env: Path) -> None:
    refs = [
        "§ 139 PatG",
        "§ 14 MarkenG",
        "§ 97 UrhG",
    ]
    result = await get_dpma_section(citation=refs)
    assert isinstance(result, ListEnvelope)
    statute_nums = [(i["statute"], i["section"]) for i in result.items]
    assert statute_nums == [
        ("PatG", "139"),
        ("MarkenG", "14"),
        ("UrhG", "97"),
    ]
    assert "Fetched 3" in result.summary


async def test_get_geschgehg_citation(dpma_statutes_corpus_env: Path) -> None:
    result = await get_dpma_section(citation="§ 1 GeschGehG")
    assert result.items[0]["statute"] == "GeschGehG"
    assert result.items[0]["section"] == "1"


async def test_get_provenance_carries_corpus_fields(
    dpma_statutes_corpus_env: Path,
) -> None:
    result = await get_dpma_section(citation="§ 139 PatG")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_get_empty_list_raises(dpma_statutes_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await get_dpma_section(citation=[])


async def test_no_batch_tool_present() -> None:
    from patent_client_agents.mcp.tools import dpma_statutes as mod

    assert not hasattr(mod, "batch_get_dpma_section")
    assert not hasattr(mod, "batch_dpma_section")
