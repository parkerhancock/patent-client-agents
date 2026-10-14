"""IPO India MPPP (Manual of Patent Practice & Procedure) MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
``update_cadence=irregular`` (per ``coverage/sources.yaml``). The MPPP
corpus is a SQLite/FTS5 snapshot of the IPO India MPPP v3.0 (2019).
Every response stamps ``Provenance.corpus_synced_at`` /
``corpus_version`` read from
:func:`patent_client_agents.ipo_in_mppp.get_corpus_status` so agents
can warn when the bundle is stale (§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.ipo_in_mppp import MpppClient, get_corpus_status
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

ipo_in_mppp_mcp = FastMCP("IPO India — MPPP")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). Substantive-law
# Provenance carries corpus_synced_at + corpus_version (§4) read from
# get_corpus_status() — never hardcoded.
# ──────────────────────────────────────────────────────────────────────

_MPPP_SOURCE_NAME = "IPO India Manual of Patent Practice & Procedure (MPPP)"
_MPPP_PDF_URL = (
    "https://ipindia.gov.in/frontend/pdf/patents/"
    "Manual_for_Patent_Office_Practice_and_Procedure_.pdf"
)

_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of an MPPP search hit (§5.5)."""
    return {
        "section_number": hit.get("section_number"),
        "chapter": hit.get("chapter"),
        "title": hit.get("title"),
        "snippet": truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single MPPP section."""
    num = record.get("section_number") or "?"
    title = record.get("title")
    head = f"**MPPP Chapter {num}**"
    if title:
        head += f" — {title}"
    return f"{head}\nSource: MPPP {corpus_version}"


# ---------------------------------------------------------------------------
# search_ipo_in_mppp
# ---------------------------------------------------------------------------


@ipo_in_mppp_mcp.tool(annotations=READ_ONLY)
async def search_ipo_in_mppp(
    query: Annotated[
        str,
        "Search query. Examples: 'first examination report', "
        "'compulsory licensing', 'pre-grant opposition', 'Form 27 working'. "
        "Default 'and' syntax means every term must appear.",
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
        "'relevance' (BM25, default) or 'outline' (section number ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: section_number, "
        "chapter, title, snippet. When True, returns the upstream "
        "MpppSearchHit shape with the BM25 rank.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the IPO India Manual of Patent Practice & Procedure (MPPP).

    The MPPP is the IPO India's internal patent examination manual —
    India's counterpart to the USPTO's MPEP and the UKIPO's MoPP. It
    explains procedural and substantive examination practice under the
    Patents Act, 1970 and the Patent Rules, 2003. Use
    ``get_ipo_in_mppp_section`` for the full text of any hit.

    Examples:
      * Examination procedure:   query='first examination report'
      * Section 3(d) practice:   query='efficacy enhancement'
      * Working statements:      query='Form 27 working'
      * PCT national phase:      query='national phase 31 months'

    Related tools: get_ipo_in_mppp_section, search_ipo_in_statutes.
    """
    return await corpus_search(
        MpppClient,
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
            f"IPO India MPPP — `{query}`",
            len(items),
            response.has_more,
            f" (corpus {corpus_label})",
        ),
        source_url=_MPPP_PDF_URL,
        source_name=_MPPP_SOURCE_NAME,
    )


# ---------------------------------------------------------------------------
# get_ipo_in_mppp_section
# ---------------------------------------------------------------------------


@ipo_in_mppp_mcp.tool(annotations=READ_ONLY)
async def get_ipo_in_mppp_section(
    citation: Annotated[
        str | list[str],
        "MPPP section citation. Accepts: bare dotted number ('04.05.01'), "
        "informal ('Chapter 04.05.01'), or fully-qualified "
        "('MPPP Chapter 04.05.01'). Pass a list for portfolio workflows. "
        "Examples: '04.05.01', ['04.05.01', '05.04', '07.02'].",
    ],
) -> FetchedList[dict]:
    """Get one or more sections from the IPO India MPPP by citation.

    Returns each section's title, chapter, full text, and source URL.
    Accepts a single citation or a list (§5.4); the response shape is
    always a ``ListEnvelope`` with order preserved across calls. The
    bundled corpus version is surfaced in
    ``provenance.corpus_version`` so agents can quote freshness.

    Related tools: search_ipo_in_mppp, get_ipo_in_section.
    """
    refs = as_id_list(citation, noun="MPPP citation")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return record.model_dump()

    return await corpus_get(
        MpppClient,
        refs,
        _fetch_one,
        single=isinstance(citation, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"MPPP section {ref} — not found.",
        noun_plural="MPPP sections",
        source_url=_MPPP_PDF_URL,
        source_name=_MPPP_SOURCE_NAME,
    )


__all__ = ["ipo_in_mppp_mcp", "search_ipo_in_mppp", "get_ipo_in_mppp_section"]
