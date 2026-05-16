"""Envelope-shape tests for the migrated INPI Brazil LPI MCP tools.

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
from patent_client_agents.mcp.tools.inpi_br_statutes import (
    get_inpi_br_section,
    search_inpi_br_statutes,
)


@pytest.fixture(autouse=True)
def _set_corpus(lpi_corpus_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INPI_BR_STATUTES_CORPUS_PATH", str(lpi_corpus_path))


# ──────────────────────────────────────────────────────────────────────
# search_inpi_br_statutes — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default() -> None:
    result = await search_inpi_br_statutes(query="concorrência desleal")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "INPI Brazil — LPI (Lei 9.279/1996)"
    assert "planalto.gov.br" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys.
    assert set(result.items[0].keys()) == {"article_number", "title", "snippet", "href"}
    # Art. 195 is the trade-secret / unfair-competition article.
    articles = [item["article_number"] for item in result.items]
    assert "Art. 195" in articles
    # Summary embeds the query and corpus version so an agent can quote.
    assert "concorrência desleal" in result.summary
    assert "LPI" in result.summary


async def test_search_full_true_returns_upstream_shape() -> None:
    result = await search_inpi_br_statutes(query="patente", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


async def test_search_provenance_carries_corpus_fields() -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()``.
    """
    result = await search_inpi_br_statutes(query="patente")

    assert result.provenance.corpus_version == "1996"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_search_via_english_translation() -> None:
    """The FTS5 index covers EN translation columns, so EN queries also match."""
    result = await search_inpi_br_statutes(query="unfair competition")

    assert len(result.items) >= 1
    assert any(item["article_number"] == "Art. 195" for item in result.items)


# ──────────────────────────────────────────────────────────────────────
# get_inpi_br_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_string_returns_list_envelope() -> None:
    """§5.4: a single-string call returns a ListEnvelope (not a
    ResponseEnvelope) so the response shape is stable.
    """
    result = await get_inpi_br_section(citation="Art. 6")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "INPI Brazil — LPI (Lei 9.279/1996)"
    assert "planalto.gov.br" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert item["href"] == "art6"
    assert "patente" in item["text_pt"].lower()
    assert "patent" in item["text_en"].lower()
    assert "html_pt" in item
    # Summary leads with corpus version + Article label.
    assert "LPI" in result.summary
    assert "1996" in result.summary
    assert "Art. 6" in result.summary


async def test_get_list_preserves_order() -> None:
    refs = ["Art. 6", "Art. 125", "Art. 195"]
    result = await get_inpi_br_section(citation=refs)

    assert isinstance(result, ListEnvelope)
    hrefs = [item["href"] for item in result.items]
    assert hrefs == ["art6", "art125", "art195"]
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root.
    assert result.provenance.source_url.endswith("l9279.htm")


async def test_get_provenance_carries_corpus_fields() -> None:
    result = await get_inpi_br_section(citation="Art. 6")

    assert result.provenance.corpus_version == "1996"
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_get_handles_lpi_suffix() -> None:
    """Attorney citations like 'Art. 195 LPI' / 'Art. 195(XI) LPI' resolve."""
    result = await get_inpi_br_section(citation="Art. 195(XI) LPI")

    assert len(result.items) == 1
    assert result.items[0]["href"] == "art195"


def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import inpi_br_statutes as module

    assert not hasattr(module, "batch_get_inpi_br_section")
    assert not hasattr(module, "batch_inpi_br_section")
