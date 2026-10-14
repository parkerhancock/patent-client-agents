"""Tests for the corpus-backed IpoInStatutesClient."""

from __future__ import annotations

import pytest

from patent_client_agents.ipo_in_statutes import IpoInStatutesClient
from patent_client_agents.ipo_in_statutes.client import parse_citation
from patent_client_agents.ipo_in_statutes.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(ipo_in_statutes_corpus_path, monkeypatch):
    monkeypatch.setenv("IPO_IN_STATUTES_CORPUS_PATH", str(ipo_in_statutes_corpus_path))


class TestParseCitation:
    def test_section_with_subparagraph_and_statute(self) -> None:
        num, statute = parse_citation("Section 3(d) Patents Act")
        assert num == "3(d)"
        assert statute == "Patents Act"

    def test_section_with_subsection(self) -> None:
        num, statute = parse_citation("Section 25(2) Patents Act")
        assert num == "25(2)"
        assert statute == "Patents Act"

    def test_section_with_of_the(self) -> None:
        num, statute = parse_citation("Section 84 of the Patents Act")
        assert num == "84"
        assert statute == "Patents Act"

    def test_rule(self) -> None:
        num, statute = parse_citation("Rule 71 Patent Rules")
        assert num == "71"
        assert statute == "Patent Rules"

    def test_abbreviated_section(self) -> None:
        num, statute = parse_citation("S. 84")
        assert num == "84"
        assert statute is None

    def test_bare_number(self) -> None:
        num, statute = parse_citation("107A")
        assert num == "107A"
        assert statute is None

    def test_alias_resolution(self) -> None:
        _, statute = parse_citation("Section 9 trade marks act 1999")
        assert statute == "Trade Marks Act"

    def test_unparseable_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse citation"):
            parse_citation("totally not a citation")


class TestGetSection:
    async def test_by_citation_with_subparagraph(self) -> None:
        async with IpoInStatutesClient() as c:
            sec = await c.get_section_by_citation("Section 3(d) Patents Act")
        assert sec.statute_name == "Patents Act"
        assert sec.section_number == "3(d)"
        assert "evergreening" in (sec.title or "").lower()
        assert "Novartis" in sec.text

    async def test_by_number_with_explicit_statute(self) -> None:
        async with IpoInStatutesClient() as c:
            sec = await c.get_section("84", statute_name="Patents Act")
        assert sec.statute_name == "Patents Act"
        assert sec.title is not None
        assert "compulsory" in sec.title.lower()

    async def test_by_number_alone_when_unique(self) -> None:
        async with IpoInStatutesClient() as c:
            sec = await c.get_section("107A")
        assert sec.statute_name == "Patents Act"
        assert sec.section_number == "107A"

    async def test_by_number_alone_ambiguous_raises(self) -> None:
        # Section 2 exists in both Patents Act and Trade Marks Act
        async with IpoInStatutesClient() as c:
            with pytest.raises(ValueError, match="ambiguous"):
                await c.get_section("2")

    async def test_unknown_section_raises(self) -> None:
        async with IpoInStatutesClient() as c:
            with pytest.raises(ValueError, match="not found"):
                await c.get_section("999", statute_name="Patents Act")

    async def test_unknown_section_no_statute_raises(self) -> None:
        async with IpoInStatutesClient() as c:
            with pytest.raises(ValueError, match="not found in any bundled"):
                await c.get_section("9999")

    async def test_get_section_alias(self) -> None:
        async with IpoInStatutesClient() as c:
            sec = await c.get_section("3(d)", statute_name="patents act")
        assert sec.statute_name == "Patents Act"


class TestSearch:
    async def test_finds_phrase(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("compulsory licensing", syntax="adj")
        assert r.hits
        assert any(h.section_number == "84" for h in r.hits)

    async def test_and_syntax(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("efficacy enhancement", syntax="and")
        assert r.hits
        assert any(h.section_number == "3(d)" for h in r.hits)

    async def test_or_syntax(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("efficacy congenital", syntax="or")
        # "efficacy" alone matches §3(d)
        assert r.hits

    async def test_statute_filter(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("fair dealing", statute_name="Copyright Act")
        for h in r.hits:
            assert h.statute_name == "Copyright Act"

    async def test_statute_alias(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("dilution", statute_name="trademarks")
        # may or may not match; the test confirms alias resolved to canonical
        assert r.statute_name == "Trade Marks Act"

    async def test_outline_sort(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("section", sort="outline", per_page=5)
        # outline sort returns rows in statute_name, section_number order
        assert [(h.statute_name, h.section_number) for h in r.hits] == [
            ("Copyright Act", "13"),
            ("Designs Act", "2(d)"),
            ("Patent Rules", "71"),
            ("Patents Act", "122"),
            ("Patents Act", "25(1)"),
        ]

    async def test_empty_query_returns_empty(self) -> None:
        async with IpoInStatutesClient() as c:
            r = await c.search("   ")
        assert r.hits == []
        assert r.has_more is False

    async def test_pagination(self) -> None:
        async with IpoInStatutesClient() as c:
            r1 = await c.search("section", per_page=2, page=1)
            r2 = await c.search("section", per_page=2, page=2)
        assert r1.hits and r2.hits
        # First-page hits should not match second-page hits (per_page=2)
        first_ids = {(h.statute_name, h.section_number) for h in r1.hits}
        second_ids = {(h.statute_name, h.section_number) for h in r2.hits}
        assert first_ids & second_ids == set()


class TestMetaAndStatutes:
    async def test_list_statutes(self) -> None:
        async with IpoInStatutesClient() as c:
            statutes = await c.list_statutes()
        assert "Patents Act" in statutes
        assert "Trade Marks Act" in statutes
        assert "Copyright Act" in statutes
        assert "Designs Act" in statutes

    async def test_meta(self) -> None:
        async with IpoInStatutesClient() as c:
            meta = await c.meta()
        assert meta.schema_version >= 1
        assert meta.snapshot_date is not None
        assert meta.section_count > 0


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("IPO_IN_STATUTES_CORPUS_PATH", str(tmp_path / "does-not-exist.db"))
        async with IpoInStatutesClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("3(d)", statute_name="Patents Act")
