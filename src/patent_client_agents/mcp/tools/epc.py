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

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.epc import EpcClient, get_corpus_status
from patent_client_agents.epc.client import _CITATION_PATTERN, _SLUG_PATTERN
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

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

# Lean snippet cap (§5.5). FTS5 already returns short snippets, but the
# raw column can blow past this when the surrounding context is dense.
# Truncate so a 25-hit page fits comfortably under the §5.5 token budget.
_EPC_LEAN_SNIPPET_CHARS = 400


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
        "snippet": truncate(hit.get("snippet") or "", _EPC_LEAN_SNIPPET_CHARS),
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
    return await corpus_search(
        EpcClient,
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
            f"EPC ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=f"{_EPC_BASE}/en/legal/epc",
        source_name=_EPC_NAME,
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
) -> FetchedList[dict]:
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
    refs = as_id_list(section, noun="EPC section reference")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return dump(record)

    def _source_url(items: list[dict], corpus_label: str) -> str:
        # If the single ref looks like a citation/slug, point provenance
        # at the specific section's URL; otherwise at the collection root.
        if len(refs) == 1 and items:
            href = items[0].get("href")
            if href and _looks_like_section_ref(refs[0]):
                return f"{_EPC_BASE}/en/legal/epc/{corpus_label}/{href}.html"
        return f"{_EPC_BASE}/en/legal/epc"

    return await corpus_get(
        EpcClient,
        refs,
        _fetch_one,
        single=isinstance(section, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"EPC section {ref} — not found.",
        noun_plural="EPC sections",
        source_url=_source_url,
        source_name=_EPC_NAME,
    )


__all__ = ["epc_mcp", "search_epc", "get_epc_section"]
