"""Tests for the corpus-backed LegifranceIpClient + citation parsing."""

from __future__ import annotations

import pytest

from patent_client_agents.legifrance_ip import (
    CitationParseError,
    LegifranceIpClient,
    parse_citation,
)
from patent_client_agents.legifrance_ip.client import _normalize_section
from patent_client_agents.legifrance_ip.corpus import CorpusUnavailable


@pytest.fixture(autouse=True)
def _set_corpus(legifrance_ip_corpus_path, monkeypatch):
    monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(legifrance_ip_corpus_path))


class TestParseCitation:
    def test_l_dot_form_cpi(self) -> None:
        statute, section = parse_citation("L. 611-10 CPI")
        assert statute == "CPI"
        assert section == "L611-10"

    def test_art_dot_l_dot_form(self) -> None:
        statute, section = parse_citation("Art. L. 611-10 CPI")
        assert statute == "CPI"
        assert section == "L611-10"

    def test_article_word_form(self) -> None:
        statute, section = parse_citation("Article L. 611-10 CPI")
        assert statute == "CPI"
        assert section == "L611-10"

    def test_compact_form(self) -> None:
        statute, section = parse_citation("L611-10 CPI")
        assert statute == "CPI"
        assert section == "L611-10"

    def test_code_de_commerce(self) -> None:
        statute, section = parse_citation("L. 151-1 Code de commerce")
        assert statute == "Code de commerce"
        assert section == "L151-1"

    def test_dotted_section_normalized_to_hyphen(self) -> None:
        statute, section = parse_citation("L. 611.10 CPI")
        assert statute == "CPI"
        assert section == "L611-10"

    def test_case_insensitive_statute(self) -> None:
        statute, _ = parse_citation("L. 611-10 cpi")
        assert statute == "CPI"

    def test_extra_whitespace_in_code_de_commerce(self) -> None:
        statute, _ = parse_citation("L. 151-1 code  de  commerce")
        assert statute == "Code de commerce"

    def test_unparseable_raises(self) -> None:
        with pytest.raises(CitationParseError, match="could not parse"):
            parse_citation("totally not a citation")

    def test_citation_parse_error_is_value_error(self) -> None:
        assert issubclass(CitationParseError, ValueError)


class TestNormalizeSection:
    def test_already_canonical(self) -> None:
        assert _normalize_section("L611-10") == "L611-10"

    def test_dot_separator(self) -> None:
        assert _normalize_section("L. 611-10") == "L611-10"

    def test_dot_between_digits(self) -> None:
        assert _normalize_section("L 611.10") == "L611-10"


class TestGetSection:
    async def test_by_citation_cpi(self) -> None:
        async with LegifranceIpClient() as c:
            sec = await c.get_section("L. 611-10 CPI")
        assert sec.statute == "CPI"
        assert sec.section == "L611-10"
        assert sec.text and sec.title

    async def test_by_citation_code_de_commerce(self) -> None:
        async with LegifranceIpClient() as c:
            sec = await c.get_section("Art. L. 151-1 Code de commerce")
        assert sec.statute == "Code de commerce"
        assert sec.section == "L151-1"

    async def test_unknown_article_raises(self) -> None:
        async with LegifranceIpClient() as c:
            with pytest.raises(ValueError, match="could not find"):
                await c.get_section("L. 999-99 CPI")

    async def test_invalid_citation_raises(self) -> None:
        async with LegifranceIpClient() as c:
            with pytest.raises(CitationParseError):
                await c.get_section("garbage")

    async def test_get_by_section_number(self) -> None:
        async with LegifranceIpClient() as c:
            sec = await c.get_by_section_number("CPI", "L611-10")
        assert sec.statute == "CPI"

    async def test_get_by_section_number_normalizes(self) -> None:
        async with LegifranceIpClient() as c:
            sec = await c.get_by_section_number("CPI", "L. 611-10")
        assert sec.section == "L611-10"

    async def test_get_by_section_number_missing_raises(self) -> None:
        async with LegifranceIpClient() as c:
            with pytest.raises(ValueError, match="could not find"):
                await c.get_by_section_number("CPI", "L999-99")


class TestSearch:
    async def test_basic_query(self) -> None:
        async with LegifranceIpClient() as c:
            r = await c.search("brevetabilité")
        assert r.hits
        assert r.page == 1
        assert any(h.section == "L611-10" for h in r.hits)

    async def test_diacritics_fold(self) -> None:
        async with LegifranceIpClient() as c:
            r = await c.search("brevetabilite")
        assert r.hits

    async def test_statute_filter(self) -> None:
        async with LegifranceIpClient() as c:
            r = await c.search("secret", statute="Code de commerce")
        for hit in r.hits:
            assert hit.statute == "Code de commerce"

    async def test_pagination_has_more(self) -> None:
        async with LegifranceIpClient() as c:
            r = await c.search("invention", per_page=1, page=1)
        assert r.per_page == 1

    async def test_pagination_second_page(self) -> None:
        async with LegifranceIpClient() as c:
            r1 = await c.search("article", per_page=1, page=1)
            r2 = await c.search("article", per_page=1, page=2)
        # When both pages have hits, they should differ.
        if r1.hits and r2.hits:
            assert (r1.hits[0].statute, r1.hits[0].section) != (
                r2.hits[0].statute,
                r2.hits[0].section,
            )

    async def test_empty_query_returns_empty(self) -> None:
        async with LegifranceIpClient() as c:
            r = await c.search("   ")
        assert r.hits == []
        assert r.has_more is False


class TestCorpusUnavailable:
    async def test_raises_when_path_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(tmp_path / "does-not-exist.db"))
        async with LegifranceIpClient() as c:
            with pytest.raises(CorpusUnavailable):
                await c.get_section("L. 611-10 CPI")


@pytest.mark.asyncio
async def test_search_accepts_citation_punctuation() -> None:
    # FTS5 rejects bare punctuation; citations like these used to raise OperationalError.
    async with LegifranceIpClient() as client:
        await client.search("L. 611-10 brevet NOT")
