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

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.epo_up_guidelines import UpGuidelinesClient, get_corpus_status

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

# Bounded fan-out for list-accepting get_epo_up_guidelines_section
# (§5.4). SQLite reads are fast so the concurrency budget is
# conservative — the cap exists so a multi-section portfolio doesn't
# open many connections at once.
_UP_GUIDELINES_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5). Truncate so a multi-hit page fits comfortably
# under the §5.5 token budget.
_UP_GUIDELINES_LEAN_SNIPPET_CHARS = 400


def _up_guidelines_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.epo_up_guidelines.get_corpus_status`
    so the values track the bundled corpus without per-call hardcoding.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_UP_GUIDELINES_BASE}{path}",
        source_name=_UP_GUIDELINES_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


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
        "snippet": _truncate(title_only, _UP_GUIDELINES_LEAN_SNIPPET_CHARS),
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
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    page = (offset // limit) + 1 if offset >= 0 else 1
    async with UpGuidelinesClient() as client:
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
    summary = (
        f"UP Guidelines ({corpus_label}) — `{query}`: "
        f"{len(items)} hit{'s' if len(items) != 1 else ''}"
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
        provenance=_up_guidelines_provenance("/en/legal/guidelines-up"),
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
) -> ListEnvelope[dict]:
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
    refs = [section] if isinstance(section, str) else list(section)
    if not refs:
        raise ValidationError(
            "get_epo_up_guidelines_section requires at least one section reference"
        )

    semaphore = asyncio.Semaphore(_UP_GUIDELINES_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UpGuidelinesClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section(ref)
            return record.model_dump()

    async with UpGuidelinesClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
        ref = refs[0]
        href = results[0].get("href") or ref
        path = f"/en/legal/guidelines-up/{corpus_label}/{href}"
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} UP Guidelines sections ({corpus_label}): {joined}"
        path = "/en/legal/guidelines-up"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_up_guidelines_provenance(path),
    )


__all__ = [
    "epo_up_guidelines_mcp",
    "search_epo_up_guidelines",
    "get_epo_up_guidelines_section",
]
