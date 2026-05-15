"""European Patent Convention (EPC) MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The EPC corpus is a SQLite/FTS5 snapshot
materialized by ``patent-client-agents-build-epc-corpus`` covering the
180 Articles of the Convention and 176 Rules of the Implementing
Regulations; every response stamps ``Provenance.corpus_synced_at`` and
``corpus_version`` read from
:func:`patent_client_agents.epc.get_corpus_status` so agents can warn
when the bundle is stale (§4).
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.epc import EpcClient, get_corpus_status
from patent_client_agents.epc.client import _CITATION_PATTERN, _SLUG_PATTERN

epc_mcp = FastMCP("EPC")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). EPC is substantive
# law served from a locally-bundled SQLite snapshot (§4 / coverage/
# sources.yaml), so Provenance carries corpus_synced_at + corpus_version
# in addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_EPC_BASE = "https://www.epo.org"
_EPC_NAME = "European Patent Convention"

# Bounded fan-out for list-accepting get_epc_section (§5.4). SQLite reads
# are fast so the concurrency budget is conservative — the cap exists so
# a 50-article portfolio doesn't open 50 connections at once.
_EPC_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5). FTS5 already returns short snippets, but the
# raw column can blow past this when the surrounding context is dense.
# Truncate so a 25-hit page fits comfortably under the §5.5 token budget.
_EPC_LEAN_SNIPPET_CHARS = 400


def _epc_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.epc.get_corpus_status` so the values
    track the bundled corpus without per-call hardcoding. Mirrors the
    MPEP template for substantive-law ``mcp_local`` corpora.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_EPC_BASE}{path}",
        source_name=_EPC_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _stub_hit(hit: dict) -> dict:
    """Lean projection of an EPC search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates the snippet to keep multi-hit pages cheap. Use
    ``get_epc_section`` for the full content of any hit.
    """
    # hit is an EpcSearchHit dump: title like "Article 54 - Article 54 – Novelty";
    # path looks like ["Article", "Article 54"]; the second element of path is
    # the section_number when present.
    title = hit.get("title") or ""
    path_parts = hit.get("path") or []
    section_number: str | None = None
    for part in path_parts:
        if isinstance(part, str) and not part.lower().startswith("chapter"):
            section_number = part
    return {
        "section_number": section_number,
        "title": title,
        "snippet": _truncate(hit.get("snippet") or "", _EPC_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single EPC section record.

    Leads with the corpus version so the agent can quote it directly
    when warning about staleness (§4 + §5.13).
    """
    href = record.get("href") or ""
    title = record.get("title") or "(no title)"
    head = f"**EPC {corpus_version} — {title}**"
    if href:
        return f"{head}\nSource: {_EPC_BASE}/en/legal/epc/{corpus_version}/{href}.html"
    return head


def _section_to_dict(section: Any) -> dict:
    """Dump an EpcSection model to a dict."""
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
# search_epc
# ---------------------------------------------------------------------------


@epc_mcp.tool(annotations=READ_ONLY)
async def search_epc(
    query: Annotated[
        str,
        "Search query. Examples: 'novelty', 'inventive step', "
        "'priority claim'. By default treated as an adjacent-word phrase; "
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
        "the upstream EpcSearchHit shape (title prefixed with section_number, "
        "the full result_url, and the path breadcrumb).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the European Patent Convention + Implementing Regulations.

    The EPC is the foundational substantive-law statute governing
    European patent practice — 180 Articles of the Convention plus 176
    Rules of the Implementing Regulations as published by the EPO.
    Returns relevance-ranked hits with truncated snippets by default;
    use ``get_epc_section`` for the full text of any Article or Rule.
    Pass ``full=True`` to get the upstream-shaped row.

    Examples:
      * Novelty (Art. 54): query='novelty', syntax='adj'
      * Inventive step (Art. 56): query='inventive step'
      * Examination procedure (R. 71): query='communication examining division'

    Related tools: get_epc_section.
    """
    if limit < 1 or limit > 100:
        raise ValidationError(f"limit must be between 1 and 100; got {limit}")

    # Translate the offset/limit pair into the underlying client's page/per_page.
    page = (offset // limit) + 1 if offset >= 0 else 1
    async with EpcClient() as client:
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
    summary = f"EPC ({corpus_label}) — `{query}`: {len(items)} hit{'s' if len(items) != 1 else ''}"
    if response.has_more:
        summary += " (more available)."
    else:
        summary += "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=_epc_provenance("/en/legal/epc"),
    )


# ---------------------------------------------------------------------------
# get_epc_section
# ---------------------------------------------------------------------------


@epc_mcp.tool(annotations=READ_ONLY)
async def get_epc_section(
    section: Annotated[
        str | list[str],
        "EPC section identifier or a list of identifiers. Accepts canonical "
        "citations like 'Article 54' / 'Art. 54' / 'Rule 71' / 'R. 71', "
        "URL slugs like 'a54' or 'r71', or full epo.org URLs. Examples: "
        "'Article 54', ['Article 54', 'Article 56', 'Rule 71'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more EPC Articles or Rules by citation.

    Returns each section's title, full HTML, plaintext, and the resolved
    href. Accepts either a single citation or a list (§5.4); the response
    is always a ListEnvelope so the shape is stable. Bounded concurrent
    fan-out internally; order matches the input.

    The EPC is the foundational substantive-law statute governing
    European patent practice — Articles of the Convention plus Rules of
    the Implementing Regulations. The bundled corpus version is surfaced
    in ``provenance.corpus_version`` so agents can quote freshness.

    Related tools: search_epc.
    """
    refs = [section] if isinstance(section, str) else list(section)
    if not refs:
        raise ValidationError("get_epc_section requires at least one section reference")

    semaphore = asyncio.Semaphore(_EPC_FANOUT_CONCURRENCY)

    async def _fetch_one(client: EpcClient, ref: str) -> dict:
        async with semaphore:
            record = await client.get_section(ref)
            return _section_to_dict(record)

    async with EpcClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        summary = _summarize_section(results[0], corpus_label)
        # If the single ref looks like a citation/slug, point provenance
        # at the specific section's URL; otherwise at the collection root.
        ref = refs[0]
        href = results[0].get("href")
        if href and _looks_like_section_ref(ref):
            path = f"/en/legal/epc/{corpus_label}/{href}.html"
        else:
            path = "/en/legal/epc"
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} EPC sections ({corpus_label}): {joined}"
        path = "/en/legal/epc"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_epc_provenance(path),
    )


__all__ = ["epc_mcp", "search_epc", "get_epc_section"]
