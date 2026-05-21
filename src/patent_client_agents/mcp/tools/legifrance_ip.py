"""Légifrance IP statutes MCP tools — French CPI + Code de commerce L.151.

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_local``, ``update_strategy=scheduled_recrawl``,
``update_cadence=annual`` (per ``coverage/sources.yaml`` row
``FR/Legifrance/IP``). The corpus is a SQLite/FTS5 snapshot materialized
by ``patent-client-agents-build-legifrance-ip-corpus`` from the bundled
JSONL seed — every response stamps ``Provenance.corpus_synced_at`` and
``corpus_version`` from
:func:`patent_client_agents.legifrance_ip.get_corpus_status` so agents
can warn when the bundle is stale (§4).

Two tools:

* ``search_legifrance_ip`` — full-text search across the corpus, with
  optional ``statute`` filter (``'CPI'`` or ``'Code de commerce'``).
* ``get_legifrance_section`` — resolve one or more practitioner-shaped
  citations (``L. 611-10 CPI``, ``Art. L. 151-1 Code de commerce``) to
  their canonical article text.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.legifrance_ip import (
    CitationParseError,
    LegifranceIpClient,
    get_corpus_status,
)
from patent_client_agents.legifrance_ip.resources import STATUTES

legifrance_ip_mcp = FastMCP("Légifrance IP")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). Légifrance IP is
# substantive law served from a locally-bundled SQLite snapshot (§4 /
# coverage/sources.yaml), so Provenance carries corpus_synced_at +
# corpus_version in addition to the standard fields. Both come from
# ``get_corpus_status()`` once per request — NEVER hardcoded — so a
# corpus refresh propagates without a code change here.
# ──────────────────────────────────────────────────────────────────────

_LEGIFRANCE_BASE = "https://www.legifrance.gouv.fr"
_LEGIFRANCE_NAME = "Légifrance — French IP statutes (CPI + Code de commerce L.151 trade secrets)"

# Bounded fan-out for list-accepting get_legifrance_section (§5.4).
# SQLite reads are fast; the budget is conservative so a 50-citation
# batch doesn't open 50 connections at once.
_LEGIFRANCE_FANOUT_CONCURRENCY = 5

# Lean snippet cap (§5.5). FTS5 returns short snippets already, but
# the raw column can sprawl when the article body is long. Truncate so
# a 25-hit page fits comfortably under the §5.5 token budget.
_LEGIFRANCE_LEAN_SNIPPET_CHARS = 400


def _legifrance_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` with corpus metadata.

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.legifrance_ip.get_corpus_status` so the
    values track the bundled corpus without per-call hardcoding.
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=f"{_LEGIFRANCE_BASE}{path}",
        source_name=_LEGIFRANCE_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _truncate(text: str, limit: int) -> str:
    """Cap a string at ``limit`` chars, appending an ellipsis on overflow."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _hit_to_dict(hit: Any) -> dict:
    """Lean projection of a LegifranceSearchHit (§5.5).

    Returns the four fields agents need to cite the article and decide
    whether to fetch the full body via ``get_legifrance_section``.
    """
    if hasattr(hit, "model_dump"):
        data = hit.model_dump()
    else:
        data = dict(hit)
    return {
        "statute": data.get("statute"),
        "section": data.get("section"),
        "title": data.get("title"),
        "snippet": _truncate(data.get("snippet") or "", _LEGIFRANCE_LEAN_SNIPPET_CHARS),
    }


def _section_to_dict(section: Any) -> dict:
    """Dump a LegifranceSection model to a plain dict."""
    if hasattr(section, "model_dump"):
        return section.model_dump()
    return dict(section)


def _validate_statute_filter(statute: str | None) -> str | None:
    """Reject unknown ``statute`` values early so the FTS query stays valid.

    Accepts ``None`` (no filter) and the closed vocabulary from
    :data:`patent_client_agents.legifrance_ip.resources.STATUTES`.
    """
    if statute is None:
        return None
    if statute not in STATUTES:
        raise ValidationError(f"statute must be one of {list(STATUTES)} or None; got {statute!r}")
    return statute


# ---------------------------------------------------------------------------
# search_legifrance_ip
# ---------------------------------------------------------------------------


@legifrance_ip_mcp.tool(annotations=READ_ONLY)
async def search_legifrance_ip(
    query: Annotated[
        str,
        "Search query in French (or English fallback). Examples: "
        "'brevetabilité', 'activité inventive', 'marque', 'secret des affaires'. "
        "Multi-token queries are AND-joined; diacritics fold "
        "(brevetabilite matches brevetabilité).",
    ],
    statute: Annotated[
        str | None,
        "Optional filter — 'CPI' (Code de la propriété intellectuelle: "
        "patents/trademarks/designs/copyright) or 'Code de commerce' "
        "(L.151 trade secrets). Omit to search both.",
    ] = None,
) -> ListEnvelope[dict]:
    """Search French intellectual-property statutes (CPI + Code de commerce L.151).

    Returns relevance-ranked hits with highlighted snippets. Use
    ``get_legifrance_section`` to fetch the full article body for any
    hit by its citation (``L. 611-10 CPI`` etc.).

    Examples:
      * Patentability: query='brevetabilité', statute='CPI'
      * Trade secrets: query='secret des affaires', statute='Code de commerce'
      * Trademark definition: query='marque', statute='CPI'

    Related tools: get_legifrance_section.
    """
    statute = _validate_statute_filter(statute)
    async with LegifranceIpClient() as client:
        response = await client.search(query, statute=statute, per_page=25, page=1)

    items = [_hit_to_dict(hit) for hit in response.hits]
    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    statute_label = f" [{statute}]" if statute else ""
    summary = (
        f"Légifrance IP ({corpus_label}){statute_label} — `{query}`: "
        f"{len(items)} hit{'s' if len(items) != 1 else ''}"
    )
    summary += " (more available)." if response.has_more else "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=response.has_more,
        next_cursor=None,
        provenance=_legifrance_provenance("/codes/section_lc/LEGITEXT000006069414"),
    )


# ---------------------------------------------------------------------------
# get_legifrance_section
# ---------------------------------------------------------------------------


@legifrance_ip_mcp.tool(annotations=READ_ONLY)
async def get_legifrance_section(
    citation: Annotated[
        str | list[str],
        "French statutory citation (or list for portfolio workflows). "
        "Accepted forms: 'L. 611-10 CPI', 'Art. L. 611-10 CPI', "
        "'L611-10 CPI', 'L. 151-1 Code de commerce'. Examples: "
        "'L. 611-10 CPI', ['L. 611-1 CPI', 'L. 151-1 Code de commerce'].",
    ],
) -> ListEnvelope[dict]:
    """Get one or more Légifrance IP articles by practitioner citation.

    Returns each article's statute, section, title, and full text.
    Accepts either a single citation string or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally; order matches the input.

    Related tools: search_legifrance_ip.
    """
    refs = [citation] if isinstance(citation, str) else list(citation)
    if not refs:
        raise ValidationError("get_legifrance_section requires at least one citation")

    semaphore = asyncio.Semaphore(_LEGIFRANCE_FANOUT_CONCURRENCY)

    async def _fetch_one(client: LegifranceIpClient, ref: str) -> dict:
        async with semaphore:
            try:
                section = await client.get_section(ref)
            except CitationParseError as exc:
                raise ValidationError(str(exc)) from exc
            return _section_to_dict(section)

    async with LegifranceIpClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, ref) for ref in refs])

    status = get_corpus_status()
    corpus_label = status["corpus_version"]
    if len(results) == 1:
        record = results[0]
        head = (
            f"**Légifrance IP {corpus_label} — {record.get('statute')} "
            f"art. {record.get('section')}: {record.get('title') or '(sans titre)'}**"
        )
        summary = head
    else:
        joined = ", ".join(refs)
        summary = f"Fetched {len(results)} Légifrance IP articles ({corpus_label}): {joined}"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_legifrance_provenance("/codes"),
    )


__all__ = ["legifrance_ip_mcp", "search_legifrance_ip", "get_legifrance_section"]
