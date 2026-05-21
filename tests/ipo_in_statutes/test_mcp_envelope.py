"""Envelope-shape tests for the IPO India statutes MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + ``full=True`` opt-in),
§5.6 (cross-references), and §4 (substantive-law Provenance carries
``corpus_synced_at`` + ``corpus_version`` from the bundled corpus).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.ipo_in_statutes import (
    get_ipo_in_section,
    search_ipo_in_statutes,
)

# ──────────────────────────────────────────────────────────────────────
# search_ipo_in_statutes — §5.9, §5.5, §4
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default(
    ipo_in_statutes_corpus_env: Path,
) -> None:
    result = await search_ipo_in_statutes(query="efficacy")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IPO India — IP statutes"
    assert len(result.items) >= 1
    assert set(result.items[0].keys()) == {
        "statute_name",
        "section_number",
        "title",
        "snippet",
    }
    assert "efficacy" in result.summary
    assert "IPO India statutes" in result.summary


async def test_search_full_true_returns_upstream_shape(
    ipo_in_statutes_corpus_env: Path,
) -> None:
    result = await search_ipo_in_statutes(query="efficacy", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full mode preserves the rank/snippet shape
    assert "rank" in result.items[0]


async def test_search_with_statute_filter(ipo_in_statutes_corpus_env: Path) -> None:
    result = await search_ipo_in_statutes(query="fair", statute="Copyright Act")
    for item in result.items:
        assert item["statute_name"] == "Copyright Act"
    assert "Copyright Act" in result.summary


async def test_search_provenance_carries_corpus_fields(
    ipo_in_statutes_corpus_env: Path,
) -> None:
    result = await search_ipo_in_statutes(query="patent")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_search_limit_validation(ipo_in_statutes_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_ipo_in_statutes(query="x", limit=0)
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_ipo_in_statutes(query="x", limit=999)


async def test_search_pagination_summary(ipo_in_statutes_corpus_env: Path) -> None:
    result = await search_ipo_in_statutes(query="section", limit=1, offset=0)
    # With a small per-page, there should be more available
    assert result.more_available is True
    assert "more available" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_ipo_in_section — §5.4 list-accepting + envelope
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_citation_returns_list_envelope(
    ipo_in_statutes_corpus_env: Path,
) -> None:
    result = await get_ipo_in_section(citation="Section 3(d) Patents Act")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "IPO India — IP statutes"
    assert len(result.items) == 1
    item = result.items[0]
    assert item["statute_name"] == "Patents Act"
    assert item["section_number"] == "3(d)"
    assert "Patents Act" in result.summary
    assert "3(d)" in result.summary


async def test_get_list_preserves_order(ipo_in_statutes_corpus_env: Path) -> None:
    refs = [
        "Section 3(d) Patents Act",
        "Section 84 Patents Act",
        "Section 9 Trade Marks Act",
    ]
    result = await get_ipo_in_section(citation=refs)
    assert isinstance(result, ListEnvelope)
    statute_nums = [(i["statute_name"], i["section_number"]) for i in result.items]
    assert statute_nums == [
        ("Patents Act", "3(d)"),
        ("Patents Act", "84"),
        ("Trade Marks Act", "9"),
    ]
    assert "Fetched 3" in result.summary


async def test_get_rule_citation(ipo_in_statutes_corpus_env: Path) -> None:
    result = await get_ipo_in_section(citation="Rule 71 Patent Rules")
    assert result.items[0]["statute_name"] == "Patent Rules"
    assert result.items[0]["section_number"] == "71"


async def test_get_provenance_carries_corpus_fields(
    ipo_in_statutes_corpus_env: Path,
) -> None:
    result = await get_ipo_in_section(citation="Section 84 Patents Act")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_get_empty_list_raises(ipo_in_statutes_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipo_in_section(citation=[])


async def test_no_batch_tool_present() -> None:
    from patent_client_agents.mcp.tools import ipo_in_statutes as mod

    assert not hasattr(mod, "batch_get_ipo_in_section")
    assert not hasattr(mod, "batch_ipo_in_section")
