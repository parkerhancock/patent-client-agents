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
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.dpma_statutes import (
    DpmaStatutesClient,
    get_corpus_status,
    parse_citation,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list, fetch_many, fetched_summary
from patent_client_agents.shared.provenance import provenance_for

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


def _statutes_provenance(source_url: str) -> Any:
    """Build a Provenance for the statutes corpus."""
    status = get_corpus_status()
    return provenance_for(
        source_url=source_url,
        source_name=_DPMA_SOURCE_NAME,
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
        "statute": hit.get("statute"),
        "section": hit.get("section"),
        "title": hit.get("title"),
        "snippet": _truncate(hit.get("snippet") or "", _LEAN_SNIPPET_CHARS),
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
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    page = (offset // limit) + 1 if offset >= 0 else 1
    async with DpmaStatutesClient() as client:
        response = await client.search(
            query,
            statute=statute,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            page=page,
        )

    hits = [h.model_dump() for h in response.hits]
    items = hits if full else [_stub_hit(h) for h in hits]

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    scope = f" ({response.statute})" if response.statute else ""
    summary = (
        f"DPMA Germany statutes{scope} — `{query}`: "
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
        provenance=_statutes_provenance(f"{_GESETZE_BASE}/"),
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

    async with DpmaStatutesClient() as client:

        async def _fetch_one(ref: str) -> dict:
            record = await client.get_section_by_citation(ref)
            return record.model_dump()

        items, not_found = await fetch_many(refs, _fetch_one, single=isinstance(citation, str))

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(refs) == 1 and items:
        summary = _summarize_section(items[0], corpus_label)
    elif len(refs) == 1:
        summary = f"DPMA statute section {refs[0]} — not found."
    else:
        summary = fetched_summary(len(items), len(refs), "DPMA statute sections", not_found)

    return FetchedList[dict](
        summary=summary,
        items=items,
        not_found=not_found,
        provenance=_statutes_provenance(f"{_GESETZE_BASE}/"),
    )


__all__ = ["dpma_statutes_mcp", "search_dpma_statutes", "get_dpma_section"]

# Re-export so tests can patch from this module path.
parse_citation = parse_citation  # noqa: PLW0127 — explicit re-export for symmetry
