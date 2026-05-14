"""Tests for the corpus-backed GuidelinesClient."""

from __future__ import annotations

import pytest

from patent_client_agents.epo_guidelines import GuidelinesClient
from patent_client_agents.epo_guidelines.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(guidelines_corpus_path, monkeypatch):
    monkeypatch.setenv("GUIDELINES_CORPUS_PATH", str(guidelines_corpus_path))


class TestGetSectionByCitation:
    """Various canonical citation forms all resolve to the same section."""

    @pytest.mark.parametrize(
        "citation",
        ["G-II, 3.1", "G-II 3.1", "G.II.3.1", "G_II_3_1", "g-ii-3-1"],
    )
    async def test_canonical_citation_forms(self, citation: str) -> None:
        async with GuidelinesClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "g_ii_3_1"
        assert "Discoveries" in sec.title

    async def test_chapter_only_raises_when_not_in_corpus(self) -> None:
        # Fixture has g_ii_3 and g_ii_3_1 but not g_ii — caller asking
        # for a chapter that doesn't exist as its own row gets a clear
        # ValueError, not a silent nearest-match.
        async with GuidelinesClient() as c:
            with pytest.raises(ValueError, match="Could not find"):
                await c.get_section("G-II")


class TestGetSectionBySlug:
    async def test_bare_slug(self) -> None:
        async with GuidelinesClient() as c:
            sec = await c.get_section("g_ii_3_1")
        assert sec.title.startswith("3.1")

    async def test_slug_with_html_suffix(self) -> None:
        async with GuidelinesClient() as c:
            sec = await c.get_section("g_ii_3_1.html")
        assert sec.href == "g_ii_3_1"

    async def test_full_url(self) -> None:
        async with GuidelinesClient() as c:
            sec = await c.get_section(
                "https://www.epo.org/en/legal/guidelines-epc/2024/g_ii_3_1.html"
            )
        assert sec.href == "g_ii_3_1"

    async def test_part_only_slug(self) -> None:
        async with GuidelinesClient() as c:
            sec = await c.get_section("h")
        assert "Part H" in sec.title

    async def test_unknown_section_raises(self) -> None:
        async with GuidelinesClient() as c:
            with pytest.raises(ValueError, match="Could not find"):
                await c.get_section("z_x_99_99")


class TestSearch:
    async def test_finds_matching_section_phrase(self) -> None:
        async with GuidelinesClient() as c:
            r = await c.search("Discoveries as such")
        assert r.hits
        assert r.hits[0].href == "g_ii_3_1"

    async def test_finds_matching_section_and(self) -> None:
        async with GuidelinesClient() as c:
            r = await c.search("discoveries patentability", syntax="and")
        assert r.hits

    async def test_search_returns_epo_result_urls(self) -> None:
        async with GuidelinesClient() as c:
            r = await c.search("Discoveries")
        assert r.hits
        for h in r.hits:
            assert h.result_url.startswith("https://www.epo.org/en/legal/guidelines-epc/2024/")
            assert h.result_url.endswith(".html")

    async def test_no_hits_for_unmatched(self) -> None:
        async with GuidelinesClient() as c:
            r = await c.search("zzz nothing matches")
        assert r.hits == []


class TestListVersions:
    async def test_returns_year_edition(self) -> None:
        async with GuidelinesClient() as c:
            versions = await c.list_versions()
        assert len(versions) == 1
        assert versions[0].current is True
        assert "2024" in versions[0].label


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("GUIDELINES_CORPUS_PATH", str(tmp_path / "missing.db"))
        async with GuidelinesClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("a_i")
