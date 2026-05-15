"""Tests for UP Guidelines client.

UP Guidelines use a flat ``N.M.P`` numbering matching slug
``section_N_M_P`` — different from the EPC/PCT Guidelines'
Part/Chapter/Section hierarchy.

The corpus fixture lives in ``conftest.py`` so it's shared with the
row-18 envelope/corpus_status tests.
"""

from __future__ import annotations

import pytest

from patent_client_agents.epo_up_guidelines import UpGuidelinesClient
from patent_client_agents.epo_up_guidelines.client import _citation_to_slug


@pytest.fixture(autouse=True)
def _set_corpus(up_corpus_path, monkeypatch):
    monkeypatch.setenv("UP_GUIDELINES_CORPUS_PATH", str(up_corpus_path))


class TestCitationToSlug:
    @pytest.mark.parametrize(
        "citation,expected",
        [
            ("1.2.1", "section_1_2_1"),
            ("1-2-1", "section_1_2_1"),
            ("1 2 1", "section_1_2_1"),
            ("Section 1.2.1", "section_1_2_1"),
            ("§ 1.2.1", "section_1_2_1"),
            ("2.1", "section_2_1"),
        ],
    )
    def test_decoder(self, citation: str, expected: str) -> None:
        assert _citation_to_slug(citation) == expected


class TestUpGuidelines:
    @pytest.mark.parametrize("citation", ["2.1", "Section 2.1", "§ 2.1", "section_2_1"])
    async def test_citation_forms(self, citation: str) -> None:
        async with UpGuidelinesClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "section_2_1"

    async def test_search(self) -> None:
        async with UpGuidelinesClient() as c:
            r = await c.search("unitary effect")
        assert r.hits
        assert r.hits[0].result_url.startswith("https://www.epo.org/en/legal/guidelines-up/")
        # UP URLs don't have .html suffix
        assert not r.hits[0].result_url.endswith(".html")
