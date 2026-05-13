"""Tests for the corpus-backed TmepClient.

Mirrors ``tests/mpep/test_client.py``. No live HTTP — the runtime
reads from a fixture SQLite/FTS5 corpus built in ``conftest.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.tmep.client import TmepClient
from patent_client_agents.tmep.corpus import CorpusUnavailable
from patent_client_agents.tmep.models import TmepSearchResponse, TmepSection, TmepVersion


class TestTmepClientInit:
    def test_constructs_without_opening_corpus(self) -> None:
        client = TmepClient(corpus_path="/nonexistent.db")
        assert client._db is None

    @pytest.mark.asyncio
    async def test_missing_corpus_raises_on_first_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("TMEP_CORPUS_PATH", raising=False)
        absent = tmp_path / "does-not-exist.db"
        client = TmepClient(corpus_path=absent)
        with pytest.raises(CorpusUnavailable):
            await client.search("anything")


class TestTmepClientLookups:
    @pytest.mark.asyncio
    async def test_get_section_by_number(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            section = await client.get_section("1207")
        assert isinstance(section, TmepSection)
        assert "Likelihood of Confusion" in section.title

    @pytest.mark.asyncio
    async def test_get_section_with_subsection_parens(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            section = await client.get_section("1209.03(u)")
        assert section.title == "Punctuation"

    @pytest.mark.asyncio
    async def test_get_section_by_href(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            section = await client.get_section("TMEP-1200d1e_1207.html")
        assert "Likelihood of Confusion" in section.title

    @pytest.mark.asyncio
    async def test_get_section_not_found_raises(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            with pytest.raises(ValueError):
                await client.get_section("9999")

    @pytest.mark.asyncio
    async def test_resolve_section_href_hits(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            href = await client.resolve_section_href("1207")
        assert href == "TMEP-1200d1e_1207.html"

    @pytest.mark.asyncio
    async def test_resolve_section_href_misses(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            href = await client.resolve_section_href("9999")
        assert href is None


class TestTmepClientSearch:
    @pytest.mark.asyncio
    async def test_search_phrase_hits_likelihood_of_confusion(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            results = await client.search("likelihood of confusion")
        assert isinstance(results, TmepSearchResponse)
        assert results.hits, "expected at least one hit"
        titles = [hit.title for hit in results.hits]
        assert any("Likelihood of Confusion" in t for t in titles)

    @pytest.mark.asyncio
    async def test_search_or_syntax_widens(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            adj = await client.search("confusion specimen", syntax="adj")
            or_ = await client.search("confusion specimen", syntax="or")
        assert len(or_.hits) >= len(adj.hits)

    @pytest.mark.asyncio
    async def test_search_pagination_and_has_more(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            page1 = await client.search("mark", per_page=2, page=1)
            page2 = await client.search("mark", per_page=2, page=2)
        assert page1.has_more is True
        page1_hrefs = {h.href for h in page1.hits}
        page2_hrefs = {h.href for h in page2.hits}
        assert page1_hrefs.isdisjoint(page2_hrefs)

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty_response(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            results = await client.search("   ")
        assert results.hits == []
        assert results.has_more is False


class TestTmepClientVersions:
    @pytest.mark.asyncio
    async def test_list_versions_single_snapshot(self, tmep_corpus_env: Path) -> None:
        async with TmepClient() as client:
            versions = await client.list_versions()
        assert len(versions) == 1
        v = versions[0]
        assert isinstance(v, TmepVersion)
        assert v.value == "current"
        assert v.current is True
        assert "snapshot" in v.label
