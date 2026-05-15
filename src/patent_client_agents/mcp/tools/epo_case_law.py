"""EPO Case Law of the Boards of Appeal MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The Case Law corpus is a SQLite/FTS5
snapshot materialized by ``patent-client-agents-build-caselaw-corpus``
covering Parts I-VII of the EPO Boards of Appeal "white book" — the
canonical compilation of case law referenced constantly in European
patent prosecution and opposition. Every response stamps
``Provenance.corpus_synced_at`` and ``corpus_version`` read from
:func:`patent_client_agents.epo_case_law.get_corpus_status` so agents
can warn when the bundle is stale (§4).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.epo_case_law import CaseLawClient, get_corpus_status
from patent_client_agents.epo_case_law.client import _CITATION_PATTERN, _SLUG_PATTERN

epo_case_law_mcp = FastMCP("EPO Case Law")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). EPO Case Law is
# substantive law served from a locally-bundled SQLite snapshot
# (§4 / coverage/sources.yaml), so Provenance carries corpus_synced_at +
# corpus_version in addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_CASELAW_BASE = "https://www.epo.org"
_CASELAW_NAME = "EPO Boards of Appeal Case Law Compendium"

# Bounded fan-out for list-accepting get_epo_case_law_section (§5.4).
_CASELAW_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5).
_CASELAW_LEAN_SNIPPET_CHARS = 400


def _caselaw_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.epo_case_law.get_corpus_status` so the
    values track the bundled corpus without per-call hardcoding. Mirrors
    the MPEP template for substantive-law ``mcp_local`` corpora.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_CASELAW_BASE}{path}",
        source_name=_CASELAW_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _stub_hit(hit: dict) -> dict:
    """Lean projection of a Case Law search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates the snippet to keep multi-hit pages cheap. Use
    ``get_epo_case_law_section`` for the full content of any hit.
    """
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number: str | None = None
    for part in path_parts:
        if isinstance(part, str) and not part.lower().startswith("part"):
            section_number = part
    return {
        "section_number": section_number,
        "title": title,
        "snippet": _truncate(hit.get("snippet") or "", _CASELAW_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single Case Law section record."""
    href = record.get("href") or ""
    title = record.get("title") or "(no title)"
    head = f"**EPO Case Law {corpus_version} — {title}**"
    if href:
        return f"{head}\nSource: {_CASELAW_BASE}/en/legal/case-law/{corpus_version}/{href}.html"
    return head


def _section_to_dict(section: Any) -> dict:
    """Dump a CaseLawSection model to a dict."""
    if hasattr(section, "model_dump"):
        return section.model_dump()
    return dict(section)


def _looks_like_section_ref(ref: str) -> bool:
    """True if ``ref`` is a citation form or bare slug (not an URL/href path)."""
    cleaned = ref.strip()
    if _CITATION_PATTERN.match(cleaned):
        return True
    if _SLUG_PATTERN.match(cleaned):
        return True
    return False


# ---------------------------------------------------------------------------
# search_epo_case_law
# ---------------------------------------------------------------------------


@epo_case_law_mcp.tool(annotations=READ_ONLY)
async def search_epo_case_law(
    query: Annotated[
        str,
        "Search query. Examples: 'problem-and-solution approach', "
        "'inventive step', 'sufficiency of disclosure'. By default treated "
        "as an adjacent-word phrase; set ``syntax='or'`` to widen.",
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
        "the upstream CaseLawSearchHit shape (title prefixed with "
        "section_number, the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the EPO Case Law of the Boards of Appeal ("white book").

    The canonical compilation of EPO Boards of Appeal case law,
    organized into Parts I-VII, covering how the EPC has been
    interpreted in practice — the reference work for European patent
    prosecution and opposition. Returns relevance-ranked hits with
    truncated snippets by default; use ``get_epo_case_law_section`` for
    the full section text. Pass ``full=True`` to get the upstream-shaped
    row.

    Examples:
      * Inventive step (Part I.D): query='problem-and-solution approach'
      * Sufficiency (Part II.C): query='sufficiency of disclosure'
      * Added subject-matter (Part II.E): query='added subject-matter'

    Related tools: get_epo_case_law_section.
    """
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    page = (offset // limit) + 1 if offset >= 0 else 1
    async with CaseLawClient() as client:
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
        f"EPO Case Law ({corpus_label}) — `{query}`: "
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
        provenance=_caselaw_provenance("/en/legal/case-law"),
    )


# ---------------------------------------------------------------------------
# get_epo_case_law_section
# ---------------------------------------------------------------------------


@epo_case_law_mcp.tool(annotations=READ_ONLY)
async def get_epo_case_law_section(
    section: Annotated[
        str | list[str],
        "Case Law section identifier or a list of identifiers. Accepts "
        "canonical citations like 'I.A.1' / 'I-A-1' / 'I A 1', URL slugs "
        "like 'clr_i_a_1', or full epo.org URLs. Examples: 'I.D.3', "
        "['I.D.3', 'II.E.1', 'II.C.4'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more EPO Case Law sections by citation or slug.

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single citation or a list (§5.4); the response
    is always a ListEnvelope so the shape is stable. Bounded concurrent
    fan-out internally; order matches the input.

    The EPO Case Law of the Boards of Appeal is the canonical compendium
    of how the EPC has been interpreted by the Boards — the reference
    for European patent prosecution and opposition. The bundled corpus
    version is surfaced in ``provenance.corpus_version`` so agents can
    quote freshness.

    Related tools: search_epo_case_law.
    """
    refs = [section] if isinstance(section, str) else list(section)
    if not refs:
        raise ValidationError("get_epo_case_law_section requires at least one section reference")

    semaphore = asyncio.Semaphore(_CASELAW_FANOUT_CONCURRENCY)

    async def _fetch_one(client: CaseLawClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section(ref)
            return _section_to_dict(record)

    async with CaseLawClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
        ref = refs[0]
        href = results[0].get("href")
        if href and _looks_like_section_ref(ref):
            path = f"/en/legal/case-law/{corpus_label}/{href}.html"
        else:
            path = "/en/legal/case-law"
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} EPO Case Law sections ({corpus_label}): {joined}"
        path = "/en/legal/case-law"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_caselaw_provenance(path),
    )


__all__ = [
    "epo_case_law_mcp",
    "search_epo_case_law",
    "get_epo_case_law_section",
]
