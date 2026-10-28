"""Routing contract for the consolidated legal-reference facade dispatchers.

The facade tools hold no business logic — each branch forwards to an
existing per-corpus function that is already tested for §5.9 envelope shape
(see the per-corpus envelope tests). These tests pin the *routing*: that the
right ``corpus`` enum value reaches the right underlying search/get function
with the right arguments, and that the facade returns that function's result
unchanged. Targets are patched where the facade imports them
(``...mcp.facade.legal_reference``), so no upstream/corpus client is touched
except in the one end-to-end test.

This is the eval-flagged 14-value-enum pair, so routing is parametrized
across all folded corpora. ``upc`` / ``wipo_lex`` diverge and are re-exposed
verbatim — covered separately.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.facade.legal_reference import (
    get_legal_reference,
    search_legal_reference,
)

_MOD = "patent_client_agents.facade.legal_reference"


# ──────────────────────────────────────────────────────────────────────
# search_legal_reference — the 10 uniform-shape corpora (no statute filter)
# ──────────────────────────────────────────────────────────────────────

_UNIFORM_SEARCH = [
    ("uspto_mpep", "search_mpep"),
    ("uspto_tmep", "search_tmep"),
    ("epo_guidelines", "search_epo_guidelines"),
    ("epo_pct_guidelines", "search_epo_pct_guidelines"),
    ("epo_up_guidelines", "search_epo_up_guidelines"),
    ("epo_case_law", "search_epo_case_law"),
    ("epc", "search_epc"),
    ("ukipo_mopp", "search_mopp"),
    ("india_mppp", "search_ipo_in_mppp"),
    ("tw_trade_secrets", "search_tw_trade_secrets"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("corpus", "target"), _UNIFORM_SEARCH)
async def test_search_routes_uniform_corpus(corpus, target):
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="HITS")) as m:
        out = await search_legal_reference(
            corpus=corpus, query="q", limit=5, offset=2, syntax="or", sort="outline", full=True
        )
    assert out == "HITS"
    # Uniform corpora never receive ``statute``.
    m.assert_awaited_once_with(
        query="q",
        limit=5,
        offset=2,
        syntax="or",
        sort="outline",
        full=True,
        **({"version": "current"} if corpus == "uspto_mpep" else {}),
    )


# ──────────────────────────────────────────────────────────────────────
# search_legal_reference — the 2 statute-filter corpora forward ``statute``
# ──────────────────────────────────────────────────────────────────────

_STATUTE_SEARCH = [
    ("dpma", "search_dpma_statutes"),
    ("india_statutes", "search_ipo_in_statutes"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("corpus", "target"), _STATUTE_SEARCH)
async def test_search_routes_statute_corpus_with_filter(corpus, target):
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="HITS")) as m:
        out = await search_legal_reference(corpus=corpus, query="q", limit=10, statute="PatG")
    assert out == "HITS"
    m.assert_awaited_once_with(
        query="q", statute="PatG", limit=10, offset=0, syntax="adj", sort="relevance", full=False
    )


@pytest.mark.asyncio
async def test_search_statute_corpus_defaults_statute_to_none():
    with patch(f"{_MOD}.search_dpma_statutes", new=AsyncMock(return_value="HITS")) as m:
        await search_legal_reference(corpus="dpma", query="q")
    _, kwargs = m.await_args
    assert kwargs["statute"] is None


# ──────────────────────────────────────────────────────────────────────
# get_legal_reference — uniform single-identifier across the 12 corpora
# ──────────────────────────────────────────────────────────────────────

_GET_ROUTES = [
    ("uspto_mpep", "get_mpep_section"),
    ("uspto_tmep", "get_tmep_section"),
    ("epo_guidelines", "get_epo_guidelines_section"),
    ("epo_pct_guidelines", "get_epo_pct_guidelines_section"),
    ("epo_up_guidelines", "get_epo_up_guidelines_section"),
    ("epo_case_law", "get_epo_case_law_section"),
    ("epc", "get_epc_section"),
    ("dpma", "get_dpma_section"),
    ("ukipo_mopp", "get_mopp_section"),
    ("india_statutes", "get_ipo_in_section"),
    ("india_mppp", "get_ipo_in_mppp_section"),
    ("tw_trade_secrets", "get_tw_trade_secrets_section"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("corpus", "target"), _GET_ROUTES)
async def test_get_routes_each_corpus(corpus, target):
    # Identifier passed positionally so the section/citation param-name
    # difference between manual and statute corpora is absorbed.
    with patch(f"{_MOD}.{target}", new=AsyncMock(return_value="REC")) as m:
        out = await get_legal_reference(corpus=corpus, identifier="2106")
    assert out == "REC"
    m.assert_awaited_once_with("2106", **({"version": "current"} if corpus == "uspto_mpep" else {}))


# ──────────────────────────────────────────────────────────────────────
# Divergent pairs re-exposed verbatim on the facade (full schema preserved)
# ──────────────────────────────────────────────────────────────────────


def test_divergent_pairs_are_reexposed_verbatim():
    from patent_client_agents.facade import legal_reference as fac
    from patent_client_agents.mcp.tools.upc import get_upc_section, search_upc_statutes
    from patent_client_agents.mcp.tools.wipo_lex import (
        get_wipo_lex_legislation,
        search_wipo_lex_legislation,
    )

    # The standalone tools are the exact upstream functions (no wrapper).
    assert fac.search_upc_statutes is search_upc_statutes
    assert fac.get_upc_section is get_upc_section
    assert fac.search_wipo_lex_legislation is search_wipo_lex_legislation
    assert fac.get_wipo_lex_legislation is get_wipo_lex_legislation


# ──────────────────────────────────────────────────────────────────────
# End-to-end: facade → real search_mpep → §5.9 envelope. Proves the envelope
# contract (incl. §4 corpus provenance) survives the dispatch.
# ──────────────────────────────────────────────────────────────────────


class _FakeHit:
    def __init__(self, data):
        self._data = data

    def model_dump(self):
        return dict(self._data)


class _FakeSearchResponse:
    def __init__(self, hits, has_more):
        self.hits = hits
        self.has_more = has_more


@pytest.mark.asyncio
async def test_search_mpep_preserves_envelope_end_to_end():
    from mcp_data_core.envelope import ListEnvelope, Provenance

    fake = _FakeSearchResponse(
        hits=[
            _FakeHit(
                {
                    "title": "2106 - Patent Subject Matter Eligibility",
                    "path": ["Chapter 2100", "2106"],
                    "snippet": "...subject matter eligibility...",
                    "href": "d0e197244.htm",
                }
            )
        ],
        has_more=True,
    )
    with patch("patent_client_agents.mcp.tools.mpep.MpepClient") as cls:
        client = cls.return_value.__aenter__.return_value
        client.search = AsyncMock(return_value=fake)
        out = await search_legal_reference(corpus="uspto_mpep", query="eligibility", limit=1)

    assert isinstance(out, ListEnvelope)
    assert isinstance(out.provenance, Provenance)
    assert out.provenance.source_name == "USPTO MPEP (Manual of Patent Examining Procedure)"
    assert "mpep.uspto.gov" in out.provenance.source_url
    # §4 recency metadata for substantive_law corpora rides along.
    assert out.provenance.corpus_version is not None
    assert len(out.items) == 1
    assert out.more_available is True


@pytest.mark.asyncio
async def test_mpep_version_forwarding():
    with patch(f"{_MOD}.get_mpep_section", new=AsyncMock(return_value="REC")) as mocked:
        await get_legal_reference(corpus="uspto_mpep", identifier="2106", version="retained")
    mocked.assert_awaited_once_with("2106", version="retained")
    with pytest.raises(ValueError, match="only for uspto_mpep"):
        await get_legal_reference(corpus="uspto_tmep", identifier="1", version="old")
