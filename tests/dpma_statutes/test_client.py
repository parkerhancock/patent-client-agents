"""Tests for the corpus-backed DpmaStatutesClient."""

from __future__ import annotations

import pytest

from patent_client_agents.dpma_statutes import DpmaStatutesClient
from patent_client_agents.dpma_statutes.client import parse_citation
from patent_client_agents.dpma_statutes.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(dpma_statutes_corpus_path, monkeypatch):
    monkeypatch.setenv("DPMA_STATUTES_CORPUS_PATH", str(dpma_statutes_corpus_path))


class TestParseCitation:
    def test_paragraph_with_statute(self) -> None:
        num, statute = parse_citation("§ 139 PatG")
        assert num == "139"
        assert statute == "PatG"

    def test_paragraph_with_long_form_alias(self) -> None:
        num, statute = parse_citation("§ 14 Markengesetz")
        assert num == "14"
        assert statute == "MarkenG"

    def test_section_word_with_statute(self) -> None:
        num, statute = parse_citation("Section 14 MarkenG")
        assert num == "14"
        assert statute == "MarkenG"

    def test_abbreviated_section(self) -> None:
        num, statute = parse_citation("S. 139 PatG")
        assert num == "139"
        assert statute == "PatG"

    def test_section_of_the_form(self) -> None:
        num, statute = parse_citation("Section 5 of the GeschGehG")
        assert num == "5"
        assert statute == "GeschGehG"

    def test_bare_number(self) -> None:
        num, statute = parse_citation("139")
        assert num == "139"
        assert statute is None

    def test_english_alias_resolution(self) -> None:
        _, statute = parse_citation("§ 1 Patent Act")
        assert statute == "PatG"

    def test_unknown_statute_passes_through(self) -> None:
        # Unknown labels are passed through (not mapped) so downstream
        # filtering can cleanly return no hits.
        _, statute = parse_citation("§ 1 NotARealAct")
        assert statute == "NotARealAct"

    def test_unparseable_raises(self) -> None:
        with pytest.raises(ValueError, match="Could not parse citation"):
            parse_citation("totally not a citation")


class TestGetSection:
    async def test_by_citation_with_statute(self) -> None:
        async with DpmaStatutesClient() as c:
            sec = await c.get_section_by_citation("§ 139 PatG")
        assert sec.statute == "PatG"
        assert sec.section == "139"
        assert "Unterlassung" in (sec.title or "")

    async def test_by_number_with_explicit_statute(self) -> None:
        async with DpmaStatutesClient() as c:
            sec = await c.get_section("14", statute="MarkenG")
        assert sec.statute == "MarkenG"
        assert sec.section == "14"

    async def test_by_number_alone_when_unique(self) -> None:
        # Section 139 is only in PatG in the seed
        async with DpmaStatutesClient() as c:
            sec = await c.get_section("139")
        assert sec.statute == "PatG"
        assert sec.section == "139"

    async def test_by_number_alone_ambiguous_raises(self) -> None:
        # Section 1 exists in PatG, GebrMG, DesignG, UrhG, GeschGehG
        async with DpmaStatutesClient() as c:
            with pytest.raises(ValueError, match="ambiguous"):
                await c.get_section("1")

    async def test_unknown_section_raises(self) -> None:
        async with DpmaStatutesClient() as c:
            with pytest.raises(ValueError, match="not found"):
                await c.get_section("9999", statute="PatG")

    async def test_unknown_section_no_statute_raises(self) -> None:
        async with DpmaStatutesClient() as c:
            with pytest.raises(ValueError, match="not found in any bundled"):
                await c.get_section("9999")

    async def test_get_section_long_form_statute_alias(self) -> None:
        async with DpmaStatutesClient() as c:
            sec = await c.get_section("139", statute="patentgesetz")
        assert sec.statute == "PatG"


class TestSearch:
    async def test_finds_phrase_adj(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("erfinderischen Tätigkeit", syntax="adj")
        assert r.hits

    async def test_and_syntax(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("Patente Erfindungen", syntax="and")
        assert r.hits
        assert any(h.statute == "PatG" for h in r.hits)

    async def test_or_syntax(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("Erfindung Marke", syntax="or")
        assert r.hits

    async def test_exact_syntax(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("ausschließliches Recht", syntax="exact")
        assert r.hits
        assert any(h.statute == "MarkenG" for h in r.hits)

    async def test_statute_filter(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("Anmeldung", statute="MarkenG")
        for h in r.hits:
            assert h.statute == "MarkenG"
        assert r.statute == "MarkenG"

    async def test_statute_alias(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("Geschäftsgeheimnis", statute="trade secrets act")
        assert r.statute == "GeschGehG"

    async def test_outline_sort(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("oder", sort="outline", per_page=5)
        # Ordered by (statute, section); relevance order differs for this query.
        assert [(h.statute, h.section) for h in r.hits] == [
            ("DesignG", "1"),
            ("GeschGehG", "2"),
            ("PatG", "3"),
            ("UrhG", "97"),
        ]

    async def test_empty_query_returns_empty(self) -> None:
        async with DpmaStatutesClient() as c:
            r = await c.search("   ")
        assert r.hits == []
        assert r.has_more is False

    async def test_pagination(self) -> None:
        async with DpmaStatutesClient() as c:
            r1 = await c.search("die", per_page=2, page=1, syntax="or")
            r2 = await c.search("die", per_page=2, page=2, syntax="or")
        assert r1.hits and r2.hits
        first_ids = {(h.statute, h.section) for h in r1.hits}
        second_ids = {(h.statute, h.section) for h in r2.hits}
        assert first_ids & second_ids == set()


class TestMetaAndStatutes:
    async def test_list_statutes(self) -> None:
        async with DpmaStatutesClient() as c:
            statutes = await c.list_statutes()
        # All six bundled Acts present
        assert "PatG" in statutes
        assert "MarkenG" in statutes
        assert "GebrMG" in statutes
        assert "DesignG" in statutes
        assert "UrhG" in statutes
        assert "GeschGehG" in statutes

    async def test_meta(self) -> None:
        async with DpmaStatutesClient() as c:
            meta = await c.meta()
        assert meta.schema_version >= 1
        assert meta.snapshot_date is not None
        assert meta.section_count > 0


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("DPMA_STATUTES_CORPUS_PATH", str(tmp_path / "does-not-exist.db"))
        async with DpmaStatutesClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("139", statute="PatG")
