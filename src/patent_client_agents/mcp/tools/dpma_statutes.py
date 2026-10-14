"""DPMA Germany IP statutes MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
``update_cadence=annual`` (per ``coverage/sources.yaml``). The corpus
bundles six German IP Acts (PatG, MarkenG, GebrMG, DesignG, UrhG,
GeschGehG) into one SQLite/FTS5 snapshot materialized by
``patent-client-agents-build-dpma-statutes-corpus``. Every response
stamps ``Provenance.corpus_synced_at`` / ``corpus_version`` read from
:func:`patent_client_agents.dpma_statutes.get_corpus_status` so
agents can warn when the bundle is stale (§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.dpma_statutes import (
    DpmaStatutesClient,
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

dpma_statutes_mcp = FastMCP("DPMA Germany — Statutes")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). DPMA statutes are
# substantive law served from a locally-bundled SQLite snapshot, so
# Provenance carries corpus_synced_at + corpus_version in addition to
# the standard fields. Both are read from ``get_corpus_status()`` once
# per request — NEVER hardcoded — so a corpus refresh propagates
# without a code change here.
# ──────────────────────────────────────────────────────────────────────

_DPMA_SOURCE_NAME = "DPMA Germany — IP statutes"
_GESETZE_BASE = "https://www.gesetze-im-internet.de"

# Lean snippet cap (§5.5).
_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a statute search hit (§5.5)."""
    return {
        "statute": hit.get("statute"),
        "section": hit.get("section"),
        "title": hit.get("title"),
        "snippet": truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single statute section."""
    statute = record.get("statute") or "(unknown statute)"
    num = record.get("section") or "?"
    title = record.get("title")
    head = f"**§ {num} {statute}**"
    if title:
        head += f" — {title}"
    return f"{head}\nSource: DPMA Germany statutes corpus ({corpus_version})"


# ---------------------------------------------------------------------------
# search_dpma_statutes
# ---------------------------------------------------------------------------


@dpma_statutes_mcp.tool(annotations=READ_ONLY)
async def search_dpma_statutes(
    query: Annotated[
        str,
        "Search query. Examples: 'Patentverletzung', 'erfinderische Tätigkeit', "
        "'Markenanmeldung', 'Geschäftsgeheimnis'. Default 'and' syntax means "
        "every term must appear; pass syntax='or' to widen.",
    ],
    statute: Annotated[
        str | None,
        "Optional Act filter — 'PatG', 'MarkenG', 'GebrMG', 'DesignG', "
        "'UrhG', or 'GeschGehG' (case-insensitive; long-form aliases "
        "like 'Patentgesetz' accepted). Omit to search across all six.",
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
        "When False (default), each hit is a lean stub: statute, section, "
        "title, snippet. When True, returns the upstream DpmaSearchHit "
        "shape with the BM25 rank.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search German IP statutes (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG).

    The corpus bundles six core German IP Acts — pass ``statute=`` to
    constrain to one Act, or omit to search across all six. Use
    ``get_dpma_section`` for the full section text by citation
    (e.g. '§ 139 PatG').

    Examples:
      * Patent infringement:        query='Unterlassung', statute='PatG'
      * Inventive step:             query='erfinderische Tätigkeit'
      * Trade mark exclusive right: query='ausschließliches Recht', statute='MarkenG'
      * Trade secret definition:    query='Geschäftsgeheimnis'

    Related tools: get_dpma_section.
    """

    def _summary(response: Any, items: list[dict], corpus_label: str) -> str:
        scope = f" ({response.statute})" if response.statute else ""
        return hits_summary(
            f"DPMA Germany statutes{scope} — `{query}`",
            len(items),
            response.has_more,
            f" (corpus {corpus_label})",
        )

    return await corpus_search(
        DpmaStatutesClient,
        lambda client: client.search(
            query,
            statute=statute,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            offset=offset,
        ),
        corpus_status=get_corpus_status,
        project=None if full else _stub_hit,
        summary=_summary,
        source_url=f"{_GESETZE_BASE}/",
        source_name=_DPMA_SOURCE_NAME,
    )


# ---------------------------------------------------------------------------
# get_dpma_section
# ---------------------------------------------------------------------------


@dpma_statutes_mcp.tool(annotations=READ_ONLY)
async def get_dpma_section(
    citation: Annotated[
        str | list[str],
        "Statute citation. Accepts: '§ 1 PatG', '§ 139 PatG', '§ 14 MarkenG', "
        "'§ 1 GebrMG', '§ 5 GeschGehG'. Also 'Section 14 MarkenG' / 'S. 139 PatG' "
        "shorthand. Pass a list for portfolio workflows. Examples: "
        "'§ 139 PatG', ['§ 1 PatG', '§ 14 MarkenG', '§ 97 UrhG'].",
    ],
) -> FetchedList[dict]:
    """Get one or more sections of the bundled German IP Acts by citation.

    Accepts free-text citations like '§ 139 PatG' or 'Section 14 MarkenG';
    the parser extracts the section number and statute short-name. Bare
    section numbers ('139') resolve when the number is unique across the
    bundled Acts. Pass a list for portfolio workflows (§5.4); the
    response shape stays a ``ListEnvelope`` with order preserved.

    The bundled corpus version is surfaced in
    ``provenance.corpus_version`` so agents can quote freshness.

    Related tools: search_dpma_statutes.
    """
    refs = as_id_list(citation, noun="DPMA statute citation")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section_by_citation(ref)
        return record.model_dump()

    return await corpus_get(
        DpmaStatutesClient,
        refs,
        _fetch_one,
        single=isinstance(citation, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"DPMA statute section {ref} — not found.",
        noun_plural="DPMA statute sections",
        source_url=f"{_GESETZE_BASE}/",
        source_name=_DPMA_SOURCE_NAME,
    )


__all__ = ["dpma_statutes_mcp", "search_dpma_statutes", "get_dpma_section"]

# Re-export so tests can patch from this module path.
parse_citation = parse_citation  # noqa: PLW0127 — explicit re-export for symmetry
