"""Tests for the corpus-backed InpiBrStatutesClient."""

from __future__ import annotations

import pytest

from patent_client_agents.inpi_br_statutes import InpiBrStatutesClient
from patent_client_agents.inpi_br_statutes.client import _citation_to_slug


@pytest.fixture(autouse=True)
def _set_corpus(lpi_corpus_path, monkeypatch):
    monkeypatch.setenv("INPI_BR_STATUTES_CORPUS_PATH", str(lpi_corpus_path))


class TestCitationToSlug:
    @pytest.mark.parametrize(
        "citation,expected",
        [
            ("Art. 6", "art6"),
            ("Art 6", "art6"),
            ("Article 6", "art6"),
            ("Artigo 6", "art6"),
            ("art6", "art6"),
            ("ART6", "art6"),
            ("Art. 195", "art195"),
            ("Art 195 LPI", "art195"),
            ("Art. 195 da LPI", "art195"),
            ("Art. 195(XI)", "art195"),
            ("Art. 195(XI) LPI", "art195"),
        ],
    )
    def test_decoder(self, citation: str, expected: str) -> None:
        assert _citation_to_slug(citation) == expected

    def test_invalid_returns_none(self) -> None:
        assert _citation_to_slug("not a citation") is None
        assert _citation_to_slug("99 problems") is None


class TestGetSection:
    @pytest.mark.parametrize("citation", ["Art. 6", "Art 6", "Article 6", "art6", "Artigo 6"])
    async def test_article_citation_forms(self, citation: str) -> None:
        async with InpiBrStatutesClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "art6"
        assert sec.article_number == "Art. 6"
        assert "patente" in sec.text_pt.lower()
        # EN translation also bundled
        assert sec.text_en is not None
        assert "patent" in sec.text_en.lower()

    async def test_trade_secret_article(self) -> None:
        async with InpiBrStatutesClient() as c:
            sec = await c.get_section("Art. 195(XI) LPI")
        assert sec.href == "art195"
        assert "concorrência desleal" in sec.text_pt.lower()
        assert sec.text_en is not None and "unfair competition" in sec.text_en.lower()

    async def test_url_form_with_anchor(self) -> None:
        async with InpiBrStatutesClient() as c:
            sec = await c.get_section("https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#art10")
        assert sec.href == "art10"

    async def test_unknown_raises(self) -> None:
        async with InpiBrStatutesClient() as c:
            with pytest.raises(ValueError, match="Could not find"):
                await c.get_section("art999")


class TestSearch:
    async def test_finds_trade_secret(self) -> None:
        async with InpiBrStatutesClient() as c:
            r = await c.search("concorrência desleal", syntax="adj")
        assert r.hits
        assert any(h.href == "art195" for h in r.hits)

    async def test_finds_via_english(self) -> None:
        async with InpiBrStatutesClient() as c:
            r = await c.search("unfair competition", syntax="adj")
        assert r.hits
        assert any(h.href == "art195" for h in r.hits)

    async def test_result_url_format(self) -> None:
        async with InpiBrStatutesClient() as c:
            r = await c.search("patente")
        for h in r.hits:
            assert h.result_url.startswith("https://www.planalto.gov.br/")
            assert "#Art" in h.result_url


class TestListVersions:
    async def test_versions_carry_label(self) -> None:
        async with InpiBrStatutesClient() as c:
            versions = await c.list_versions()
        assert versions
        assert versions[0].current is True
        assert "1996" in versions[0].label
