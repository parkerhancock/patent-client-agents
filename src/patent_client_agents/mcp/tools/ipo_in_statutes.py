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

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.ipo_in_statutes import (
    IpoInStatutesClient,
    get_corpus_status,
    parse_citation,
)
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

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

# Lean snippet cap (§5.5).
_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a statute search hit (§5.5)."""
    return {
        "statute_name": hit.get("statute_name"),
        "section_number": hit.get("section_number"),
        "title": hit.get("title"),
        "snippet": truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
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
    limit: Limit100 = 25,
    offset: Offset = 0,
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

    def _summary(response: Any, items: list[dict], corpus_label: str) -> str:
        scope = f" ({response.statute_name})" if response.statute_name else ""
        return hits_summary(
            f"IPO India statutes{scope} — `{query}`",
            len(items),
            response.has_more,
            f" (corpus {corpus_label})",
        )

    return await corpus_search(
        IpoInStatutesClient,
        lambda client: client.search(
            query,
            statute_name=statute,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            offset=offset,
        ),
        corpus_status=get_corpus_status,
        project=None if full else _stub_hit,
        summary=_summary,
        source_url=f"{_INDIACODE_BASE}/handle/123456789",
        source_name=_IPO_IN_SOURCE_NAME,
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
) -> FetchedList[dict]:
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
    refs = as_id_list(citation, noun="IPO India statute citation")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section_by_citation(ref)
        return record.model_dump()

    def _source_url(items: list[dict], corpus_label: str) -> str:
        if len(refs) == 1 and items:
            return items[0].get("source_url") or f"{_IPINDIA_BASE}/"
        return f"{_INDIACODE_BASE}/handle/123456789"

    return await corpus_get(
        IpoInStatutesClient,
        refs,
        _fetch_one,
        single=isinstance(citation, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"IPO India statute section {ref} — not found.",
        noun_plural="IPO India statute sections",
        source_url=_source_url,
        source_name=_IPO_IN_SOURCE_NAME,
    )


__all__ = ["ipo_in_statutes_mcp", "search_ipo_in_statutes", "get_ipo_in_section"]

# Re-export so tests can patch from this module path.
parse_citation = parse_citation  # noqa: PLW0127 — explicit re-export for symmetry
