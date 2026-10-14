"""Tests for the corpus-backed EpcClient."""

from __future__ import annotations

import pytest

from patent_client_agents.epc import EpcClient
from patent_client_agents.epc.client import _citation_to_slug


@pytest.fixture(autouse=True)
def _set_corpus(epc_corpus_path, monkeypatch):
    monkeypatch.setenv("EPC_CORPUS_PATH", str(epc_corpus_path))


class TestCitationToSlug:
    @pytest.mark.parametrize(
        "citation,expected",
        [
            ("Article 54", "a54"),
            ("Art. 54", "a54"),
            ("Art 54", "a54"),
            ("article 54", "a54"),
            ("a54", "a54"),
            ("A54", "a54"),
            ("Rule 71", "r71"),
            ("R. 71", "r71"),
            ("R 71", "r71"),
            ("r71", "r71"),
            ("Article 10a", "a10a"),
        ],
    )
    def test_decoder(self, citation: str, expected: str) -> None:
        assert _citation_to_slug(citation) == expected

    def test_invalid_returns_none(self) -> None:
        assert _citation_to_slug("not a citation") is None
        assert _citation_to_slug("99 problems") is None


class TestGetSection:
    @pytest.mark.parametrize("citation", ["Article 54", "Art. 54", "a54", "A54"])
    async def test_article_citation_forms(self, citation: str) -> None:
        async with EpcClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "a54"
        assert "Novelty" in sec.title

    @pytest.mark.parametrize("citation", ["Rule 71", "R. 71", "r71"])
    async def test_rule_citation_forms(self, citation: str) -> None:
        async with EpcClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "r71"
        assert "Examination" in sec.title

    async def test_url_form(self) -> None:
        async with EpcClient() as c:
            sec = await c.get_section("https://www.epo.org/en/legal/epc/2020/a56.html")
        assert sec.href == "a56"

    async def test_unknown_raises(self) -> None:
        async with EpcClient() as c:
            with pytest.raises(ValueError, match="Could not find"):
                await c.get_section("a999")


class TestSearch:
    async def test_finds_inventive_step(self) -> None:
        async with EpcClient() as c:
            r = await c.search("inventive step", syntax="adj")
        assert r.hits
        assert any(h.href == "a56" for h in r.hits)

    async def test_result_url_format(self) -> None:
        async with EpcClient() as c:
            r = await c.search("novelty")
        for h in r.hits:
            assert h.result_url.startswith("https://www.epo.org/en/legal/epc/2020/")
            assert h.result_url.endswith(".html")


@pytest.mark.asyncio
@pytest.mark.parametrize("syntax", ["and", "or"])
async def test_search_accepts_citation_punctuation(syntax: str) -> None:
    # FTS5 rejects bare punctuation; citations like these used to raise OperationalError.
    async with EpcClient() as client:
        await client.search("Art. 54(2) G-II, 1207.01(a) L.611-10 NOT", syntax=syntax)
