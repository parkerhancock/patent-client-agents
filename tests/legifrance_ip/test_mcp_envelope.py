"""Envelope-shape tests for the Légifrance IP MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), and §4 (substantive-law Provenance carries
``corpus_synced_at`` + ``corpus_version`` from the bundled corpus).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.legifrance_ip import (
    get_legifrance_section,
    search_legifrance_ip,
)

# ──────────────────────────────────────────────────────────────────────
# search_legifrance_ip
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_list_envelope(legifrance_ip_corpus_env: Path) -> None:
    result = await search_legifrance_ip(query="brevetabilité")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert "Légifrance" in result.provenance.source_name
    assert len(result.items) >= 1
    assert set(result.items[0].keys()) == {
        "statute",
        "section",
        "title",
        "snippet",
    }
    assert "brevetabilité" in result.summary
    assert "Légifrance IP" in result.summary


async def test_search_with_statute_filter(legifrance_ip_corpus_env: Path) -> None:
    result = await search_legifrance_ip(query="secret", statute="Code de commerce")
    for item in result.items:
        assert item["statute"] == "Code de commerce"
    assert "Code de commerce" in result.summary


async def test_search_unknown_statute_raises(legifrance_ip_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="statute must be one of"):
        await search_legifrance_ip(query="x", statute="bogus")


async def test_search_provenance_carries_corpus_fields(
    legifrance_ip_corpus_env: Path,
) -> None:
    result = await search_legifrance_ip(query="invention")
    # Build script stamps CORPUS_VERSION="seed v1" → not "unknown".
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version != "unknown"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_search_summary_singular_zero_hits(
    legifrance_ip_corpus_env: Path,
) -> None:
    # A query that won't match the seed.
    result = await search_legifrance_ip(query="zzzzzzzznotaword")
    assert result.items == []
    assert "0 hit" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_legifrance_section — §5.4 list-accepting + envelope
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_citation_returns_list_envelope(
    legifrance_ip_corpus_env: Path,
) -> None:
    result = await get_legifrance_section(citation="L. 611-10 CPI")
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    item = result.items[0]
    assert item["statute"] == "CPI"
    assert item["section"] == "L611-10"
    assert "CPI" in result.summary


async def test_get_list_preserves_order(legifrance_ip_corpus_env: Path) -> None:
    refs = [
        "L. 611-1 CPI",
        "L. 611-10 CPI",
        "L. 151-1 Code de commerce",
    ]
    result = await get_legifrance_section(citation=refs)
    assert isinstance(result, ListEnvelope)
    statute_nums = [(i["statute"], i["section"]) for i in result.items]
    assert statute_nums == [
        ("CPI", "L611-1"),
        ("CPI", "L611-10"),
        ("Code de commerce", "L151-1"),
    ]
    assert "Fetched 3" in result.summary


async def test_get_art_citation(legifrance_ip_corpus_env: Path) -> None:
    result = await get_legifrance_section(citation="Art. L. 151-1 Code de commerce")
    assert result.items[0]["statute"] == "Code de commerce"
    assert result.items[0]["section"] == "L151-1"


async def test_get_provenance_carries_corpus_fields(
    legifrance_ip_corpus_env: Path,
) -> None:
    result = await get_legifrance_section(citation="L. 611-10 CPI")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version != "unknown"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_get_empty_list_raises(legifrance_ip_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await get_legifrance_section(citation=[])


async def test_get_invalid_citation_raises_validation(
    legifrance_ip_corpus_env: Path,
) -> None:
    # CitationParseError gets wrapped to ValidationError at the MCP boundary.
    with pytest.raises(ValidationError, match="could not parse"):
        await get_legifrance_section(citation="totally not a citation")


async def test_no_batch_tool_present() -> None:
    from patent_client_agents.mcp.tools import legifrance_ip as mod

    assert not hasattr(mod, "batch_get_legifrance_section")
    assert not hasattr(mod, "batch_legifrance_section")
