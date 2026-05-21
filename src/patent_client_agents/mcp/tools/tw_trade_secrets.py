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

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
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

_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5).
_LEAN_SNIPPET_CHARS = 400


def _statutes_provenance(source_url: str) -> Any:
    """Build a Provenance for the Trade Secrets corpus.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.tw_trade_secrets.get_corpus_status` so
    the values track the bundled corpus without per-call hardcoding.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=source_url,
        source_name=_TW_SOURCE_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a search hit (§5.5)."""
    return {
        "section": hit.get("section"),
        "title": hit.get("title"),
        "snippet": _truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
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
    limit: Annotated[int, "Maximum hits to return (1-100)."] = 25,
    offset: Annotated[int, "Result offset for pagination."] = 0,
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
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    page = (offset // limit) + 1 if offset >= 0 else 1
    async with TwTradeSecretsClient() as client:
        response = await client.search(
            query,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            page=page,
        )

    hits = [h.model_dump() for h in response.hits]
    items = hits if full else [_stub_hit(h) for h in hits]

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    summary = (
        f"TW Trade Secrets Act — `{query}`: "
        f"{len(items)} hit{'s' if len(items) != 1 else ''} (corpus {corpus_label})"
    )
    if response.has_more:
        summary += " (more available)."
    else:
        summary += "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=_statutes_provenance(_LAW_MOJ_TRADE_SECRETS_URL),
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
) -> ListEnvelope[dict]:
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
    refs = [citation] if isinstance(citation, str) else list(citation)
    if not refs:
        raise ValidationError("get_tw_trade_secrets_section requires at least one citation")

    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TwTradeSecretsClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section_by_citation(ref)
            return record.model_dump()

    async with TwTradeSecretsClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
    else:
        summary = (
            f"Fetched {len(results)} Taiwan Trade Secrets Articles (corpus {corpus_label}): "
            + ", ".join(refs)
        )

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_statutes_provenance(_LAW_MOJ_TRADE_SECRETS_URL),
    )


__all__ = [
    "tw_trade_secrets_mcp",
    "search_tw_trade_secrets",
    "get_tw_trade_secrets_section",
]

# Re-export so tests can patch from this module path.
parse_citation = parse_citation  # noqa: PLW0127 — explicit re-export for symmetry
