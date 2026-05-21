"""Envelope-shape tests for the IPO India MPPP MCP tools.

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
from patent_client_agents.mcp.tools.ipo_in_mppp import (
    get_ipo_in_mppp_section,
    search_ipo_in_mppp,
)


async def test_search_returns_lean_list_envelope(ipo_in_mppp_corpus_env: Path) -> None:
    result = await search_ipo_in_mppp(query="first examination report")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert "MPPP" in result.provenance.source_name
    assert len(result.items) >= 1
    assert set(result.items[0].keys()) == {
        "section_number",
        "chapter",
        "title",
        "snippet",
    }
    assert "first examination report" in result.summary


async def test_search_full_true_includes_rank(ipo_in_mppp_corpus_env: Path) -> None:
    result = await search_ipo_in_mppp(query="examination", full=True)
    assert result.items
    assert "rank" in result.items[0]


async def test_search_provenance_corpus_fields(ipo_in_mppp_corpus_env: Path) -> None:
    result = await search_ipo_in_mppp(query="examination")
    # MPPP build stamps v3.0 (2019)
    assert result.provenance.corpus_version == "v3.0 (2019)"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_search_limit_validation(ipo_in_mppp_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_ipo_in_mppp(query="x", limit=0)
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_ipo_in_mppp(query="x", limit=200)


async def test_search_pagination(ipo_in_mppp_corpus_env: Path) -> None:
    result = await search_ipo_in_mppp(query="section", limit=1, offset=0)
    assert result.more_available is True
    assert "more available" in result.summary


async def test_get_single_section(ipo_in_mppp_corpus_env: Path) -> None:
    result = await get_ipo_in_mppp_section(citation="04.05.01")
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["section_number"] == "04.05.01"
    assert "04.05.01" in result.summary


async def test_get_with_chapter_prefix(ipo_in_mppp_corpus_env: Path) -> None:
    result = await get_ipo_in_mppp_section(citation="MPPP Chapter 04.05.01")
    assert result.items[0]["section_number"] == "04.05.01"


async def test_get_list_preserves_order(ipo_in_mppp_corpus_env: Path) -> None:
    refs = ["04.05.01", "05.04", "07.02"]
    result = await get_ipo_in_mppp_section(citation=refs)
    nums = [i["section_number"] for i in result.items]
    assert nums == refs
    assert "Fetched 3" in result.summary


async def test_get_provenance_corpus_fields(ipo_in_mppp_corpus_env: Path) -> None:
    result = await get_ipo_in_mppp_section(citation="04.05.01")
    assert result.provenance.corpus_version == "v3.0 (2019)"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_get_empty_list_raises(ipo_in_mppp_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipo_in_mppp_section(citation=[])


async def test_no_batch_tool_present() -> None:
    from patent_client_agents.mcp.tools import ipo_in_mppp as mod

    assert not hasattr(mod, "batch_get_ipo_in_mppp_section")
    assert not hasattr(mod, "batch_ipo_in_mppp_section")
