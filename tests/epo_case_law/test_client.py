"""Tests for the corpus-backed CaseLawClient."""

from __future__ import annotations

import pytest

from patent_client_agents.epo_case_law import CaseLawClient
from patent_client_agents.epo_case_law.client import _citation_to_slug


@pytest.fixture(autouse=True)
def _set_corpus(caselaw_corpus_path, monkeypatch):
    monkeypatch.setenv("CASELAW_CORPUS_PATH", str(caselaw_corpus_path))


class TestCitationToSlug:
    @pytest.mark.parametrize(
        "citation,expected",
        [
            ("I.A.1", "clr_i_a_1"),
            ("I A 1", "clr_i_a_1"),
            ("I-A-1", "clr_i_a_1"),
            ("i.a.1", "clr_i_a_1"),
            ("I.A", "clr_i_a"),
            ("I", "clr_i"),
        ],
    )
    def test_decoder(self, citation: str, expected: str) -> None:
        assert _citation_to_slug(citation) == expected


class TestGetSection:
    @pytest.mark.parametrize("citation", ["I.A.1", "I A 1", "I-A-1", "i.a.1"])
    async def test_citation_forms(self, citation: str) -> None:
        async with CaseLawClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "clr_i_a_1"
        assert "Novelty" in sec.title

    async def test_bare_slug(self) -> None:
        async with CaseLawClient() as c:
            sec = await c.get_section("clr_i_d_3")
        assert "Inventive step" in sec.title

    async def test_named_section(self) -> None:
        async with CaseLawClient() as c:
            sec = await c.get_section("clr_foreword")
        assert sec.title == "Foreword"

    async def test_unknown_raises(self) -> None:
        async with CaseLawClient() as c:
            with pytest.raises(ValueError, match="Could not find"):
                await c.get_section("clr_zzz_x_999")


class TestSearch:
    async def test_finds_problem_solution(self) -> None:
        async with CaseLawClient() as c:
            r = await c.search("problem and solution", syntax="adj")
        assert r.hits

    async def test_result_url_format(self) -> None:
        async with CaseLawClient() as c:
            r = await c.search("Novelty")
        assert r.hits
        for h in r.hits:
            assert h.result_url.startswith("https://www.epo.org/en/legal/case-law/2022/")


@pytest.mark.asyncio
@pytest.mark.parametrize("syntax", ["and", "or"])
async def test_search_accepts_citation_punctuation(syntax: str) -> None:
    # FTS5 rejects bare punctuation; citations like these used to raise OperationalError.
    async with CaseLawClient() as client:
        await client.search("Art. 54(2) G-II, 1207.01(a) L.611-10 NOT", syntax=syntax)
