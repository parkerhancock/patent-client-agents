"""Tests for PCT-EPO Guidelines client.

PCT-EPO Guidelines use the same URL hierarchy as the EPC Guidelines
(``g_ii_3_1.html`` → ``G-II, 3.1``). Citation forms and behavior
mirror the EPC Guidelines tests exactly.

The corpus fixture lives in ``conftest.py`` so it's shared with the
row-18 envelope/corpus_status tests.
"""

from __future__ import annotations

import pytest

from patent_client_agents.epo_pct_guidelines import PctGuidelinesClient


@pytest.fixture(autouse=True)
def _set_corpus(pct_corpus_path, monkeypatch):
    monkeypatch.setenv("PCT_GUIDELINES_CORPUS_PATH", str(pct_corpus_path))


class TestPctGuidelines:
    @pytest.mark.parametrize("citation", ["G-II, 3.1", "G-II 3.1", "G.II.3.1", "g_ii_3_1"])
    async def test_citation_forms(self, citation: str) -> None:
        async with PctGuidelinesClient() as c:
            sec = await c.get_section(citation)
        assert sec.href == "g_ii_3_1"

    async def test_search(self) -> None:
        async with PctGuidelinesClient() as c:
            r = await c.search("Discoveries")
        assert r.hits
        assert r.hits[0].result_url.startswith("https://www.epo.org/en/legal/guidelines-pct/")
