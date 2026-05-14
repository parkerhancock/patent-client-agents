"""Tests for the corpus-backed MoppClient."""

from __future__ import annotations

import pytest

from patent_client_agents.ukipo_mopp import MoppClient
from patent_client_agents.ukipo_mopp.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(mopp_corpus_path, monkeypatch):
    monkeypatch.setenv("MOPP_CORPUS_PATH", str(mopp_corpus_path))


class TestGetSection:
    async def test_by_section_number(self) -> None:
        async with MoppClient() as c:
            sec = await c.get_section("1")
        assert "Patentability" in sec.title
        assert "novelty" in sec.text

    async def test_by_alphanumeric_section_number(self) -> None:
        async with MoppClient() as c:
            sec = await c.get_section("4A")
        assert "treatment" in sec.title.lower()

    async def test_by_bare_slug(self) -> None:
        async with MoppClient() as c:
            sec = await c.get_section("section-14-the-application")
        assert "application" in sec.title.lower()

    async def test_by_relative_path(self) -> None:
        async with MoppClient() as c:
            sec = await c.get_section(
                "/guidance/manual-of-patent-practice-mopp/section-14-the-application"
            )
        assert sec.title.startswith("Section 14")

    async def test_unknown_section_raises(self) -> None:
        async with MoppClient() as c:
            with pytest.raises(ValueError, match="Could not find"):
                await c.get_section("999")


class TestSearch:
    async def test_finds_matching_section_phrase(self) -> None:
        # Default syntax is "adj" (phrase). Use a phrase that literally
        # appears in the fixture body.
        async with MoppClient() as c:
            r = await c.search("methods of treatment")
        assert r.hits
        slugs = [h.href for h in r.hits]
        assert "-section-4a-methods-of-treatment-or-diagnosis" in slugs

    async def test_finds_matching_section_and(self) -> None:
        # AND syntax — words can appear anywhere.
        async with MoppClient() as c:
            r = await c.search("treatment diagnosis", syntax="and")
        assert r.hits
        slugs = [h.href for h in r.hits]
        assert "-section-4a-methods-of-treatment-or-diagnosis" in slugs

    async def test_returns_no_hits_for_unmatched_query(self) -> None:
        async with MoppClient() as c:
            r = await c.search("zzzzz nothing matches")
        assert r.hits == []
        assert r.has_more is False

    async def test_paginates(self) -> None:
        async with MoppClient() as c:
            r1 = await c.search("section", per_page=1, page=1)
            r2 = await c.search("section", per_page=1, page=2)
        assert r1.hits and r2.hits
        assert r1.hits[0].href != r2.hits[0].href

    async def test_search_returns_govuk_result_urls(self) -> None:
        async with MoppClient() as c:
            r = await c.search("application")
        assert r.hits
        assert all(
            h.result_url.startswith("https://www.gov.uk/guidance/manual-of-patent-practice-mopp/")
            for h in r.hits
        )


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("MOPP_CORPUS_PATH", str(tmp_path / "does-not-exist.db"))
        async with MoppClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("1")
