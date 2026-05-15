"""Envelope-shape tests for the migrated TMEP MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), §5.6
(cross-references), and §4 (substantive-law Provenance carries
``corpus_synced_at`` + ``corpus_version`` from the bundled corpus).

Mirrors ``tests/mpep/test_mcp_envelope.py`` — exercises the real
corpus-backed client against the tiny fixture corpus from
``conftest.py``. That lets us assert envelope shape AND that the
corpus_version flowed correctly from ``meta.source_version`` into
``Provenance.corpus_version`` without mocking the boundary.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.trademarks import get_tmep_section, search_tmep

# ──────────────────────────────────────────────────────────────────────
# search_tmep — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default(tmep_corpus_env: Path) -> None:
    result = await search_tmep(query="likelihood of confusion")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == ("USPTO TMEP (Trademark Manual of Examining Procedure)")
    assert "/RDMS/TMEP/search" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys, no upstream-shape fields like
    # ``result_url`` or ``path``.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # The fixture corpus has §1207 / §1207.01 as the canonical hits for
    # "likelihood of confusion".
    sections = [item["section_number"] for item in result.items]
    assert any(s and s.startswith("1207") for s in sections)
    # Summary embeds the query and corpus version so an agent can quote.
    assert "likelihood of confusion" in result.summary
    assert "TMEP" in result.summary


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape(tmep_corpus_env: Path) -> None:
    result = await search_tmep(query="likelihood of confusion", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full-shape preserves the upstream TmepSearchHit fields
    # (``title`` is prefixed with the section_number; ``result_url``
    # is present; ``path`` carries the breadcrumb).
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


@pytest.mark.asyncio
async def test_search_provenance_carries_corpus_fields(tmep_corpus_env: Path) -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()`` (which
    reads ``meta.source_version`` / ``meta.snapshot_date``) — never
    hardcoded in the tool function. The fixture corpus stamps
    ``source_version='current'``.
    """
    result = await search_tmep(query="specimen")

    assert result.provenance.corpus_version == "current"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_tmep_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope(tmep_corpus_env: Path) -> None:
    """§5.4: a single-string call returns a ListEnvelope (not a
    ResponseEnvelope) so the response shape is stable across single
    and multi-section calls.
    """
    result = await get_tmep_section(section="1207")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == ("USPTO TMEP (Trademark Manual of Examining Procedure)")
    assert "/RDMS/TMEP/result" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["section_number"] == "1207"
    assert item["title"] == ("Refusal on Basis of Likelihood of Confusion, Mistake, or Deception")
    assert "html" in item
    assert "text" in item
    # Summary is Markdown leading with the corpus version + section number
    # so agents can paste it as a freshness-aware citation (§4 / §5.13).
    assert "TMEP" in result.summary
    assert "current" in result.summary
    assert "1207" in result.summary


@pytest.mark.asyncio
async def test_get_list_preserves_order(tmep_corpus_env: Path) -> None:
    refs = ["1207", "1402", "904"]
    result = await get_tmep_section(section=refs)

    assert isinstance(result, ListEnvelope)
    assert [item["section_number"] for item in result.items] == refs
    # Multi-record summary lists the section numbers.
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root, not a specific record.
    assert result.provenance.source_url.endswith("/RDMS/TMEP/result")


@pytest.mark.asyncio
async def test_get_provenance_carries_corpus_fields(tmep_corpus_env: Path) -> None:
    """The Provenance.corpus_version stamp must be present on get_* too,
    not just search_*. Critical assertion that the Provenance fields
    flow from get_corpus_status, not from a hardcoded constant in the
    tool.
    """
    result = await get_tmep_section(section="1207")

    assert result.provenance.corpus_version == "current"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import trademarks as trademarks_module

    assert not hasattr(trademarks_module, "batch_get_tmep_section")
    assert not hasattr(trademarks_module, "batch_tmep_section")
