"""Envelope-shape tests for the Taiwan Trade Secrets Act MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + ``full=True`` opt-in),
and §4 (substantive-law Provenance carries ``corpus_synced_at`` +
``corpus_version`` from the bundled corpus).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.tw_trade_secrets import (
    get_tw_trade_secrets_section,
    search_tw_trade_secrets,
)

# ──────────────────────────────────────────────────────────────────────
# search_tw_trade_secrets — §5.9, §5.5, §4
# ──────────────────────────────────────────────────────────────────────


async def test_search_returns_lean_list_envelope_by_default(
    tw_trade_secrets_corpus_env: Path,
) -> None:
    result = await search_tw_trade_secrets(query="damages")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "Taiwan — Trade Secrets Act (EN translation)"
    assert len(result.items) >= 1
    assert set(result.items[0].keys()) == {
        "section",
        "title",
        "snippet",
    }
    assert "damages" in result.summary
    assert "TW Trade Secrets Act" in result.summary


async def test_search_full_true_returns_upstream_shape(
    tw_trade_secrets_corpus_env: Path,
) -> None:
    result = await search_tw_trade_secrets(query="damages", full=True)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) >= 1
    # Full mode preserves the rank/snippet shape
    assert "rank" in result.items[0]


async def test_search_provenance_carries_corpus_fields(
    tw_trade_secrets_corpus_env: Path,
) -> None:
    result = await search_tw_trade_secrets(query="trade")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_search_limit_validation(tw_trade_secrets_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_tw_trade_secrets(query="x", limit=0)
    with pytest.raises(ValidationError, match="between 1 and 100"):
        await search_tw_trade_secrets(query="x", limit=999)


async def test_search_pagination_summary(tw_trade_secrets_corpus_env: Path) -> None:
    result = await search_tw_trade_secrets(query="the", limit=1, offset=0, syntax="or")
    # With a small per-page, there should be more available
    assert result.more_available is True
    assert "more available" in result.summary


async def test_search_summary_zero_hits(tw_trade_secrets_corpus_env: Path) -> None:
    result = await search_tw_trade_secrets(query="zzzzzzzznotaword")
    assert result.items == []
    assert "0 hit" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_tw_trade_secrets_section — §5.4 list-accepting + envelope
# ──────────────────────────────────────────────────────────────────────


async def test_get_single_citation_returns_list_envelope(
    tw_trade_secrets_corpus_env: Path,
) -> None:
    result = await get_tw_trade_secrets_section(citation="Art. 2 Trade Secrets Act")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "Taiwan — Trade Secrets Act (EN translation)"
    assert len(result.items) == 1
    item = result.items[0]
    assert item["section"] == "2"
    assert "Trade Secrets Act Art. 2" in result.summary


async def test_get_list_preserves_order(tw_trade_secrets_corpus_env: Path) -> None:
    refs = [
        "Art. 2 Trade Secrets Act",
        "Art. 13 Trade Secrets Act",
        "Art. 13-1",
    ]
    result = await get_tw_trade_secrets_section(citation=refs)
    assert isinstance(result, ListEnvelope)
    sections = [i["section"] for i in result.items]
    assert sections == ["2", "13", "13-1"]
    assert "Fetched 3" in result.summary


async def test_get_bare_number_citation(tw_trade_secrets_corpus_env: Path) -> None:
    result = await get_tw_trade_secrets_section(citation="13-1")
    assert result.items[0]["section"] == "13-1"


async def test_get_provenance_carries_corpus_fields(
    tw_trade_secrets_corpus_env: Path,
) -> None:
    result = await get_tw_trade_secrets_section(citation="Art. 2")
    assert result.provenance.corpus_version is not None
    assert result.provenance.corpus_version.startswith("snapshot-")
    assert isinstance(result.provenance.corpus_synced_at, datetime)


async def test_get_empty_list_raises(tw_trade_secrets_corpus_env: Path) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await get_tw_trade_secrets_section(citation=[])


async def test_no_batch_tool_present() -> None:
    from patent_client_agents.mcp.tools import tw_trade_secrets as mod

    assert not hasattr(mod, "batch_get_tw_trade_secrets_section")
    assert not hasattr(mod, "batch_tw_trade_secrets_section")
