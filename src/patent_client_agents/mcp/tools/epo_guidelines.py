"""EPO Guidelines for Examination MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The Guidelines corpus is a SQLite/FTS5
snapshot materialized by ``patent-client-agents-build-guidelines-corpus``
covering Parts A-H of the EPO Guidelines plus the General Part — the
EPO equivalent of the USPTO's MPEP. Every response stamps
``Provenance.corpus_synced_at`` and ``corpus_version`` read from
:func:`patent_client_agents.epo_guidelines.get_corpus_status` so agents
can warn when the bundle is stale (§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.epo_guidelines import GuidelinesClient, get_corpus_status
from patent_client_agents.epo_guidelines.client import _CITATION_PATTERN, _SLUG_PATTERN
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

epo_guidelines_mcp = FastMCP("EPO Guidelines")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The Guidelines are
# substantive law served from a locally-bundled SQLite snapshot
# (§4 / coverage/sources.yaml), so Provenance carries corpus_synced_at +
# corpus_version in addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_GUIDELINES_BASE = "https://www.epo.org"
_GUIDELINES_NAME = "EPO Guidelines for Examination"

# Lean snippet cap (§5.5).
_GUIDELINES_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a Guidelines search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates the snippet to keep multi-hit pages cheap. Use
    ``get_epo_guidelines_section`` for the full content of any hit.
    """
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number: str | None = None
    for part in path_parts:
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    return {
        "section_number": section_number,
        "title": title,
        "snippet": truncate(hit.get("snippet") or "", _GUIDELINES_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single Guidelines section record."""
    href = record.get("href") or ""
    title = record.get("title") or "(no title)"
    head = f"**EPO Guidelines {corpus_version} — {title}**"
    if href:
        return f"{head}\nSource: {_GUIDELINES_BASE}/en/legal/guidelines-epc/{corpus_version}/{href}.html"
    return head


def _looks_like_section_ref(ref: str) -> bool:
    """True if ``ref`` is a citation form or bare slug (not an URL/href path)."""
    cleaned = ref.strip()
    if _CITATION_PATTERN.match(cleaned):
        return True
    if _SLUG_PATTERN.match(cleaned):
        return True
    return False


# ---------------------------------------------------------------------------
# search_epo_guidelines
# ---------------------------------------------------------------------------


@epo_guidelines_mcp.tool(annotations=READ_ONLY)
async def search_epo_guidelines(
    query: Annotated[
        str,
        "Search query. Examples: 'inventive step', 'added subject-matter', "
        "'unity of invention'. By default treated as an adjacent-word phrase; "
        "set ``syntax='or'`` to widen.",
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
        "'relevance' (BM25, default) or 'outline' (section_number ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: section_number, "
        "title, snippet (truncated to ~400 chars), href. When True, returns "
        "the upstream GuidelinesSearchHit shape (title prefixed with "
        "section_number, the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the EPO Guidelines for Examination — the EPO examiner's manual.

    Covers EPO examination practice for the EPC: Parts A (Formalities),
    B (Search), C (Examination), D (Opposition), E (Procedural matters),
    F (The application), G (Patentability), H (Amendments and corrections),
    plus the General Part. Returns relevance-ranked hits with truncated
    snippets by default; use ``get_epo_guidelines_section`` for the full
    section text. Pass ``full=True`` to get the upstream-shaped row.

    Examples:
      * Inventive step (G-VII): query='problem-and-solution approach'
      * Added subject-matter (H-IV): query='added subject-matter'
      * Patentable subject-matter (G-II): query='technical character'

    Related tools: get_epo_guidelines_section.
    """
    return await corpus_search(
        GuidelinesClient,
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
            f"EPO Guidelines ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=f"{_GUIDELINES_BASE}/en/legal/guidelines-epc",
        source_name=_GUIDELINES_NAME,
    )


# ---------------------------------------------------------------------------
# get_epo_guidelines_section
# ---------------------------------------------------------------------------


@epo_guidelines_mcp.tool(annotations=READ_ONLY)
async def get_epo_guidelines_section(
    section: Annotated[
        str | list[str],
        "EPO Guidelines section identifier or a list of identifiers. "
        "Accepts canonical citations like 'G-II, 3.1' / 'G-II 3.1' / "
        "'G.II.3.1' or URL slugs like 'g_ii_3_1'. Examples: 'G-II, 3.1', "
        "['G-II, 3.1', 'H-IV, 2', 'G-VII, 5'].",
    ],
) -> FetchedList[dict]:
    """Get one or more EPO Guidelines sections by citation or slug.

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single citation or a list (§5.4); the response
    is always a ListEnvelope so the shape is stable. Bounded concurrent
    fan-out internally; order matches the input.

    The EPO Guidelines are the EPO equivalent of the USPTO's MPEP — the
    canonical examiner's manual organized as Part (A-H) → Chapter
    (Roman) → Section → Subsection. The bundled corpus version is
    surfaced in ``provenance.corpus_version`` so agents can quote
    freshness.

    Related tools: search_epo_guidelines.
    """
    refs = as_id_list(section, noun="EPO Guidelines section reference")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return dump(record)

    def _source_url(items: list[dict], corpus_label: str) -> str:
        # If the single ref looks like a citation/slug, point provenance
        # at the specific section's URL; otherwise at the collection root.
        if len(refs) == 1 and items:
            href = items[0].get("href")
            if href and _looks_like_section_ref(refs[0]):
                return f"{_GUIDELINES_BASE}/en/legal/guidelines-epc/{corpus_label}/{href}.html"
        return f"{_GUIDELINES_BASE}/en/legal/guidelines-epc"

    return await corpus_get(
        GuidelinesClient,
        refs,
        _fetch_one,
        single=isinstance(section, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"EPO Guidelines section {ref} — not found.",
        noun_plural="EPO Guidelines sections",
        source_url=_source_url,
        source_name=_GUIDELINES_NAME,
    )


__all__ = [
    "epo_guidelines_mcp",
    "search_epo_guidelines",
    "get_epo_guidelines_section",
]
