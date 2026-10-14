"""UKIPO Manual of Patent Practice (MoPP) MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The MoPP corpus is a SQLite/FTS5 snapshot
materialized by ``patent-client-agents-build-mopp-corpus`` from
gov.uk's published pages; every response stamps
``Provenance.corpus_synced_at`` and ``corpus_version`` read from
:func:`patent_client_agents.ukipo_mopp.get_corpus_status` so agents can
warn when the bundle is stale (§4).
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
from patent_client_agents.ukipo_mopp import MoppClient, get_corpus_status

ukipo_mopp_mcp = FastMCP("UKIPO MoPP")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The Manual of Patent
# Practice (MoPP) is substantive law served from a locally-bundled
# SQLite snapshot (§4 / coverage/sources.yaml), so Provenance carries
# corpus_synced_at + corpus_version in addition to the standard fields.
# Both are read from ``get_corpus_status()`` once per request —
# NEVER hardcoded — so a corpus refresh propagates without a code
# change here.
# ──────────────────────────────────────────────────────────────────────

_MOPP_BASE = "https://www.gov.uk"
_MOPP_NAME = "UKIPO Manual of Patent Practice (MoPP)"
_MOPP_INDEX_PATH = "/guidance/manual-of-patent-practice-mopp"

# Lean snippet cap (§5.5). Truncate so a multi-hit page fits comfortably
# under the §5.5 token budget.
_MOPP_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a MoPP search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates anything snippet-shaped. Use ``get_mopp_section`` for the
    full content of any hit.
    """
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number = None
    title_only = title
    for part in path_parts:
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    if section_number and title.startswith(f"{section_number} - "):
        title_only = title[len(section_number) + 3 :]
    return {
        "section_number": section_number,
        "title": title_only,
        "snippet": truncate(title_only, _MOPP_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single MoPP section."""
    title = record.get("title") or "(no title)"
    href = record.get("href") or ""
    head = f"**MoPP {corpus_version} — {title}**"
    if href:
        slug = href.lstrip("-")
        return f"{head}\nSource: {_MOPP_BASE}{_MOPP_INDEX_PATH}/{slug}"
    return head


# ---------------------------------------------------------------------------
# search_mopp
# ---------------------------------------------------------------------------


@ukipo_mopp_mcp.tool(annotations=READ_ONLY)
async def search_mopp(
    query: Annotated[
        str,
        "Search query. Examples: 'inventive step', 'methods of treatment', "
        "'industrial application'. By default treated as an adjacent-word "
        "phrase; set ``syntax='or'`` to widen.",
    ],
    limit: Limit100 = 25,
    offset: Offset = 0,
    syntax: Annotated[
        str,
        "Query syntax. 'adj' (default) — adjacent-word phrase match. "
        "'and' — all terms must match. 'or' — any term matches. 'exact' — same as 'adj'.",
    ] = "adj",
    sort: Annotated[
        str,
        "'relevance' (BM25, default) or 'outline' (section ordering ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: section_number, "
        "title, snippet, href. When True, returns the upstream "
        "MoppSearchHit shape (title prefixed with section number, the full "
        "result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the UKIPO Manual of Patent Practice (MoPP) for relevant sections.

    The Manual of Patent Practice (MoPP) is the UK Intellectual Property
    Office's examination manual — controlling UK Patents Act 1977
    practice, patentability standards, and prosecution before the
    UKIPO. The UK equivalent of the USPTO's MPEP. Returns relevance-
    ranked hits with truncated metadata by default; use
    ``get_mopp_section`` for the full section text by PA 1977 section
    number or gov.uk slug. Pass ``full=True`` to get the upstream-
    shaped row.

    Examples:
      * Patentability: query='inventive step'
      * Section 4A exclusions: query='methods of treatment'
      * Industry: query='industrial application'

    Related tools: get_mopp_section.
    """
    return await corpus_search(
        MoppClient,
        lambda client: client.search(
            query=query,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            offset=offset,
        ),
        corpus_status=get_corpus_status,
        project=None if full else _stub_hit,
        summary=lambda response, items, corpus_label: hits_summary(
            f"MoPP ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=f"{_MOPP_BASE}{_MOPP_INDEX_PATH}",
        source_name=_MOPP_NAME,
    )


# ---------------------------------------------------------------------------
# get_mopp_section
# ---------------------------------------------------------------------------


@ukipo_mopp_mcp.tool(annotations=READ_ONLY)
async def get_mopp_section(
    section: Annotated[
        str | list[str],
        "MoPP section identifier. Accepts a UK Patents Act 1977 section "
        "number ('1', '14', '100', '4A'), a gov.uk slug "
        "('section-1-patentability', 'glossary-of-terms-...'), or a list of "
        "either for portfolio workflows. Examples: '1', "
        "['1', '4A', '14', 'glossary-of-terms-and-abbreviations-used-in-this-manual'].",
    ],
) -> FetchedList[dict]:
    """Get one or more UKIPO Manual of Patent Practice (MoPP) sections by number or slug.

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single section reference or a list (§5.4);
    the response is always a ListEnvelope so the shape is stable.
    Bounded concurrent fan-out internally; order matches the input.

    The MoPP (Manual of Patent Practice) is the UKIPO's examination
    manual — the UK counterpart to the USPTO's MPEP. MoPP pages are
    organized by Patents Act 1977 section number; subsection citations
    (e.g. '1.07', '14.99') appear within each page's body. The bundled
    corpus version is surfaced in ``provenance.corpus_version`` so
    agents can quote freshness.

    Related tools: search_mopp.
    """
    refs = as_id_list(section, noun="MoPP section reference")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return record.model_dump()

    def _source_url(items: list[dict], corpus_label: str) -> str:
        if len(refs) == 1 and items:
            href = items[0].get("href") or refs[0]
            return f"{_MOPP_BASE}{_MOPP_INDEX_PATH}/{href.lstrip('-')}"
        return f"{_MOPP_BASE}{_MOPP_INDEX_PATH}"

    return await corpus_get(
        MoppClient,
        refs,
        _fetch_one,
        single=isinstance(section, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"MoPP section {ref} — not found.",
        noun_plural="MoPP sections",
        source_url=_source_url,
        source_name=_MOPP_NAME,
    )


__all__ = ["ukipo_mopp_mcp", "search_mopp", "get_mopp_section"]
