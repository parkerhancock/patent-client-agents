"""Shared search/get bodies for the bundled-corpus MCP tools."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from mcp_data_core.exceptions import NotFoundError
from patent_client_agents.mcp.tools import epc as epc_tools
from patent_client_agents.mcp.tools import ilpo as ilpo_tools
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_provenance,
    corpus_search,
    hits_summary,
    truncate,
)

SYNCED = datetime(2026, 5, 1, tzinfo=UTC)


class Counter:
    """Fake corpus status function and client class that count their use."""

    def __init__(self, hits: list[dict] | None = None, has_more: bool = False) -> None:
        self.status_calls = 0
        self.opens = 0
        self.hits = hits or []
        self.has_more = has_more
        self.records: dict[str, dict] = {}

    def status(self) -> dict[str, Any]:
        self.status_calls += 1
        return {"corpus_version": "v9", "corpus_synced_at": SYNCED}

    def client_cls(self) -> Any:
        counter = self

        class _Client:
            async def __aenter__(self) -> _Client:
                counter.opens += 1
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

            async def search(self, **_: Any) -> Any:
                return SimpleNamespace(hits=counter.hits, has_more=counter.has_more)

            async def get_section(self, ref: str) -> dict:
                if ref not in counter.records:
                    raise NotFoundError(ref)
                return counter.records[ref]

        return _Client


def test_truncate_and_hits_summary() -> None:
    assert truncate("short", 10) == "short"
    assert truncate("abcdefghij", 5) == "abcd…"
    assert hits_summary("X — `q`", 1, False) == "X — `q`: 1 hit."
    assert (
        hits_summary("X — `q`", 2, True, " (corpus v1)")
        == "X — `q`: 2 hits (corpus v1) (more available)."
    )


def test_corpus_provenance_carries_corpus_fields() -> None:
    prov = corpus_provenance(
        {"corpus_version": "v9", "corpus_synced_at": SYNCED},
        source_url="https://example.test/a",
        source_name="Example",
    )
    assert prov.source_url == "https://example.test/a"
    assert prov.corpus_version == "v9"
    assert prov.corpus_synced_at == SYNCED


@pytest.mark.parametrize("full", [False, True])
async def test_corpus_search_reads_status_once(full: bool) -> None:
    counter = Counter(hits=[{"title": "T", "snippet": "s"}], has_more=True)

    env = await corpus_search(
        counter.client_cls(),
        lambda client: client.search(query="q"),
        corpus_status=counter.status,
        project=None if full else (lambda hit: {"title": hit["title"]}),
        summary=lambda response, items, version: hits_summary(
            f"X ({version}) — `q`", len(items), response.has_more
        ),
        source_url="https://example.test/search",
        source_name="Example",
    )

    assert counter.status_calls == 1
    assert counter.opens == 1
    assert env.items == ([{"title": "T", "snippet": "s"}] if full else [{"title": "T"}])
    assert env.summary == "X (v9) — `q`: 1 hit (more available)."
    assert env.more_available is True
    assert env.provenance.corpus_version == "v9"
    assert env.provenance.source_url == "https://example.test/search"


async def _get(counter: Counter, refs: list[str], *, single: bool, missing: Any) -> Any:
    async def fetch_one(client: Any, ref: str) -> dict:
        return await client.get_section(ref)

    return await corpus_get(
        counter.client_cls(),
        refs,
        fetch_one,
        single=single,
        corpus_status=counter.status,
        summarize_one=lambda record, version: f"**{record['id']}** ({version})",
        missing=missing,
        noun_plural=lambda version: f"sections ({version})",
        source_url=lambda items, version: f"https://example.test/{len(items)}/{version}",
        source_name="Example",
    )


async def test_corpus_get_single_found() -> None:
    counter = Counter()
    counter.records = {"a": {"id": "a"}}

    env = await _get(counter, ["a"], single=True, missing=lambda ref: f"{ref} missing")

    assert counter.status_calls == 1
    assert counter.opens == 1
    assert env.summary == "**a** (v9)"
    assert env.items == [{"id": "a"}]
    assert env.not_found == []
    assert env.provenance.source_url == "https://example.test/1/v9"


async def test_corpus_get_list_of_one_missing() -> None:
    counter = Counter()

    env = await _get(counter, ["zz"], single=False, missing=lambda ref: f"{ref} missing")
    assert env.summary == "zz missing"
    assert env.not_found == ["zz"]

    # Without a ``missing`` form the multi-ref summary is used.
    env = await _get(counter, ["zz"], single=False, missing=None)
    assert env.summary == "Fetched 0 of 1 sections (v9). Not found: zz."


async def test_corpus_get_many_keeps_order_and_reports_missing() -> None:
    counter = Counter()
    counter.records = {"a": {"id": "a"}, "b": {"id": "b"}}

    env = await _get(counter, ["b", "zz", "a"], single=False, missing=None)

    assert counter.status_calls == 1
    assert [item["id"] for item in env.items] == ["b", "a"]
    assert env.not_found == ["zz"]
    assert env.summary == "Fetched 2 of 3 sections (v9). Not found: zz."


async def test_corpus_get_single_string_not_found_propagates() -> None:
    counter = Counter()
    with pytest.raises(NotFoundError):
        await _get(counter, ["zz"], single=True, missing=lambda ref: ref)
    assert counter.status_calls == 0


async def test_tool_modules_read_status_once_per_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patched module attributes are picked up at call time; one status read per call."""
    counter = Counter(
        hits=[{"title": "Article 54", "path": ["Article 54"], "snippet": "s", "href": "a54"}]
    )
    counter.records = {"Article 54": {"title": "Article 54", "href": "a54"}}
    monkeypatch.setattr(epc_tools, "EpcClient", counter.client_cls())
    monkeypatch.setattr(epc_tools, "get_corpus_status", counter.status)

    env = await epc_tools.search_epc(query="novelty")
    assert (counter.opens, counter.status_calls) == (1, 1)
    assert env.summary == "EPC (v9) — `novelty`: 1 hit."

    env = await epc_tools.get_epc_section(section="Article 54")
    assert (counter.opens, counter.status_calls) == (2, 2)
    assert env.provenance.source_url == "https://www.epo.org/en/legal/epc/v9/a54.html"
    assert env.provenance.corpus_version == "v9"


async def test_ilpo_get_uses_patched_client(monkeypatch: pytest.MonkeyPatch) -> None:
    counter = Counter()

    class _Client(counter.client_cls()):  # type: ignore[misc]
        async def get_section_by_citation(self, citation: str) -> dict | None:
            return None

    monkeypatch.setattr(ilpo_tools, "IlpoStatutesClient", _Client)
    monkeypatch.setattr(ilpo_tools, "get_corpus_status", counter.status)

    env = await ilpo_tools.get_ilpo_section(citation=["Patents Law s. 1"])

    assert (counter.opens, counter.status_calls) == (1, 1)
    assert env.summary == "ILPO Israel section 'Patents Law s. 1' — not found."
