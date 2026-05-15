"""Envelope-shape tests for the migrated PCT-EPO Guidelines MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), §5.6
(cross-references), and §4 (substantive-law Provenance carries
``corpus_synced_at`` + ``corpus_version`` from the bundled corpus).

Exercises the real corpus-backed client against the tiny fixture
corpus from ``conftest.py``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.epo_pct_guidelines import (
    get_epo_pct_guidelines_section,
    search_epo_pct_guidelines,
)

# ──────────────────────────────────────────────────────────────────────
# search_epo_pct_guidelines — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default(
    pct_corpus_env: Path,
) -> None:
    result = await search_epo_pct_guidelines(query="Discoveries")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "PCT-EPO Guidelines for Examination"
    assert "/en/legal/guidelines-pct" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # Summary embeds the query and corpus version.
    assert "Discoveries" in result.summary
    assert "PCT-EPO Guidelines" in result.summary


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape(pct_corpus_env: Path) -> None:
    result = await search_epo_pct_guidelines(query="Discoveries", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full-shape preserves the upstream PctGuidelinesSearchHit fields.
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


@pytest.mark.asyncio
async def test_search_provenance_carries_corpus_fields(pct_corpus_env: Path) -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()`` (which
    reads ``meta.guidelines_year`` as the version fallback for PCT) —
    never hardcoded in the tool function.
    """
    result = await search_epo_pct_guidelines(query="Discoveries")

    assert result.provenance.corpus_version == "2024"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_epo_pct_guidelines_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope(pct_corpus_env: Path) -> None:
    """§5.4: a single-string call returns a ListEnvelope (not a
    ResponseEnvelope) so the response shape is stable across single
    and multi-section calls.
    """
    result = await get_epo_pct_guidelines_section(section="G-II, 3.1")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "PCT-EPO Guidelines for Examination"
    assert "/en/legal/guidelines-pct" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["href"] == "g_ii_3_1"
    assert "html" in item
    assert "text" in item
    assert "PCT-EPO Guidelines" in result.summary
    assert "2024" in result.summary


@pytest.mark.asyncio
async def test_get_list_preserves_order(pct_corpus_env: Path) -> None:
    refs = ["G-II, 3.1", "G-III, 1", "B-IV, 1.1"]
    result = await get_epo_pct_guidelines_section(section=refs)

    assert isinstance(result, ListEnvelope)
    assert [item["href"] for item in result.items] == [
        "g_ii_3_1",
        "g_iii_1",
        "b_iv_1_1",
    ]
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root, not a specific record.
    assert result.provenance.source_url.endswith("/en/legal/guidelines-pct")


@pytest.mark.asyncio
async def test_get_provenance_carries_corpus_fields(pct_corpus_env: Path) -> None:
    result = await get_epo_pct_guidelines_section(section="G-II, 3.1")

    assert result.provenance.corpus_version == "2024"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import epo_pct_guidelines as mod

    assert not hasattr(mod, "batch_get_epo_pct_guidelines_section")
    assert not hasattr(mod, "batch_epo_pct_guidelines_section")
