"""EPO Unitary Patent (UP) Guidelines MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The UP Guidelines corpus is a SQLite/FTS5
snapshot materialized by
``patent-client-agents-build-up-guidelines-corpus``; every response
stamps ``Provenance.corpus_synced_at`` and ``corpus_version`` read from
:func:`patent_client_agents.epo_up_guidelines.get_corpus_status` so
agents can warn when the bundle is stale (§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.epo_up_guidelines import UpGuidelinesClient, get_corpus_status
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

epo_up_guidelines_mcp = FastMCP("EPO UP Guidelines")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The Unitary Patent
# Guidelines are substantive law served from a locally-bundled SQLite
# snapshot (§4 / coverage/sources.yaml), so Provenance carries
# corpus_synced_at + corpus_version in addition to the standard fields.
# Both are read from ``get_corpus_status()`` once per request —
# NEVER hardcoded — so a corpus refresh propagates without a code
# change here.
# ──────────────────────────────────────────────────────────────────────

_UP_GUIDELINES_BASE = "https://www.epo.org"
_UP_GUIDELINES_NAME = "Unitary Patent Guidelines"

# Lean snippet cap (§5.5). Truncate so a multi-hit page fits comfortably
# under the §5.5 token budget.
_UP_GUIDELINES_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a UP Guidelines search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates anything snippet-shaped. Use
    ``get_epo_up_guidelines_section`` for the full content of any hit.
    """
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number = None
    title_only = title
    for part in path_parts:
        # path looks like ["Chapter 2", "2.1"]; the last entry that is
        # NOT a "Chapter ..." string is the section number.
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    if section_number and title.startswith(f"{section_number} - "):
        title_only = title[len(section_number) + 3 :]
    return {
        "section_number": section_number,
        "title": title_only,
        "snippet": truncate(title_only, _UP_GUIDELINES_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single UP Guidelines section."""
    title = record.get("title") or "(no title)"
    href = record.get("href") or ""
    head = f"**UP Guidelines {corpus_version} — {title}**"
    if href:
        return (
            f"{head}\nSource: {_UP_GUIDELINES_BASE}/en/legal/guidelines-up/{corpus_version}/{href}"
        )
    return head


# ---------------------------------------------------------------------------
# search_epo_up_guidelines
# ---------------------------------------------------------------------------


@epo_up_guidelines_mcp.tool(annotations=READ_ONLY)
async def search_epo_up_guidelines(
    query: Annotated[
        str,
        "Search query. Examples: 'unitary effect', 'renewal fees', 'opt-out'. "
        "By default treated as an adjacent-word phrase; set ``syntax='or'`` to widen.",
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
        "UpGuidelinesSearchHit shape (title prefixed with section number, "
        "the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the EPO Unitary Patent Guidelines for relevant sections.

    The Unitary Patent Guidelines govern EPO practice for the Unitary
    Patent regime — requesting unitary effect, fees, renewals, the
    Unitary Patent Protection register, and related procedures under
    the UP Regulation and Implementing Regulations. Returns
    relevance-ranked hits with truncated metadata by default; use
    ``get_epo_up_guidelines_section`` for the full section text by
    citation or slug. Pass ``full=True`` to get the upstream-shaped row.

    Examples:
      * Eligibility: query='unitary effect eligibility'
      * Fees: query='renewal fees', syntax='and'
      * Opt-out from UPC: query='opt-out'

    Related tools: get_epo_up_guidelines_section.
    """
    return await corpus_search(
        UpGuidelinesClient,
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
            f"UP Guidelines ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=f"{_UP_GUIDELINES_BASE}/en/legal/guidelines-up",
        source_name=_UP_GUIDELINES_NAME,
    )


# ---------------------------------------------------------------------------
# get_epo_up_guidelines_section
# ---------------------------------------------------------------------------


@epo_up_guidelines_mcp.tool(annotations=READ_ONLY)
async def get_epo_up_guidelines_section(
    section: Annotated[
        str | list[str],
        "UP Guidelines section identifier. Accepts citations like '1.2.1' / "
        "'1-2-1' / 'Section 1.2.1' / '§ 1.2.1'; URL slugs like 'section_1_2_1'; "
        "or a list of either for portfolio workflows. Examples: '2.1', "
        "['2.1', '3.2', 'section_4_1'].",
    ],
) -> FetchedList[dict]:
    """Get one or more EPO Unitary Patent (UP) Guidelines sections by citation or slug.

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single section reference or a list (§5.4);
    the response is always a ListEnvelope so the shape is stable.
    Bounded concurrent fan-out internally; order matches the input.

    The UP Guidelines cover the EPO's role administering the Unitary
    Patent — unitary effect requests, renewals, the UPP register, and
    related procedures. The bundled corpus version (typically the
    publication year) is surfaced in ``provenance.corpus_version`` so
    agents can quote freshness.

    Related tools: search_epo_up_guidelines.
    """
    refs = as_id_list(section, noun="UP Guidelines section reference")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return record.model_dump()

    def _source_url(items: list[dict], corpus_label: str) -> str:
        if len(refs) == 1 and items:
            href = items[0].get("href") or refs[0]
            return f"{_UP_GUIDELINES_BASE}/en/legal/guidelines-up/{corpus_label}/{href}"
        return f"{_UP_GUIDELINES_BASE}/en/legal/guidelines-up"

    return await corpus_get(
        UpGuidelinesClient,
        refs,
        _fetch_one,
        single=isinstance(section, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"UP Guidelines section {ref} — not found.",
        noun_plural="UP Guidelines sections",
        source_url=_source_url,
        source_name=_UP_GUIDELINES_NAME,
    )


__all__ = [
    "epo_up_guidelines_mcp",
    "search_epo_up_guidelines",
    "get_epo_up_guidelines_section",
]
