"""Envelope-shape tests for the migrated MPEP MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), §5.6
(cross-references), and §4 (substantive-law Provenance carries
``corpus_synced_at`` + ``corpus_version`` from the bundled corpus).

Exercises the real corpus-backed client against the tiny fixture
corpus from ``conftest.py`` — that lets us assert envelope shape AND
that the corpus_version flowed correctly from ``meta.source_version``
into ``Provenance.corpus_version`` without mocking the boundary.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.mpep import get_mpep_section, search_mpep

# ──────────────────────────────────────────────────────────────────────
# search_mpep — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default(mpep_corpus_env: Path) -> None:
    result = await search_mpep(query="subject matter eligibility")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO MPEP (Manual of Patent Examining Procedure)"
    assert "/RDMS/MPEP/search" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys, no upstream-shape fields like
    # ``result_url`` or ``path``.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # The fixture corpus has §2106 "Patent Subject Matter Eligibility" as
    # the canonical hit.
    sections = [item["section_number"] for item in result.items]
    assert "2106" in sections
    # Summary embeds the query and corpus version so an agent can quote.
    assert "subject matter eligibility" in result.summary
    assert "MPEP" in result.summary


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape(mpep_corpus_env: Path) -> None:
    result = await search_mpep(query="subject matter eligibility", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full-shape preserves the upstream MpepSearchHit fields
    # (``title`` is prefixed with the section_number; ``result_url``
    # is present; ``path`` carries the breadcrumb).
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


@pytest.mark.asyncio
async def test_search_provenance_carries_corpus_fields(mpep_corpus_env: Path) -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()`` (which
    reads ``meta.source_version`` / ``meta.snapshot_date``) — never
    hardcoded in the tool function. The fixture corpus stamps
    ``source_version='current'``.
    """
    result = await search_mpep(query="patent")

    assert result.provenance.corpus_version == "current"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_mpep_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope(mpep_corpus_env: Path) -> None:
    """§5.4: a single-string call returns a ListEnvelope (not a
    ResponseEnvelope) so the response shape is stable across single
    and multi-section calls.
    """
    result = await get_mpep_section(section="2106")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "USPTO MPEP (Manual of Patent Examining Procedure)"
    assert "/RDMS/MPEP/result" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["section_number"] == "2106"
    assert item["title"] == "Patent Subject Matter Eligibility"
    assert "html" in item
    assert "text" in item
    # Summary is Markdown leading with the corpus version + section number
    # so agents can paste it as a freshness-aware citation (§4 / §5.13).
    assert "MPEP" in result.summary
    assert "current" in result.summary
    assert "2106" in result.summary


@pytest.mark.asyncio
async def test_get_list_preserves_order(mpep_corpus_env: Path) -> None:
    refs = ["2106", "2143", "706"]
    result = await get_mpep_section(section=refs)

    assert isinstance(result, ListEnvelope)
    assert [item["section_number"] for item in result.items] == refs
    # Multi-record summary lists the section numbers.
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root, not a specific record.
    assert result.provenance.source_url.endswith("/RDMS/MPEP/result")


@pytest.mark.asyncio
async def test_get_provenance_carries_corpus_fields(mpep_corpus_env: Path) -> None:
    """The Provenance.corpus_version stamp must be present on get_* too,
    not just search_*. This is the critical assertion for row 17 — the
    Provenance fields flow from get_corpus_status, not from a hardcoded
    constant in the tool.
    """
    result = await get_mpep_section(section="2106")

    assert result.provenance.corpus_version == "current"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import mpep as mpep_module

    assert not hasattr(mpep_module, "batch_get_mpep_section")
    assert not hasattr(mpep_module, "batch_mpep_section")
