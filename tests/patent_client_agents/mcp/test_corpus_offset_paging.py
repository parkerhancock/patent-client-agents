"""Offset paging on the bundled-corpus search tools returns exact rows.

The corpus tools take ``limit``/``offset``. Paging through a result set with
an offset that isn't a multiple of ``limit`` must yield the same rows, in the
same order, as one large query: no repeats and no gaps.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from patent_client_agents.mcp.tools.dpma_statutes import search_dpma_statutes
from patent_client_agents.mcp.tools.epc import search_epc
from patent_client_agents.mcp.tools.epo_case_law import search_epo_case_law
from patent_client_agents.mcp.tools.epo_guidelines import search_epo_guidelines
from patent_client_agents.mcp.tools.epo_pct_guidelines import search_epo_pct_guidelines
from patent_client_agents.mcp.tools.epo_up_guidelines import search_epo_up_guidelines
from patent_client_agents.mcp.tools.inpi_br_statutes import search_inpi_br_statutes
from patent_client_agents.mcp.tools.ipo_in_mppp import search_ipo_in_mppp
from patent_client_agents.mcp.tools.ipo_in_statutes import search_ipo_in_statutes
from patent_client_agents.mcp.tools.mpep import search_mpep
from patent_client_agents.mcp.tools.trademarks import search_tmep
from patent_client_agents.mcp.tools.tw_trade_secrets import search_tw_trade_secrets
from patent_client_agents.mcp.tools.ukipo_mopp import search_mopp

# Each package's fixture corpus, imported so this module can request it.
from tests.dpma_statutes.conftest import dpma_statutes_corpus_path  # noqa: F401
from tests.epc.conftest import epc_corpus_path  # noqa: F401
from tests.epo_case_law.conftest import caselaw_corpus_path  # noqa: F401
from tests.epo_guidelines.conftest import guidelines_corpus_path  # noqa: F401
from tests.epo_pct_guidelines.conftest import pct_corpus_path  # noqa: F401
from tests.epo_up_guidelines.conftest import up_corpus_path  # noqa: F401
from tests.inpi_br_statutes.conftest import lpi_corpus_path  # noqa: F401
from tests.ipo_in_mppp.conftest import ipo_in_mppp_corpus_path  # noqa: F401
from tests.ipo_in_statutes.conftest import ipo_in_statutes_corpus_path  # noqa: F401
from tests.mpep.conftest import mpep_corpus_path  # noqa: F401
from tests.tmep.conftest import tmep_corpus_path  # noqa: F401
from tests.tw_trade_secrets.conftest import tw_trade_secrets_corpus_path  # noqa: F401
from tests.ukipo_mopp.conftest import mopp_corpus_path  # noqa: F401

Search = Callable[..., Awaitable[Any]]

# Broad OR queries so even the smallest fixture corpus returns several hits.
ENGLISH = "the a of and patent invention application section rule article"
GERMAN = "die der de das und"

# (tool, env var, corpus fixture, query)
CASES: list[tuple[Search, str, str, str]] = [
    (search_dpma_statutes, "DPMA_STATUTES_CORPUS_PATH", "dpma_statutes_corpus_path", GERMAN),
    (search_epc, "EPC_CORPUS_PATH", "epc_corpus_path", ENGLISH),
    (search_epo_case_law, "CASELAW_CORPUS_PATH", "caselaw_corpus_path", ENGLISH),
    (search_epo_guidelines, "GUIDELINES_CORPUS_PATH", "guidelines_corpus_path", ENGLISH),
    (search_epo_pct_guidelines, "PCT_GUIDELINES_CORPUS_PATH", "pct_corpus_path", ENGLISH),
    (search_epo_up_guidelines, "UP_GUIDELINES_CORPUS_PATH", "up_corpus_path", ENGLISH),
    (search_inpi_br_statutes, "INPI_BR_STATUTES_CORPUS_PATH", "lpi_corpus_path", ENGLISH),
    (search_ipo_in_mppp, "IPO_IN_MPPP_CORPUS_PATH", "ipo_in_mppp_corpus_path", ENGLISH),
    (search_ipo_in_statutes, "IPO_IN_STATUTES_CORPUS_PATH", "ipo_in_statutes_corpus_path", ENGLISH),
    (search_mpep, "MPEP_CORPUS_PATH", "mpep_corpus_path", ENGLISH),
    (search_tmep, "TMEP_CORPUS_PATH", "tmep_corpus_path", ENGLISH),
    (
        search_tw_trade_secrets,
        "TW_TRADE_SECRETS_CORPUS_PATH",
        "tw_trade_secrets_corpus_path",
        ENGLISH,
    ),
    (search_mopp, "MOPP_CORPUS_PATH", "mopp_corpus_path", ENGLISH),
]


@pytest.mark.parametrize(
    ("search", "env_var", "fixture", "query"),
    CASES,
    ids=[case[0].__name__ for case in CASES],
)
async def test_offset_paging_returns_exact_rows(
    search: Search,
    env_var: str,
    fixture: str,
    query: str,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus: Path = request.getfixturevalue(fixture)
    monkeypatch.setenv(env_var, str(corpus))

    everything = await search(query=query, limit=100, offset=0, syntax="or", full=True)
    expected = everything.items
    assert len(expected) >= 2, "fixture corpus needs at least 2 hits for this query"

    limit = 2
    paged: list[Any] = []
    offset = 1  # deliberately not a multiple of limit
    while True:
        page = await search(query=query, limit=limit, offset=offset, syntax="or", full=True)
        paged.extend(page.items)
        assert page.more_available == (offset + len(page.items) < len(expected))
        if not page.more_available:
            break
        offset += len(page.items)

    assert paged == expected[1:]
