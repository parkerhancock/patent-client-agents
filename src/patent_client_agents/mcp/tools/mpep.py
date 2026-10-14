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

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.mpep import MpepClient, get_corpus_status
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

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

# Lean snippet cap (§5.5). FTS5 already returns short snippets, but the
# raw column can blow past this when the surrounding context is dense
# (e.g. examination-procedure tables). Truncate so a 25-hit page fits
# comfortably under the §5.5 token budget.
_MPEP_LEAN_SNIPPET_CHARS = 400


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
        "snippet": truncate(hit.get("snippet") or "", _MPEP_LEAN_SNIPPET_CHARS),
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
        "the upstream MpepSearchHit shape (title prefixed with section_number, "
        "the full result_url, and the path breadcrumb).",
    ] = False,
    version: Annotated[
        str, "Installed release identifier; current selects the installed snapshot."
    ] = "current",
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
    return await corpus_search(
        MpepClient,
        lambda client: client.search(
            query=query,
            version=version,
            syntax=syntax,
            sort=sort,
            per_page=limit,
            offset=offset,
        ),
        corpus_status=get_corpus_status,
        project=None if full else _stub_hit,
        summary=lambda response, items, corpus_label: hits_summary(
            f"MPEP ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=f"{_MPEP_BASE}/RDMS/MPEP/search",
        source_name=_MPEP_NAME,
    )


# ---------------------------------------------------------------------------
# get_mpep_section
# ---------------------------------------------------------------------------


@mpep_mcp.tool(annotations=READ_ONLY)
async def get_mpep_section(
    section: Annotated[
        str | int | list[str | int],
        "MPEP section number (e.g. '2106', '2106.04(a)', '706.03(a)(1)'), an "
        "eMPEP href ('d0e122292.html'), or a list of either for portfolio "
        "workflows. Examples: '2106', ['2106', '2143', '706.03(a)'].",
    ],
    version: Annotated[
        str, "Installed release identifier; unsupported retained versions fail."
    ] = "current",
) -> FetchedList[dict]:
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
    single = isinstance(section, str | int)
    refs = as_id_list(
        str(section) if single else [str(ref) for ref in section],
        noun="MPEP section reference",
    )

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref, version=version)
        # When the caller passes a section number, ``ref`` already is
        # the section number. When they pass an href, we don't have
        # the section number on the model itself; the breadcrumb on
        # the corpus row carries it but the MpepSection model drops
        # it. Resolve via the corpus' SECTION_NUMBER_PATTERN so the
        # returned dict carries section_number when we know it.
        from patent_client_agents.mpep.client import SECTION_NUMBER_PATTERN

        section_number = ref if SECTION_NUMBER_PATTERN.match(ref) else None
        return _section_to_dict(record, section_number=section_number)

    def _source_url(items: list[dict], corpus_label: str) -> str:
        if len(refs) == 1 and items:
            # If the single ref looks like an href, point provenance at the
            # canonical result URL for that href; otherwise at the section
            # number path.
            ref = refs[0]
            if ref.endswith(".html") or "/" in ref:
                return f"{_MPEP_BASE}/RDMS/MPEP/result?href={ref.lstrip('/')}"
            return f"{_MPEP_BASE}/RDMS/MPEP/result?section={ref}"
        return f"{_MPEP_BASE}/RDMS/MPEP/result"

    return await corpus_get(
        MpepClient,
        refs,
        _fetch_one,
        single=single,
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"MPEP section {ref} — not found.",
        noun_plural="MPEP sections",
        source_url=_source_url,
        source_name=_MPEP_NAME,
    )


__all__ = ["mpep_mcp", "search_mpep", "get_mpep_section"]
