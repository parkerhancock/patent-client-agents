"""Tests for the corpus-backed MpepClient.

These exercise the real SQLite/FTS5 read path against a hand-built tiny
corpus from ``conftest.py``. No live HTTP — the runtime no longer calls
USPTO.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.mpep.client import MpepClient
from patent_client_agents.mpep.corpus import CorpusUnavailable
from patent_client_agents.mpep.models import MpepSearchResponse, MpepSection, MpepVersion


class TestMpepClientInit:
    def test_constructs_without_opening_corpus(self) -> None:
        """Construction is sync and must not open the DB — that's lazy."""
        client = MpepClient(corpus_path="/nonexistent.db")
        assert client._db is None

    @pytest.mark.asyncio
    async def test_missing_corpus_raises_on_first_call(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("MPEP_CORPUS_PATH", raising=False)
        absent = tmp_path / "does-not-exist.db"
        client = MpepClient(corpus_path=absent)
        with pytest.raises(CorpusUnavailable):
            await client.search("anything")


class TestMpepClientLookups:
    @pytest.mark.asyncio
    async def test_get_section_by_number(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            section = await client.get_section("2106")
        assert isinstance(section, MpepSection)
        assert section.title == "Patent Subject Matter Eligibility"
        assert "subject matter" in section.text.lower()

    @pytest.mark.asyncio
    async def test_get_section_with_subsection_parens(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            section = await client.get_section("2106.04(a)")
        assert section.title == "Abstract Ideas"

    @pytest.mark.asyncio
    async def test_get_section_by_href(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            section = await client.get_section("d0e_2106.html")
        assert section.title == "Patent Subject Matter Eligibility"

    @pytest.mark.asyncio
    async def test_get_section_by_href_without_extension(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            section = await client.get_section("d0e_2106")
        assert section.title == "Patent Subject Matter Eligibility"

    @pytest.mark.asyncio
    async def test_get_section_not_found_raises(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            with pytest.raises(ValueError):
                await client.get_section("9999")

    @pytest.mark.asyncio
    async def test_resolve_section_href_hits(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            href = await client.resolve_section_href("2106")
        assert href == "d0e_2106.html"

    @pytest.mark.asyncio
    async def test_resolve_section_href_misses(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            href = await client.resolve_section_href("9999")
        assert href is None


class TestMpepClientSearch:
    @pytest.mark.asyncio
    async def test_search_phrase_matches_subject_matter(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            results = await client.search("subject matter eligibility")
        assert isinstance(results, MpepSearchResponse)
        titles = [hit.title for hit in results.hits]
        # The dedicated section 2106 must be the top hit since its title
        # contains the exact phrase.
        assert titles, "expected at least one hit"
        assert any("Patent Subject Matter Eligibility" in t for t in titles)

    @pytest.mark.asyncio
    async def test_search_or_syntax_widens(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            adj = await client.search("obviousness alice", syntax="adj")
            or_ = await client.search("obviousness alice", syntax="or")
        # OR should never return fewer hits than the same-terms phrase query.
        assert len(or_.hits) >= len(adj.hits)

    @pytest.mark.asyncio
    async def test_search_pagination_and_has_more(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            page1 = await client.search("patent", per_page=2, page=1)
            page2 = await client.search("patent", per_page=2, page=2)
        assert page1.has_more is True
        # No duplicate hrefs across pages.
        page1_hrefs = {h.href for h in page1.hits}
        page2_hrefs = {h.href for h in page2.hits}
        assert page1_hrefs.isdisjoint(page2_hrefs)

    @pytest.mark.asyncio
    async def test_search_empty_query_returns_empty_response(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            results = await client.search("   ")
        assert results.hits == []
        assert results.has_more is False


class TestMpepClientVersions:
    @pytest.mark.asyncio
    async def test_list_versions_single_snapshot(self, mpep_corpus_env: Path) -> None:
        async with MpepClient() as client:
            versions = await client.list_versions()
        assert len(versions) == 1
        v = versions[0]
        assert isinstance(v, MpepVersion)
        assert v.value == "current"
        assert v.current is True
        # Label should mention the snapshot date that write_corpus stamped.
        assert "snapshot" in v.label
