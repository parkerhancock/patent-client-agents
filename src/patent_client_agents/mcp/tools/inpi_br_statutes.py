"""INPI Brazil — LPI (Lei 9.279/1996) statutes MCP tools.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl`` (per
``coverage/sources.yaml``). The LPI corpus is a SQLite/FTS5 snapshot
materialized by
``patent-client-agents-build-inpi-br-statutes-corpus`` covering the
Articles of Brazil's unified Industrial Property Law — patents (Title
I), designs (Title II), trade marks (Title III), GIs (Title IV), trade
secrets / unfair competition (Title V, Art. 195), and criminal
sanctions. Every response stamps ``Provenance.corpus_synced_at`` and
``corpus_version`` read from
:func:`patent_client_agents.inpi_br_statutes.get_corpus_status` so
agents can warn when the bundle is stale (§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.inpi_br_statutes import (
    InpiBrStatutesClient,
    get_corpus_status,
)
from patent_client_agents.inpi_br_statutes.client import (
    _CITATION_PATTERN,
    _SLUG_PATTERN,
)
from patent_client_agents.shared.corpus.tools import (
    corpus_get,
    corpus_search,
    hits_summary,
    truncate,
)
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, as_id_list
from patent_client_agents.shared.paging import Limit100, Offset

inpi_br_statutes_mcp = FastMCP("INPI Brazil — LPI")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). The LPI is substantive
# law served from a locally-bundled SQLite snapshot (§4 / coverage/
# sources.yaml), so Provenance carries corpus_synced_at + corpus_version
# in addition to the standard fields. Both are read from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_INPI_BR_BASE = "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm"
_INPI_BR_NAME = "INPI Brazil — LPI (Lei 9.279/1996)"

# Lean snippet cap (§5.5). FTS5 already returns short snippets, but the
# raw column can blow past this when the surrounding context is dense.
# Truncate so a 25-hit page fits comfortably under the §5.5 token budget.
_INPI_BR_LEAN_SNIPPET_CHARS = 400


def _stub_hit(hit: dict) -> dict:
    """Lean projection of an LPI search hit (§5.5).

    Drops the per-row ``result_url`` (reconstructable from ``href``) and
    truncates the snippet to keep multi-hit pages cheap. Use
    ``get_inpi_br_section`` for the full PT + EN content of any hit.
    """
    return {
        "article_number": hit.get("article_number"),
        "title": hit.get("title"),
        "snippet": truncate(hit.get("snippet") or "", _INPI_BR_LEAN_SNIPPET_CHARS),
        "href": hit.get("href"),
    }


def _summarize_section(record: dict, corpus_version: str) -> str:
    """One-line Markdown summary of a single LPI section record."""
    article = record.get("article_number") or ""
    title = record.get("title_pt") or "(no title)"
    head = f"**LPI ({corpus_version}) — {article}: {title}**"
    href = record.get("href") or ""
    if href and href.startswith("art"):
        return f"{head}\nSource: {_INPI_BR_BASE}#Art{href[3:]}"
    return head


def _looks_like_section_ref(ref: str) -> bool:
    """True if ``ref`` is a citation form or bare slug (not a URL)."""
    cleaned = ref.strip()
    if _CITATION_PATTERN.match(cleaned):
        return True
    if _SLUG_PATTERN.match(cleaned):
        return True
    return False


# ---------------------------------------------------------------------------
# search_inpi_br_statutes
# ---------------------------------------------------------------------------


@inpi_br_statutes_mcp.tool(annotations=READ_ONLY)
async def search_inpi_br_statutes(
    query: Annotated[
        str,
        "Search query. Examples: 'segredo industrial' (trade secret), "
        "'patentes de invenção' (patents of invention), 'marca de "
        "alto renome' (well-known trade mark). The corpus indexes both "
        "Portuguese (authoritative) and English text — query in either "
        "language. By default treated as an adjacent-word phrase; set "
        "``syntax='or'`` to widen.",
    ],
    limit: Limit100 = 25,
    offset: Offset = 0,
    syntax: Annotated[
        str,
        "Query syntax. 'adj' (default) — adjacent-word phrase match. "
        "'and' — all terms must match. 'or' — any term matches. 'exact' "
        "— same as 'adj'.",
    ] = "adj",
    sort: Annotated[
        str,
        "'relevance' (BM25, default) or 'outline' (article_number ascending).",
    ] = "relevance",
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: "
        "article_number, title, snippet (truncated to ~400 chars), href. "
        "When True, returns the upstream InpiBrSearchHit shape with the "
        "full result_url and path breadcrumb.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the Brazilian Industrial Property Law (LPI / Lei 9.279/1996).

    The LPI is Brazil's unified Industrial Property statute — patents
    and utility models (Title I), industrial designs (Title II), trade
    marks (Title III), geographical indications (Title IV), trade
    secrets and unfair competition (Title V, Art. 195), and criminal
    sanctions. Returns relevance-ranked hits with truncated PT snippets
    by default; use ``get_inpi_br_section`` for the full PT + EN text
    of any Article. Pass ``full=True`` to get the upstream-shaped row.

    Examples:
      * Trade secrets (Art. 195): query='segredo industrial'
      * Patent eligibility (Art. 10): query='não se considera invenção'
      * Well-known marks (Art. 125): query='marca de alto renome'

    Related tools: get_inpi_br_section, list_inpi_br_bulk_releases.
    """
    return await corpus_search(
        InpiBrStatutesClient,
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
            f"LPI ({corpus_label}) — `{query}`", len(items), response.has_more
        ),
        source_url=_INPI_BR_BASE,
        source_name=_INPI_BR_NAME,
    )


# ---------------------------------------------------------------------------
# get_inpi_br_section
# ---------------------------------------------------------------------------


@inpi_br_statutes_mcp.tool(annotations=READ_ONLY)
async def get_inpi_br_section(
    citation: Annotated[
        str | list[str],
        "LPI Article citation or a list of citations. Accepts canonical "
        "forms like 'Art. 6', 'Article 6', 'Artigo 6', 'Art. 195 LPI', "
        "'Art. 195(XI) LPI' (sub-paragraphs roll up to the parent "
        "Article in v1), URL slugs like 'art6'/'art195', or full "
        "Planalto URLs with anchors. Examples: 'Art. 195', "
        "['Art. 6', 'Art. 122', 'Art. 195'].",
    ],
) -> FetchedList[dict]:
    """Get one or more LPI (Lei 9.279/1996) Articles by citation.

    Returns each Article's PT (authoritative — Planalto) and EN (WIPO
    Lex translation) text and HTML, plus the resolved slug. Accepts
    either a single citation or a list (§5.4); the response is always a
    ListEnvelope so the shape is stable. Bounded concurrent fan-out
    internally; order matches the input.

    The LPI is Brazil's unified Industrial Property Law — patents,
    designs, trade marks, GIs, trade secrets / unfair competition, and
    criminal sanctions in one statute. The bundled corpus version is
    surfaced in ``provenance.corpus_version`` so agents can quote
    freshness.

    Related tools: search_inpi_br_statutes, list_inpi_br_bulk_releases.
    """
    refs = as_id_list(citation, noun="LPI citation")

    async def _fetch_one(client: Any, ref: str) -> dict:
        record = await client.get_section(ref)
        return dump(record)

    def _source_url(items: list[dict], corpus_label: str) -> str:
        if len(refs) == 1 and items:
            href = items[0].get("href")
            if href and _looks_like_section_ref(refs[0]) and href.startswith("art"):
                return f"{_INPI_BR_BASE}#Art{href[3:]}"
        return _INPI_BR_BASE

    return await corpus_get(
        InpiBrStatutesClient,
        refs,
        _fetch_one,
        single=isinstance(citation, str),
        corpus_status=get_corpus_status,
        summarize_one=_summarize_section,
        missing=lambda ref: f"LPI Article {ref} — not found.",
        noun_plural="LPI Articles",
        source_url=_source_url,
        source_name=_INPI_BR_NAME,
    )


__all__ = ["inpi_br_statutes_mcp", "search_inpi_br_statutes", "get_inpi_br_section"]
