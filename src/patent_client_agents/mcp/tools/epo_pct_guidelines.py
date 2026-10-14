"""PCT-EPO Guidelines for Examination MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The PCT-EPO Guidelines corpus is a SQLite/
FTS5 snapshot materialized by
``patent-client-agents-build-pct-guidelines-corpus``; every response
stamps ``Provenance.corpus_synced_at`` and ``corpus_version`` read from
:func:`patent_client_agents.epo_pct_guidelines.get_corpus_status` so
agents can warn when the bundle is stale (§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.epo_pct_guidelines import PctGuidelinesClient, get_corpus_status
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

epo_pct_guidelines_mcp = FastMCP("EPO PCT-EPO Guidelines")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The PCT-EPO Guidelines
# are substantive law served from a locally-bundled SQLite snapshot
# (§4 / coverage/sources.yaml), so Provenance carries corpus_synced_at +
# corpus_version in addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_PCT_GUIDELINES_BASE = "https://www.epo.org"
_PCT_GUIDELINES_NAME = "PCT-EPO Guidelines for Examination"

# Lean snippet cap (§5.5). Truncate so a multi-hit page fits comfortably
# under the §5.5 token budget.
_PCT_GUIDELINES_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a PCT-EPO Guidelines search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates anything snippet-shaped. Use
    ``get_epo_pct_guidelines_section`` for the full content of any hit.
    """
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number = None
    title_only = title
    for part in path_parts:
        # path looks like ["Chapter G-II", "G-II, 3.1"]; the last entry
        # that is NOT a "Chapter ..." string is the section number.
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    if section_number and title.startswith(f"{section_number} - "):
        title_only = title[len(section_number) + 3 :]
    return {
        "section_number": section_number,
        "title": title_only,
        "snippet": truncate(title_only, _PCT_GUIDELINES_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single PCT-EPO Guidelines section."""
    title = record.get("title") or "(no title)"
    href = record.get("href") or ""
    head = f"**PCT-EPO Guidelines {corpus_version} — {title}**"
    if href:
        return f"{head}\nSource: {_PCT_GUIDELINES_BASE}/en/legal/guidelines-pct/{corpus_version}/{href}.html"
    return head


# ---------------------------------------------------------------------------
# search_epo_pct_guidelines
# ---------------------------------------------------------------------------


@epo_pct_guidelines_mcp.tool(annotations=READ_ONLY)
async def search_epo_pct_guidelines(
    query: Annotated[
        str,
        "Search query. Examples: 'subject matter excluded from international search', "
        "'unity of invention', 'amendments under Article 19'. By default treated as an "
        "adjacent-word phrase; set ``syntax='or'`` to widen.",
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
        "PctGuidelinesSearchHit shape (title prefixed with section number, "
        "the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the PCT-EPO Guidelines for Examination for relevant sections.

    The PCT-EPO Guidelines govern EPO practice when acting as
    International Searching Authority, International Preliminary
    Examining Authority, or Receiving Office under the Patent
    Cooperation Treaty (PCT). Returns relevance-ranked hits with
    truncated metadata by default; use
    ``get_epo_pct_guidelines_section`` for the full section text by
    citation or href. Pass ``full=True`` to get the upstream-shaped row.

    Examples:
      * ISA exclusions: query='subject matter excluded from international search'
      * Unity: query='unity of invention', syntax='and'
      * Amendments: query='amendments under Article 19'

    Related tools: get_epo_pct_guidelines_section.
    """
    return await corpus_search(
        PctGuidelinesClient,
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
            f"PCT-EPO Guidelines ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=f"{_PCT_GUIDELINES_BASE}/en/legal/guidelines-pct",
        source_name=_PCT_GUIDELINES_NAME,
    )


# ---------------------------------------------------------------------------
# get_epo_pct_guidelines_section
# ---------------------------------------------------------------------------


@epo_pct_guidelines_mcp.tool(annotations=READ_ONLY)
async def get_epo_pct_guidelines_section(
    section: Annotated[
        str | list[str],
        "PCT-EPO Guidelines section identifier. Accepts canonical citations like "
        "'G-II, 3.1', 'G-II 3.1', or 'G.II.3.1'; URL slugs like 'g_ii_3_1' / "
        "'g_ii_3_1.html'; or a list of either for portfolio workflows. Examples: "
        "'G-II, 3.1', ['G-II, 3.1', 'G-III, 1', 'B-IV, 1.1'].",
    ],
) -> FetchedList[dict]:
    """Get one or more PCT-EPO Guidelines for Examination sections by citation or href.

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single section reference or a list (§5.4);
    the response is always a ListEnvelope so the shape is stable.
    Bounded concurrent fan-out internally; order matches the input.

    The PCT-EPO Guidelines govern EPO practice when acting as
    International Searching Authority, International Preliminary
    Examining Authority, or Receiving Office under the Patent
    Cooperation Treaty. The bundled corpus version (typically the
    publication year) is surfaced in ``provenance.corpus_version`` so
    agents can quote freshness.

    Related tools: search_epo_pct_guidelines.
    """
    refs = as_id_list(section, noun="PCT-EPO Guidelines section reference")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return record.model_dump()

    def _source_url(items: list[dict], corpus_label: str) -> str:
        if len(refs) == 1 and items:
            # Single-record provenance points at the canonical section URL.
            href = items[0].get("href") or refs[0]
            return f"{_PCT_GUIDELINES_BASE}/en/legal/guidelines-pct/{corpus_label}/{href}.html"
        return f"{_PCT_GUIDELINES_BASE}/en/legal/guidelines-pct"

    return await corpus_get(
        PctGuidelinesClient,
        refs,
        _fetch_one,
        single=isinstance(section, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"PCT-EPO Guidelines section {ref} — not found.",
        noun_plural="PCT-EPO Guidelines sections",
        source_url=_source_url,
        source_name=_PCT_GUIDELINES_NAME,
    )


__all__ = [
    "epo_pct_guidelines_mcp",
    "search_epo_pct_guidelines",
    "get_epo_pct_guidelines_section",
]
