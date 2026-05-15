"""Envelope-shape tests for the migrated UP Guidelines MCP tools.

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
from patent_client_agents.mcp.tools.epo_up_guidelines import (
    get_epo_up_guidelines_section,
    search_epo_up_guidelines,
)

# ──────────────────────────────────────────────────────────────────────
# search_epo_up_guidelines — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default(
    up_corpus_env: Path,
) -> None:
    result = await search_epo_up_guidelines(query="unitary effect")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Unitary Patent Guidelines"
    assert "/en/legal/guidelines-up" in result.provenance.source_url
    assert len(result.items) >= 1
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    assert "unitary effect" in result.summary
    assert "UP Guidelines" in result.summary


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape(up_corpus_env: Path) -> None:
    result = await search_epo_up_guidelines(query="unitary effect", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


@pytest.mark.asyncio
async def test_search_provenance_carries_corpus_fields(up_corpus_env: Path) -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()`` (which
    reads ``meta.up_guidelines_year`` as the version fallback for UP) —
    never hardcoded in the tool function.
    """
    result = await search_epo_up_guidelines(query="unitary effect")

    assert result.provenance.corpus_version == "2026"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_epo_up_guidelines_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope(up_corpus_env: Path) -> None:
    """§5.4: a single-string call returns a ListEnvelope so the response
    shape is stable across single and multi-section calls.
    """
    result = await get_epo_up_guidelines_section(section="2.1")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "Unitary Patent Guidelines"
    assert "/en/legal/guidelines-up" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["href"] == "section_2_1"
    assert "html" in item
    assert "text" in item
    assert "UP Guidelines" in result.summary
    assert "2026" in result.summary


@pytest.mark.asyncio
async def test_get_list_preserves_order(up_corpus_env: Path) -> None:
    refs = ["2.1", "3.2", "4.1"]
    result = await get_epo_up_guidelines_section(section=refs)

    assert isinstance(result, ListEnvelope)
    assert [item["href"] for item in result.items] == [
        "section_2_1",
        "section_3_2",
        "section_4_1",
    ]
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    assert result.provenance.source_url.endswith("/en/legal/guidelines-up")


@pytest.mark.asyncio
async def test_get_provenance_carries_corpus_fields(up_corpus_env: Path) -> None:
    result = await get_epo_up_guidelines_section(section="2.1")

    assert result.provenance.corpus_version == "2026"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import epo_up_guidelines as mod

    assert not hasattr(mod, "batch_get_epo_up_guidelines_section")
    assert not hasattr(mod, "batch_epo_up_guidelines_section")
