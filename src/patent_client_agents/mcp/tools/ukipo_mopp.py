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

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
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

# Bounded fan-out for list-accepting get_mopp_section (§5.4). SQLite
# reads are fast so the concurrency budget is conservative — the cap
# exists so a multi-section portfolio doesn't open many connections at
# once.
_MOPP_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5). Truncate so a multi-hit page fits comfortably
# under the §5.5 token budget.
_MOPP_LEAN_SNIPPET_CHARS = 400


def _mopp_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.ukipo_mopp.get_corpus_status` so the
    values track the bundled corpus without per-call hardcoding.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_MOPP_BASE}{path}",
        source_name=_MOPP_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


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
        "snippet": _truncate(title_only, _MOPP_LEAN_SNIPPET_CHARS),
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
    limit: Annotated[int, "Maximum hits to return (1-100)."] = 25,
    offset: Annotated[int, "Result offset for pagination."] = 0,
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
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    page = (offset // limit) + 1 if offset >= 0 else 1
    async with MoppClient() as client:
        response = await client.search(
            query=query,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            page=page,
        )

    hits = [h.model_dump() for h in response.hits]
    items = hits if full else [_stub_hit(h) for h in hits]

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    summary = f"MoPP ({corpus_label}) — `{query}`: {len(items)} hit{'s' if len(items) != 1 else ''}"
    if response.has_more:
        summary += " (more available)."
    else:
        summary += "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=_mopp_provenance(_MOPP_INDEX_PATH),
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
) -> ListEnvelope[dict]:
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
    refs = [section] if isinstance(section, str) else list(section)
    if not refs:
        raise ValidationError("get_mopp_section requires at least one section reference")

    semaphore = asyncio.Semaphore(_MOPP_FANOUT_CONCURRENCY)

    async def _fetch_one(client: MoppClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section(ref)
            return record.model_dump()

    async with MoppClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
        href = results[0].get("href") or refs[0]
        path = f"{_MOPP_INDEX_PATH}/{href.lstrip('-')}"
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} MoPP sections ({corpus_label}): {joined}"
        path = _MOPP_INDEX_PATH

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_mopp_provenance(path),
    )


__all__ = ["ukipo_mopp_mcp", "search_mopp", "get_mopp_section"]
