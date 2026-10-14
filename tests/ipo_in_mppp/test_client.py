"""Tests for the corpus-backed IPO India MpppClient."""

from __future__ import annotations

import pytest

from patent_client_agents.ipo_in_mppp import MpppClient
from patent_client_agents.ipo_in_mppp.client import normalize_section_reference
from patent_client_agents.ipo_in_mppp.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(ipo_in_mppp_corpus_path, monkeypatch):
    monkeypatch.setenv("IPO_IN_MPPP_CORPUS_PATH", str(ipo_in_mppp_corpus_path))


class TestNormalize:
    def test_bare_number(self) -> None:
        assert normalize_section_reference("04.05.01") == "04.05.01"

    def test_chapter_prefix(self) -> None:
        assert normalize_section_reference("Chapter 04.05.01") == "04.05.01"

    def test_full_citation(self) -> None:
        assert normalize_section_reference("MPPP Chapter 04.05.01") == "04.05.01"

    def test_short_ch_prefix(self) -> None:
        assert normalize_section_reference("Ch 04.05.01") == "04.05.01"
        assert normalize_section_reference("Ch. 04.05.01") == "04.05.01"

    def test_top_level(self) -> None:
        assert normalize_section_reference("04") == "04"

    def test_unparseable_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            normalize_section_reference("not a section")


class TestGetSection:
    async def test_by_bare_number(self) -> None:
        async with MpppClient() as c:
            sec = await c.get_section("04.05.01")
        assert sec.section_number == "04.05.01"
        assert sec.title is not None

    async def test_by_full_citation(self) -> None:
        async with MpppClient() as c:
            sec = await c.get_section("MPPP Chapter 04.05.02")
        assert sec.section_number == "04.05.02"
        assert "Novartis" in sec.text

    async def test_unknown_raises(self) -> None:
        async with MpppClient() as c:
            with pytest.raises(ValueError, match="not found"):
                await c.get_section("99.99.99")


class TestSearch:
    async def test_finds_phrase(self) -> None:
        async with MpppClient() as c:
            r = await c.search("first examination report", syntax="adj")
        assert r.hits

    async def test_and_default(self) -> None:
        async with MpppClient() as c:
            r = await c.search("compulsory licensing")
        assert r.hits

    async def test_or_syntax(self) -> None:
        async with MpppClient() as c:
            r = await c.search("Form 27 zzzzzz", syntax="or")
        assert r.hits

    async def test_empty_query_returns_empty(self) -> None:
        async with MpppClient() as c:
            r = await c.search("   ")
        assert r.hits == []
        assert r.has_more is False

    async def test_outline_sort(self) -> None:
        async with MpppClient() as c:
            r = await c.search("section", sort="outline")
        nums = [h.section_number for h in r.hits]
        assert nums == [
            "03.04",
            "04.05",
            "04.05.01",
            "04.05.02",
            "04.06",
            "05.03",
            "05.04",
            "06.02",
            "07.02",
            "08.04",
        ]

    async def test_pagination(self) -> None:
        async with MpppClient() as c:
            r1 = await c.search("section", per_page=2, page=1)
            r2 = await c.search("section", per_page=2, page=2)
        first = {h.section_number for h in r1.hits}
        second = {h.section_number for h in r2.hits}
        assert first & second == set()


class TestMeta:
    async def test_meta_has_source_version(self) -> None:
        async with MpppClient() as c:
            meta = await c.meta()
        assert meta.schema_version == 1
        assert meta.source_version == "v3.0 (2019)"
        assert meta.section_count > 0


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("IPO_IN_MPPP_CORPUS_PATH", str(tmp_path / "no.db"))
        async with MpppClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("04.05.01")
