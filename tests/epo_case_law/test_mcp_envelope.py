"""Envelope-shape tests for the migrated EPO Case Law MCP tools.

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
from patent_client_agents.mcp.tools.epo_case_law import (
    get_epo_case_law_section,
    search_epo_case_law,
)


@pytest.fixture(autouse=True)
def _set_corpus(caselaw_corpus_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASELAW_CORPUS_PATH", str(caselaw_corpus_path))


# ──────────────────────────────────────────────────────────────────────
# search_epo_case_law — §5.9, §5.5, §4
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default() -> None:
    result = await search_epo_case_law(query="problem-and-solution")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "EPO Boards of Appeal Case Law Compendium"
    assert "/en/legal/case-law" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys, no upstream-shape fields.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # The fixture corpus has I.D.3 inventive step as the canonical hit.
    sections = [item["section_number"] for item in result.items]
    assert "I.D.3" in sections
    # Summary embeds the query and corpus label so an agent can quote.
    assert "problem-and-solution" in result.summary
    assert "EPO Case Law" in result.summary


async def test_search_full_true_returns_upstream_shape() -> None:
    result = await search_epo_case_law(query="problem-and-solution", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


async def test_search_provenance_carries_corpus_fields() -> None:
    """§4: Provenance must surface ``corpus_synced_at`` and
    ``corpus_version`` from ``get_corpus_status()`` —
    ``meta.caselaw_year`` flows into ``corpus_version``.
    """
    result = await search_epo_case_law(query="Novelty")

    assert result.provenance.corpus_version == "2022"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_epo_case_law_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_string_returns_list_envelope() -> None:
    result = await get_epo_case_law_section(section="I.D.3")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "EPO Boards of Appeal Case Law Compendium"
    assert "/en/legal/case-law" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["href"] == "clr_i_d_3"
    assert "Inventive step" in item["title"]
    assert "html" in item
    assert "text" in item
    # Summary leads with the corpus version + title (§4 / §5.13).
    assert "EPO Case Law" in result.summary
    assert "2022" in result.summary


async def test_get_list_preserves_order() -> None:
    refs = ["I.D.3", "I.A.1", "I.A"]
    result = await get_epo_case_law_section(section=refs)

    assert isinstance(result, ListEnvelope)
    hrefs = [item["href"] for item in result.items]
    assert hrefs == ["clr_i_d_3", "clr_i_a_1", "clr_i_a"]
    # Multi-record summary lists the section numbers.
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root.
    assert result.provenance.source_url.endswith("/en/legal/case-law")


async def test_get_provenance_carries_corpus_fields() -> None:
    result = await get_epo_case_law_section(section="I.D.3")

    assert result.provenance.corpus_version == "2022"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import epo_case_law as caselaw_module

    assert not hasattr(caselaw_module, "batch_get_epo_case_law_section")
    assert not hasattr(caselaw_module, "batch_epo_case_law_section")
