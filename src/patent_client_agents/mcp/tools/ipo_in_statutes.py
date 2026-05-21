"""IPO India statutes MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
``update_cadence=annual`` (per ``coverage/sources.yaml``). The corpus
bundles four Indian IP Acts (Patents Act 1970, Designs Act 2000, Trade
Marks Act 1999, Copyright Act 1957) plus the Patent Rules 2003 into one
SQLite/FTS5 snapshot materialized by
``patent-client-agents-build-ipo-in-statutes-corpus``. Every response
stamps ``Provenance.corpus_synced_at`` / ``corpus_version`` read from
:func:`patent_client_agents.ipo_in_statutes.get_corpus_status` so
agents can warn when the bundle is stale (§4).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.ipo_in_statutes import (
    IpoInStatutesClient,
    get_corpus_status,
    parse_citation,
)

ipo_in_statutes_mcp = FastMCP("IPO India — Statutes")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The IPO India
# statutes are substantive law served from a locally-bundled SQLite
# snapshot, so Provenance carries corpus_synced_at + corpus_version in
# addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_IPO_IN_SOURCE_NAME = "IPO India — IP statutes"
_INDIACODE_BASE = "https://indiacode.nic.in"
_IPINDIA_BASE = "https://ipindia.gov.in"

_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5).
_LEAN_SNIPPET_CHARS = 400


def _statutes_provenance(source_url: str) -> Any:
    """Build a Provenance for the statutes corpus.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.ipo_in_statutes.get_corpus_status` so
    the values track the bundled corpus without per-call hardcoding.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=source_url,
        source_name=_IPO_IN_SOURCE_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a statute search hit (§5.5)."""
    return {
        "statute_name": hit.get("statute_name"),
        "section_number": hit.get("section_number"),
        "title": hit.get("title"),
        "snippet": _truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single statute section."""
    statute = record.get("statute_name") or "(unknown statute)"
    num = record.get("section_number") or "?"
    title = record.get("title")
    head = f"**{statute} §{num}**"
    if title:
        head += f" — {title}"
    return f"{head}\nSource: IPO India statutes corpus ({corpus_version})"


# ---------------------------------------------------------------------------
# search_ipo_in_statutes
# ---------------------------------------------------------------------------


@ipo_in_statutes_mcp.tool(annotations=READ_ONLY)
async def search_ipo_in_statutes(
    query: Annotated[
        str,
        "Search query. Examples: 'compulsory licensing', 'fair dealing', "
        "'inventive step', 'well-known mark'. Default 'and' syntax means "
        "every term must appear; pass syntax='or' to widen.",
    ],
    statute: Annotated[
        str | None,
        "Optional Act filter — 'Patents Act', 'Patent Rules', 'Designs Act', "
        "'Trade Marks Act', or 'Copyright Act' (case-insensitive; "
        "aliases like 'patents act 1970' accepted). Omit to search "
        "across all bundled Acts.",
    ] = None,
    limit: Annotated[int, "Maximum hits to return (1-100)."] = 25,
    offset: Annotated[int, "Result offset for pagination."] = 0,
    syntax: Annotated[
        str,
        "Query syntax. 'and' (default) — all terms must match. "
        "'or' — any term matches. 'adj' or 'exact' — adjacent phrase.",
    ] = "and",
    sort: Annotated[
        str,
        "'relevance' (BM25, default) or 'outline' (statute + section ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: statute_name, "
        "section_number, title, snippet. When True, returns the upstream "
        "IpoInSearchHit shape with the BM25 rank.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Indian IP statutes (Patents, Designs, Trade Marks, Copyright Acts).

    The corpus bundles the four core Indian IP Acts plus the Patent
    Rules 2003 — pass ``statute=`` to constrain to one Act, or omit
    to search across all four. Use ``get_ipo_in_section`` for the
    full section text by citation (e.g. 'Section 3(d) Patents Act').

    Examples:
      * §3(d) anti-evergreening:    query='efficacy'
      * Compulsory licensing:       query='compulsory licensing', statute='Patents Act'
      * Trade mark dilution:        query='well-known mark', statute='Trade Marks Act'
      * Fair dealing copyright:     query='fair dealing'

    Related tools: get_ipo_in_section, search_ipo_in_mppp.
    """
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    page = (offset // limit) + 1 if offset >= 0 else 1
    async with IpoInStatutesClient() as client:
        response = await client.search(
            query,
            statute_name=statute,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            page=page,
        )

    hits = [h.model_dump() for h in response.hits]
    items = hits if full else [_stub_hit(h) for h in hits]

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    scope = f" ({response.statute_name})" if response.statute_name else ""
    summary = (
        f"IPO India statutes{scope} — `{query}`: "
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
        provenance=_statutes_provenance(f"{_INDIACODE_BASE}/handle/123456789"),
    )


# ---------------------------------------------------------------------------
# get_ipo_in_section
# ---------------------------------------------------------------------------


@ipo_in_statutes_mcp.tool(annotations=READ_ONLY)
async def get_ipo_in_section(
    citation: Annotated[
        str | list[str],
        "Statute citation. Accepts: free-text form ('Section 3(d) Patents Act', "
        "'Rule 71 Patent Rules', 'Section 25(2) of the Patents Act'); or a "
        "list of either for portfolio workflows. Examples: "
        "'Section 3(d) Patents Act', "
        "['Section 3(d) Patents Act', 'Section 84 Patents Act', "
        "'Section 9 Trade Marks Act'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more sections of the bundled Indian IP Acts by citation.

    Accepts free-text citations like 'Section 3(d) Patents Act' or
    'Rule 71 Patent Rules'; the parser extracts the section number and
    statute name. Bare section numbers ('§107A') resolve when the
    number is unique across the bundled Acts. Pass a list for
    portfolio workflows (§5.4); the response shape stays a
    ``ListEnvelope`` with order preserved.

    The bundled corpus version is surfaced in
    ``provenance.corpus_version`` so agents can quote freshness.

    Related tools: search_ipo_in_statutes, get_ipo_in_mppp_section.
    """
    refs = [citation] if isinstance(citation, str) else list(citation)
    if not refs:
        raise ValidationError("get_ipo_in_section requires at least one citation")

    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IpoInStatutesClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section_by_citation(ref)
            return record.model_dump()

    async with IpoInStatutesClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
        src_url = results[0].get("source_url") or f"{_IPINDIA_BASE}/"
    else:
        summary = (
            f"Fetched {len(results)} IPO India statute sections (corpus {corpus_label}): "
            + ", ".join(refs)
        )
        src_url = f"{_INDIACODE_BASE}/handle/123456789"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_statutes_provenance(src_url),
    )


__all__ = ["ipo_in_statutes_mcp", "search_ipo_in_statutes", "get_ipo_in_section"]

# Re-export so tests can patch from this module path.
parse_citation = parse_citation  # noqa: PLW0127 — explicit re-export for symmetry
