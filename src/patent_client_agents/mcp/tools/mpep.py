"""Manual of Patent Examining Procedure (MPEP) MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The MPEP corpus is a SQLite/FTS5 snapshot
materialized by ``patent-client-agents-build-mpep-corpus``; every
response stamps ``Provenance.corpus_synced_at`` and ``corpus_version``
read from :func:`patent_client_agents.mpep.get_corpus_status` so agents
can warn when the bundle is stale (§4).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.mpep import MpepClient, get_corpus_status

mpep_mcp = FastMCP("MPEP")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). MPEP is substantive
# law served from a locally-bundled SQLite snapshot (§4 / coverage/
# sources.yaml), so Provenance carries corpus_synced_at + corpus_version
# in addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_MPEP_BASE = "https://mpep.uspto.gov"
_MPEP_NAME = "USPTO MPEP (Manual of Patent Examining Procedure)"

# Bounded fan-out for list-accepting get_mpep_section (§5.4). SQLite reads
# are fast so the concurrency budget is conservative — the cap exists so a
# 50-section portfolio doesn't open 50 connections at once.
_MPEP_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5). FTS5 already returns short snippets, but the
# raw column can blow past this when the surrounding context is dense
# (e.g. examination-procedure tables). Truncate so a 25-hit page fits
# comfortably under the §5.5 token budget.
_MPEP_LEAN_SNIPPET_CHARS = 400


def _mpep_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.mpep.get_corpus_status` so the values
    track the bundled corpus without per-call hardcoding. This is the
    template all 8 ``mcp_local`` substantive-law corpora in row 18 copy.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_MPEP_BASE}{path}",
        source_name=_MPEP_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _stub_hit(hit: Any) -> dict:
    """Lean projection of an MPEP search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates the snippet to keep multi-hit pages cheap. Use
    ``get_mpep_section`` for the full content of any hit.
    """
    # hit is an MpepSearchHit dump: title (e.g. "2106 - Patent Subject...")
    # carries the section number first; expose them separately so agents
    # don't need to parse the string.
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number = None
    title_only = title
    for part in path_parts:
        # path looks like ["Chapter 2100", "2106"]; the last entry that is
        # NOT a "Chapter ..." string is the section number.
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    if section_number and title.startswith(f"{section_number} - "):
        title_only = title[len(section_number) + 3 :]
    return {
        "section_number": section_number,
        "title": title_only,
        "snippet": _truncate(hit.get("snippet") or "", _MPEP_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single MPEP section record.

    Leads with the corpus version so the agent can quote it directly
    when warning about staleness (§4 + §5.13).
    """
    section_number = record.get("section_number") or "(no §)"
    title = record.get("title") or "(no title)"
    href = record.get("href") or ""
    head = f"**MPEP {corpus_version} — §{section_number}: {title}**"
    if href:
        return f"{head}\nSource: {_MPEP_BASE}/RDMS/MPEP/result?href={href}"
    return head


def _section_to_dict(section: Any, *, section_number: str | None) -> dict:
    """Dump an MpepSection model and re-attach the section_number we resolved.

    The model carries href + html + text + title + version, but not the
    practitioner-facing section_number (eMPEP stores section_number on
    the corpus row, not the MpepSection model). We surface it on the
    returned dict so agents can quote it without round-tripping.
    """
    data = section.model_dump() if hasattr(section, "model_dump") else dict(section)
    data["section_number"] = section_number
    return data


# ---------------------------------------------------------------------------
# search_mpep
# ---------------------------------------------------------------------------


@mpep_mcp.tool(annotations=READ_ONLY)
async def search_mpep(
    query: Annotated[
        str,
        "Search query. Examples: 'subject matter eligibility', 'inventive step', "
        "'restriction requirement'. By default treated as an adjacent-word phrase; "
        "set ``syntax='or'`` to widen.",
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
        "'relevance' (BM25, default) or 'outline' (section_number ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: section_number, "
        "title, snippet (truncated to ~400 chars), href. When True, returns "
        "the upstream MpepSearchHit shape (title prefixed with section_number, "
        "the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the Manual of Patent Examining Procedure (MPEP) for relevant sections.

    The MPEP is the USPTO examiner's manual — controlling examination
    procedure, patentability standards, and prosecution practice.
    Returns relevance-ranked hits with truncated snippets by default;
    use ``get_mpep_section`` for the full section text by section number
    or href. Pass ``full=True`` to get the upstream-shaped row.

    Examples:
      * Alice/Mayo guidance: query='subject matter eligibility'
      * Obviousness factors: query='Graham factors', syntax='adj'
      * Restriction practice: query='restriction requirement'

    Related tools: get_mpep_section.
    """
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    # Translate the offset/limit pair into the underlying client's page/per_page.
    page = (offset // limit) + 1 if offset >= 0 else 1
    async with MpepClient() as client:
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
    summary = f"MPEP ({corpus_label}) — `{query}`: {len(items)} hit{'s' if len(items) != 1 else ''}"
    if response.has_more:
        summary += " (more available)."
    else:
        summary += "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=_mpep_provenance("/RDMS/MPEP/search"),
    )


# ---------------------------------------------------------------------------
# get_mpep_section
# ---------------------------------------------------------------------------


@mpep_mcp.tool(annotations=READ_ONLY)
async def get_mpep_section(
    section: Annotated[
        str | list[str],
        "MPEP section number (e.g. '2106', '2106.04(a)', '706.03(a)(1)'), an "
        "eMPEP href ('d0e122292.html'), or a list of either for portfolio "
        "workflows. Examples: '2106', ['2106', '2143', '706.03(a)'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more MPEP sections by number (or eMPEP href).

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single section reference or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally; order matches the input.

    The MPEP is the Manual of Patent Examining Procedure — the USPTO
    examiner's manual controlling patentability standards and prosecution
    practice. The bundled corpus version is surfaced in
    ``provenance.corpus_version`` so agents can quote freshness.

    Related tools: search_mpep.
    """
    refs = [section] if isinstance(section, str) else list(section)
    if not refs:
        raise ValidationError("get_mpep_section requires at least one section reference")

    semaphore = asyncio.Semaphore(_MPEP_FANOUT_CONCURRENCY)

    async def _fetch_one(client: MpepClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section(ref)
            # When the caller passes a section number, ``ref`` already is
            # the section number. When they pass an href, we don't have
            # the section number on the model itself; the breadcrumb on
            # the corpus row carries it but the MpepSection model drops
            # it. Resolve via the corpus' SECTION_NUMBER_PATTERN so the
            # returned dict carries section_number when we know it.
            from patent_client_agents.mpep.client import SECTION_NUMBER_PATTERN

            section_number = ref if SECTION_NUMBER_PATTERN.match(ref) else None
            return _section_to_dict(record, section_number=section_number)

    async with MpepClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
        # If the single ref looks like an href, point provenance at the
        # canonical result URL for that href; otherwise at the section
        # number path.
        ref = refs[0]
        if ref.endswith(".html") or "/" in ref:
            path = f"/RDMS/MPEP/result?href={ref.lstrip('/')}"
        else:
            path = f"/RDMS/MPEP/result?section={ref}"
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} MPEP sections ({corpus_label}): {joined}"
        path = "/RDMS/MPEP/result"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_mpep_provenance(path),
    )


__all__ = ["mpep_mcp", "search_mpep", "get_mpep_section"]
