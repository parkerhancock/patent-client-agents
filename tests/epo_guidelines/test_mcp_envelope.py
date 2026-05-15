"""Envelope-shape tests for the migrated EPO Guidelines MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + full opt-in), §5.6
(cross-references), and §4 (substantive-law Provenance carries
``corpus_synced_at`` + ``corpus_version`` from the bundled corpus).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.epo_guidelines import (
    get_epo_guidelines_section,
    search_epo_guidelines,
)


@pytest.fixture(autouse=True)
def _set_corpus(guidelines_corpus_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GUIDELINES_CORPUS_PATH", str(guidelines_corpus_path))


# ──────────────────────────────────────────────────────────────────────
# search_epo_guidelines — §5.9, §5.5, §4
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default() -> None:
    result = await search_epo_guidelines(query="Discoveries")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "EPO Guidelines for Examination"
    assert "/en/legal/guidelines-epc" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys, no upstream-shape fields.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # The fixture corpus has G-II, 3.1 "Discoveries" as the canonical hit.
    sections = [item["section_number"] for item in result.items]
    assert "G-II, 3.1" in sections
    # Summary embeds the query and corpus label so an agent can quote.
    assert "Discoveries" in result.summary
    assert "EPO Guidelines" in result.summary


async def test_search_full_true_returns_upstream_shape() -> None:
    result = await search_epo_guidelines(query="Discoveries", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


async def test_search_provenance_carries_corpus_fields() -> None:
    """§4: Provenance must surface ``corpus_synced_at`` and
    ``corpus_version`` from ``get_corpus_status()`` —
    ``meta.guidelines_year`` flows into ``corpus_version``.
    """
    result = await search_epo_guidelines(query="Discoveries")

    assert result.provenance.corpus_version == "2024"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_epo_guidelines_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_string_returns_list_envelope() -> None:
    result = await get_epo_guidelines_section(section="G-II, 3.1")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "EPO Guidelines for Examination"
    assert "/en/legal/guidelines-epc" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["href"] == "g_ii_3_1"
    assert "Discoveries" in item["title"]
    assert "html" in item
    assert "text" in item
    # Summary leads with the corpus version so agents can paste it as a
    # freshness-aware citation (§4 / §5.13).
    assert "EPO Guidelines" in result.summary
    assert "2024" in result.summary


async def test_get_list_preserves_order() -> None:
    refs = ["G-II, 3.1", "G-II, 3", "H"]
    result = await get_epo_guidelines_section(section=refs)

    assert isinstance(result, ListEnvelope)
    hrefs = [item["href"] for item in result.items]
    assert hrefs == ["g_ii_3_1", "g_ii_3", "h"]
    # Multi-record summary lists the section numbers.
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root.
    assert result.provenance.source_url.endswith("/en/legal/guidelines-epc")


async def test_get_provenance_carries_corpus_fields() -> None:
    result = await get_epo_guidelines_section(section="G-II, 3.1")

    assert result.provenance.corpus_version == "2024"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import epo_guidelines as guidelines_module

    assert not hasattr(guidelines_module, "batch_get_epo_guidelines_section")
    assert not hasattr(guidelines_module, "batch_epo_guidelines_section")
