"""Envelope-shape tests for the migrated UKIPO MoPP MCP tools.

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
from patent_client_agents.mcp.tools.ukipo_mopp import get_mopp_section, search_mopp

# ──────────────────────────────────────────────────────────────────────
# search_mopp — §5.9, §5.5, §4 (corpus fields on Provenance)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_lean_list_envelope_by_default(
    mopp_corpus_env: Path,
) -> None:
    result = await search_mopp(query="methods of treatment")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "UKIPO Manual of Patent Practice (MoPP)"
    assert "/guidance/manual-of-patent-practice-mopp" in result.provenance.source_url
    assert len(result.items) >= 1
    # Lean projection: exactly these keys.
    assert set(result.items[0].keys()) == {"section_number", "title", "snippet", "href"}
    # Summary embeds the query and corpus version.
    assert "methods of treatment" in result.summary
    assert "MoPP" in result.summary


@pytest.mark.asyncio
async def test_search_full_true_returns_upstream_shape(mopp_corpus_env: Path) -> None:
    result = await search_mopp(query="methods of treatment", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    item = result.items[0]
    assert "result_url" in item
    assert "path" in item
    assert "title" in item


@pytest.mark.asyncio
async def test_search_provenance_carries_corpus_fields(mopp_corpus_env: Path) -> None:
    """§4: substantive-law Provenance must surface ``corpus_synced_at`` and
    ``corpus_version``. They flow from ``get_corpus_status()`` — for
    MoPP the version falls back to a ``snapshot-<date>`` label since
    gov.uk doesn't publish a stable revision tag.
    """
    result = await search_mopp(query="application")

    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


# ──────────────────────────────────────────────────────────────────────
# get_mopp_section — §5.4 list-accepting + envelope shape
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_single_string_returns_list_envelope(mopp_corpus_env: Path) -> None:
    """§5.4: a single-string call returns a ListEnvelope so the response
    shape is stable across single and multi-section calls.
    """
    result = await get_mopp_section(section="1")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "UKIPO Manual of Patent Practice (MoPP)"
    assert "/guidance/manual-of-patent-practice-mopp" in result.provenance.source_url
    assert len(result.items) == 1
    item = result.items[0]
    assert "Patentability" in (item.get("title") or "")
    assert "html" in item
    assert "text" in item
    assert "MoPP" in result.summary


@pytest.mark.asyncio
async def test_get_list_preserves_order(mopp_corpus_env: Path) -> None:
    refs = ["1", "4A", "14"]
    result = await get_mopp_section(section=refs)

    assert isinstance(result, ListEnvelope)
    titles = [item.get("title") or "" for item in result.items]
    assert "Patentability" in titles[0]
    assert "treatment" in titles[1].lower()
    assert titles[2].startswith("Section 14")
    assert "Fetched 3" in result.summary
    for ref in refs:
        assert ref in result.summary
    # Multi-record path is the collection root, not a specific record.
    assert result.provenance.source_url.endswith("/guidance/manual-of-patent-practice-mopp")


@pytest.mark.asyncio
async def test_get_provenance_carries_corpus_fields(mopp_corpus_env: Path) -> None:
    result = await get_mopp_section(section="1")

    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


@pytest.mark.asyncio
async def test_no_batch_tool_present() -> None:
    """§5.4 forbids batch_* tools — list-accepting get_* replaces them."""
    from patent_client_agents.mcp.tools import ukipo_mopp as mod

    assert not hasattr(mod, "batch_get_mopp_section")
    assert not hasattr(mod, "batch_mopp_section")
