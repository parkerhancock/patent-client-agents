"""Envelope-shape tests for the migrated EPC MCP tools.

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
from patent_client_agents.mcp.tools.epc import get_epc_section, search_epc


@pytest.fixture(autouse=True)
def _set_corpus(epc_corpus_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EPC_CORPUS_PATH", str(epc_corpus_path))


# ──────────────────────────────────────────────────────────────────────
# search_epc — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default() -> None:
    result = await search_epc(query="novelty")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "European Patent Convention"
    assert "/en/legal/epc" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys, no upstream-shape fields.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # The fixture corpus has Article 54 as the canonical novelty hit.
    sections = [item["section_number"] for item in result.items]
    assert "Article 54" in sections
    # Summary embeds the query and corpus version so an agent can quote.
    assert "novelty" in result.summary
    assert "EPC" in result.summary


async def test_search_full_true_returns_upstream_shape() -> None:
    result = await search_epc(query="novelty", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full-shape preserves the upstream EpcSearchHit fields:
    # ``title``, ``href``, ``path`` (breadcrumb), ``result_url``.
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


async def test_search_provenance_carries_corpus_fields() -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()`` (which
    reads ``meta.epc_year`` / ``meta.snapshot_date``) — never hardcoded
    in the tool function. The fixture corpus stamps ``epc_year='2020'``.
    """
    result = await search_epc(query="novelty")

    assert result.provenance.corpus_version == "2020"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_epc_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_string_returns_list_envelope() -> None:
    """§5.4: a single-string call returns a ListEnvelope (not a
    ResponseEnvelope) so the response shape is stable across single
    and multi-section calls.
    """
    result = await get_epc_section(section="Article 54")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "European Patent Convention"
    assert "/en/legal/epc" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["href"] == "a54"
    assert "Novelty" in item["title"]
    assert "html" in item
    assert "text" in item
    # Summary is Markdown leading with the corpus version + title so
    # agents can paste it as a freshness-aware citation (§4 / §5.13).
    assert "EPC" in result.summary
    assert "2020" in result.summary


async def test_get_list_preserves_order() -> None:
    refs = ["Article 54", "Article 56", "Rule 71"]
    result = await get_epc_section(section=refs)

    assert isinstance(result, ListEnvelope)
    # Order is preserved across the fan-out.
    hrefs = [item["href"] for item in result.items]
    assert hrefs == ["a54", "a56", "r71"]
    # Multi-record summary lists the section numbers.
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root.
    assert result.provenance.source_url.endswith("/en/legal/epc")


async def test_get_provenance_carries_corpus_fields() -> None:
    """The Provenance.corpus_version stamp must be present on get_* too,
    not just search_*. The Provenance fields flow from
    get_corpus_status, not from a hardcoded constant in the tool.
    """
    result = await get_epc_section(section="Article 54")

    assert result.provenance.corpus_version == "2020"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import epc as epc_module

    assert not hasattr(epc_module, "batch_get_epc_section")
    assert not hasattr(epc_module, "batch_epc_section")
