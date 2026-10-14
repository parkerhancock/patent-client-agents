"""Taiwan Trade Secrets Act MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
``update_cadence=irregular`` (per ``coverage/sources.yaml``). The
corpus bundles the official English translation of the Taiwan Trade
Secrets Act (營業秘密法) — Articles 1, 2, 3, 10, 11, 13, and 13-1 —
into one SQLite/FTS5 snapshot materialized by
``patent-client-agents-build-tw-trade-secrets-corpus``. Every response
stamps ``Provenance.corpus_synced_at`` / ``corpus_version`` read from
:func:`patent_client_agents.tw_trade_secrets.get_corpus_status` so
agents can warn when the bundle is stale (§4).

TIPO REST + bulk are deferred to a follow-up PR. This connector's
scope is statute corpus only.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset
from patent_client_agents.tw_trade_secrets import (
    TwTradeSecretsClient,
    get_corpus_status,
    parse_citation,
)

tw_trade_secrets_mcp = FastMCP("Taiwan — Trade Secrets Act")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The Trade Secrets Act
# is substantive law served from a locally-bundled SQLite snapshot, so
# Provenance carries corpus_synced_at + corpus_version in addition to
# the standard fields. Both are read from ``get_corpus_status()`` once
# per request — NEVER hardcoded — so a corpus refresh propagates
# without a code change here.
# ──────────────────────────────────────────────────────────────────────

_TW_SOURCE_NAME = "Taiwan — Trade Secrets Act (EN translation)"
_LAW_MOJ_BASE = "https://law.moj.gov.tw/Eng"
_LAW_MOJ_TRADE_SECRETS_URL = f"{_LAW_MOJ_BASE}/LawClass/LawAll.aspx?pcode=J0080028"

# Lean snippet cap (§5.5).
_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a search hit (§5.5)."""
    return {
        "section": hit.get("section"),
        "title": hit.get("title"),
        "snippet": truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single Article."""
    num = record.get("section") or "?"
    title = record.get("title")
    head = f"**Trade Secrets Act Art. {num}**"
    if title:
        head += f" — {title}"
    return f"{head}\nSource: Taiwan Trade Secrets Act corpus ({corpus_version})"


# ---------------------------------------------------------------------------
# search_tw_trade_secrets
# ---------------------------------------------------------------------------


@tw_trade_secrets_mcp.tool(annotations=READ_ONLY)
async def search_tw_trade_secrets(
    query: Annotated[
        str,
        "Search query. Examples: 'damages', 'misappropriation', 'criminal "
        "liability', 'employee'. Default 'and' syntax means every term "
        "must appear; pass syntax='or' to widen.",
    ],
    limit: Limit100 = 25,
    offset: Offset = 0,
    syntax: Annotated[
        str,
        "Query syntax. 'and' (default) — all terms must match. "
        "'or' — any term matches. 'adj' or 'exact' — adjacent phrase.",
    ] = "and",
    sort: Annotated[
        str,
        "'relevance' (BM25, default) or 'outline' (Article number ascending, lex).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: section, title, "
        "snippet. When True, returns the upstream TwTradeSecretsSearchHit "
        "shape with the BM25 rank.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the Taiwan Trade Secrets Act (營業秘密法, EN translation).

    The corpus bundles Articles 1, 2, 3, 10, 11, 13, and 13-1 of the
    Trade Secrets Act in the official English translation published by
    law.moj.gov.tw/Eng. Use ``get_tw_trade_secrets_section`` for the
    full Article text by citation (e.g. 'Art. 13-1 Trade Secrets Act').

    Examples:
      * Definition (Art. 2):     query='reasonable measures'
      * Damages calculation:     query='damages royalty'
      * Criminal liability:      query='imprisonment'
      * Misappropriation acts:   query='improper means'

    Related tools: get_tw_trade_secrets_section.
    """
    return await corpus_search(
        TwTradeSecretsClient,
        lambda client: client.search(
            query,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            offset=offset,
        ),
        corpus_status=get_corpus_status,
        project=None if full else _stub_hit,
        summary=lambda response, items, corpus_label: hits_summary(
            f"TW Trade Secrets Act — `{query}`",
            len(items),
            response.has_more,
            f" (corpus {corpus_label})",
        ),
        source_url=_LAW_MOJ_TRADE_SECRETS_URL,
        source_name=_TW_SOURCE_NAME,
    )


# ---------------------------------------------------------------------------
# get_tw_trade_secrets_section
# ---------------------------------------------------------------------------


@tw_trade_secrets_mcp.tool(annotations=READ_ONLY)
async def get_tw_trade_secrets_section(
    citation: Annotated[
        str | list[str],
        "Article citation. Accepts: free-text form ('Art. 2 Trade Secrets "
        "Act', 'Section 13 Trade Secrets Act', 'Art. 13-1'); bare article "
        "numbers ('13', '13-1'); or a list of any of these for portfolio "
        "workflows. Examples: 'Art. 2 Trade Secrets Act', ['Art. 2', "
        "'Art. 13', 'Art. 13-1'].",
    ],
) -> FetchedList[dict]:
    """Get one or more Articles of the Taiwan Trade Secrets Act by citation.

    Accepts free-text citations like 'Art. 2 Trade Secrets Act' or
    'Section 13 Trade Secrets Act'; the parser extracts the Article
    number. Sub-numbered articles ('Art. 13-1') and bare numbers ('13')
    are both accepted. Pass a list for portfolio workflows (§5.4); the
    response shape stays a ``ListEnvelope`` with order preserved.

    The bundled corpus version is surfaced in
    ``provenance.corpus_version`` so agents can quote freshness.

    Related tools: search_tw_trade_secrets.
    """
    refs = as_id_list(citation, noun="Taiwan Trade Secrets Act citation")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section_by_citation(ref)
        return record.model_dump()

    return await corpus_get(
        TwTradeSecretsClient,
        refs,
        _fetch_one,
        single=isinstance(citation, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"Taiwan Trade Secrets Article {ref} — not found.",
        noun_plural="Taiwan Trade Secrets Articles",
        source_url=_LAW_MOJ_TRADE_SECRETS_URL,
        source_name=_TW_SOURCE_NAME,
    )


__all__ = [
    "tw_trade_secrets_mcp",
    "search_tw_trade_secrets",
    "get_tw_trade_secrets_section",
]

# Re-export so tests can patch from this module path.
parse_citation = parse_citation  # noqa: PLW0127 — explicit re-export for symmetry
