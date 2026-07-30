"""IPOS Singapore MCP tools — statutes corpus + manuals corpus.

Two corpus surfaces, both ``mcp_local`` / ``substantive_law``:

* **Statutes** read from a pre-built SQLite/FTS5 corpus produced by
  ``patent-client-agents-build-ipos-statutes-corpus``. Covers the four
  Singapore IP Acts (Patents / Trade Marks / Registered Designs /
  Copyright). Provenance carries ``corpus_synced_at`` /
  ``corpus_version`` per §4, sourced from
  :func:`patent_client_agents.ipos_statutes.get_corpus_status`.
* **Manuals** read from a pre-built corpus produced by
  ``patent-client-agents-build-ipos-manuals-corpus``. Covers the three
  IPOS examination / work manuals (PEG / TM / Designs). Same
  provenance shape, sourced from
  :func:`patent_client_agents.ipos_manuals.get_corpus_status`.

Neither surface requires credentials, so the tools are unconditionally
registered.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.ipos_manuals import (
    IposManualsClient,
    ManualSearchInput,
    ManualSectionInput,
)
from patent_client_agents.ipos_manuals import get_corpus_status as _manuals_status
from patent_client_agents.ipos_manuals import list_manuals as _list_manuals
from patent_client_agents.ipos_manuals import search as _search_manuals
from patent_client_agents.ipos_manuals.client import parse_citation as _parse_manual_citation
from patent_client_agents.ipos_statutes import (
    IposStatutesClient,
    SectionInput,
    StatuteSearchInput,
)
from patent_client_agents.ipos_statutes import get_corpus_status as _statutes_status
from patent_client_agents.ipos_statutes import list_statutes as _list_statutes
from patent_client_agents.ipos_statutes import search as _search_statutes
from patent_client_agents.ipos_statutes.client import parse_citation as _parse_statute_citation

ipos_mcp = FastMCP("IPOS Singapore")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). Both surfaces carry
# corpus_synced_at + corpus_version per §4 (mcp_local substantive law).
# ──────────────────────────────────────────────────────────────────────

_IPOS_NAME = "IPOS Singapore"
_SSO_BASE = "https://sso.agc.gov.sg"
_IPOS_BASE = "https://www.ipos.gov.sg"


def _statutes_provenance(source_url: str) -> Any:
    """Build a Provenance for an IPOS statutes corpus response."""
    status = _statutes_status()
    return make_provenance(
        source_url=source_url,
        source_name=_IPOS_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _manuals_provenance(source_url: str) -> Any:
    """Build a Provenance for an IPOS manuals corpus response."""
    status = _manuals_status()
    return make_provenance(
        source_url=source_url,
        source_name=_IPOS_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _dump(obj: object) -> Any:
    """Serialize a Pydantic model or list of models; pass through dicts/None."""
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, list):
        return [_dump(item) for item in obj]
    return obj


def _summarize_statute_section(record: dict) -> str:
    """One-line Markdown summary for a single statute section."""
    short = record.get("short_name") or "(no statute)"
    label = record.get("section_label") or "(no section)"
    title = record.get("title") or ""
    head = f"**{short} § {label}**"
    if title:
        head += f" — {title}"
    return head


def _summarize_manual_section(record: dict) -> str:
    """One-line Markdown summary for a single manual section."""
    short = record.get("short_name") or "(no manual)"
    label = record.get("section_label") or "(no section)"
    title = record.get("title") or ""
    head = f"**IPOS {short} {label}**"
    if title:
        head += f" — {title}"
    return head


_IPOS_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------------------
# Statutes
# ---------------------------------------------------------------------------


@ipos_mcp.tool(annotations=READ_ONLY)
async def search_ipos_statutes(
    query: Annotated[str, "Search query against the IPOS Singapore statutes corpus."],
    statute: Annotated[
        str | None,
        (
            "Optional statute key — 'patents', 'tm', 'designs', or "
            "'copyright'. Aliases ('Patents Act', 'TMA1998', 'RDA2000', "
            "'CA2021') are accepted. Omit to search across all four Acts."
        ),
    ] = None,
    per_page: Annotated[int, "Hits per page, 1..100."] = 10,
    page: Annotated[int, "1-indexed page number."] = 1,
) -> ListEnvelope[dict]:
    """Search the Singapore IP statutes (Patents Act, Trade Marks Act, Registered Designs Act, Copyright Act).

    Returns ranked snippets with ``<mark>...</mark>`` highlights around
    matched terms. Use this for citation lookups like ``"Section 13"``
    or topical searches like ``"inventive step"``. Once a provision is
    located, call ``get_ipos_section`` for the full section text.

    Related tools: get_ipos_section, search_ipos_manuals.
    """
    params = StatuteSearchInput(
        query=query,
        statute=statute,
        per_page=per_page,
        page=page,
    )
    response = await _search_statutes(params)
    dumped = cast("dict[str, Any]", _dump(response) or {})
    items = list(dumped.get("hits") or [])
    has_more = bool(dumped.get("has_more"))
    statute_label = statute or "all"
    return ListEnvelope[dict](
        summary=(
            f"IPOS Singapore statutes — `{query}` (statute={statute_label}): "
            f"{len(items)} hits (page {page})."
        ),
        items=items,
        more_available=has_more,
        next_cursor=None,
        provenance=_statutes_provenance(f"{_SSO_BASE}/Browse/Act-Rev"),
    )


@ipos_mcp.tool(annotations=READ_ONLY)
async def get_ipos_section(
    citation: Annotated[
        str | list[str],
        (
            "Free-form citation to one Singapore IP statute section, or "
            "a list for portfolio reads. Accepted forms include "
            "'Section 13 Patents Act', 'Patents Act s. 13', "
            "'s 27(1) Trade Marks Act', '13 Patents Act'. Sub-section "
            "suffixes (13A, 27(1)) are preserved verbatim."
        ),
    ],
) -> ListEnvelope[dict]:
    """Fetch the full text of one or more Singapore IP statute sections by citation.

    Accepts either a single citation string or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally; order matches the input. Unrecognized
    citations and missing sections appear as ``not_found`` in the
    summary but do not raise.

    Related tools: search_ipos_statutes, get_ipos_manual_section.
    """
    citations = [citation] if isinstance(citation, str) else list(citation)
    if not citations:
        raise ValidationError("get_ipos_section requires at least one citation")

    semaphore = asyncio.Semaphore(_IPOS_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IposStatutesClient, cite: str) -> dict | None:
        async with semaphore:
            record = await client.get_by_citation(cite)
        return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with IposStatutesClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, c) for c in citations])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [c for c, r in zip(citations, fetched, strict=True) if r is None]

    if len(citations) == 1 and items:
        summary = _summarize_statute_section(items[0])
        # Try to point provenance at the specific section URL we resolved.
        parsed = _parse_statute_citation(citations[0])
        path = f"/Act/{parsed[0].upper()}#pr{parsed[1]}-" if parsed else "/Browse/Act-Rev"
    elif len(citations) == 1:
        summary = f"IPOS section `{citations[0]}` — not found."
        path = "/Browse/Act-Rev"
    else:
        head = f"Fetched {len(items)} of {len(citations)} IPOS statute sections."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")
        path = "/Browse/Act-Rev"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_statutes_provenance(f"{_SSO_BASE}{path}"),
    )


@ipos_mcp.tool(annotations=READ_ONLY)
async def list_ipos_statutes() -> ListEnvelope[dict]:
    """List the Singapore IP statutes bundled in the IPOS statutes corpus.

    Each entry carries the canonical statute key (``patents``, ``tm``,
    ``designs``, ``copyright``), the citation-ready short name, the full
    Act title, and the canonical Singapore Statutes Online URL. Per
    CONNECTOR_STANDARDS.md §5.8, ``list_*`` is a soft fit for vocabulary
    enumerators — kept intentionally so the name signals "scoped
    enumeration" to agents.

    Related tools: search_ipos_statutes, get_ipos_section.
    """
    statutes = await _list_statutes()
    items: list[dict] = [_dump(s) for s in statutes]  # type: ignore[misc]
    return ListEnvelope[dict](
        summary=f"IPOS Singapore statutes — {len(items)} Acts.",
        items=items,
        provenance=_statutes_provenance(f"{_SSO_BASE}/Browse/Act-Rev"),
    )


# ---------------------------------------------------------------------------
# Manuals
# ---------------------------------------------------------------------------


@ipos_mcp.tool(annotations=READ_ONLY)
async def search_ipos_manuals(
    query: Annotated[str, "Search query against the IPOS Singapore manuals corpus."],
    manual: Annotated[
        str | None,
        (
            "Optional manual key — 'peg' (Patent Examination Guidelines), "
            "'tm' (TM Work Manual), or 'designs' (Designs Work Manual). "
            "Aliases like 'Patent Examination Guidelines' or 'TM Work "
            "Manual' are accepted. Omit to search across all three."
        ),
    ] = None,
    per_page: Annotated[int, "Hits per page, 1..100."] = 10,
    page: Annotated[int, "1-indexed page number."] = 1,
) -> ListEnvelope[dict]:
    """Search the IPOS examination and work manuals (PEG, Trade Marks, Industrial Designs).

    Returns ranked snippets with ``<mark>...</mark>`` highlights around
    matched terms. Use for prosecution-argument lookups like
    ``"inventive step"`` or ``"distinctiveness"``. Once a section is
    located, call ``get_ipos_manual_section`` for the full text.

    Related tools: get_ipos_manual_section, search_ipos_statutes.
    """
    params = ManualSearchInput(
        query=query,
        manual=manual,
        per_page=per_page,
        page=page,
    )
    response = await _search_manuals(params)
    dumped = cast("dict[str, Any]", _dump(response) or {})
    items = list(dumped.get("hits") or [])
    has_more = bool(dumped.get("has_more"))
    manual_label = manual or "all"
    return ListEnvelope[dict](
        summary=(
            f"IPOS manuals — `{query}` (manual={manual_label}): {len(items)} hits (page {page})."
        ),
        items=items,
        more_available=has_more,
        next_cursor=None,
        provenance=_manuals_provenance(f"{_IPOS_BASE}/about-ip/patents/guides"),
    )


@ipos_mcp.tool(annotations=READ_ONLY)
async def get_ipos_manual_section(
    citation: Annotated[
        str | list[str],
        (
            "Free-form citation to one IPOS manual section, or a list "
            "for portfolio reads. Accepted forms include 'IPOS PEG "
            "1.5.3', 'PEG 1.5.3', 'IPOS TM Work Manual 3.4', "
            "'Designs Work Manual 2.1'. The 'IPOS ' prefix is optional."
        ),
    ],
) -> ListEnvelope[dict]:
    """Fetch the full text of one or more IPOS manual sections by citation.

    Accepts either a single citation string or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally; order matches the input.
    Unrecognized citations and missing sections appear as ``not_found``
    in the summary but do not raise.

    Related tools: search_ipos_manuals, get_ipos_section.
    """
    citations = [citation] if isinstance(citation, str) else list(citation)
    if not citations:
        raise ValidationError("get_ipos_manual_section requires at least one citation")

    semaphore = asyncio.Semaphore(_IPOS_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IposManualsClient, cite: str) -> dict | None:
        async with semaphore:
            record = await client.get_by_citation(cite)
        return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with IposManualsClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, c) for c in citations])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [c for c, r in zip(citations, fetched, strict=True) if r is None]

    if len(citations) == 1 and items:
        summary = _summarize_manual_section(items[0])
        parsed = _parse_manual_citation(citations[0])
        path = f"/about-ip/patents/guides#{parsed[0]}-{parsed[1]}" if parsed else "/about-ip"
    elif len(citations) == 1:
        summary = f"IPOS manual section `{citations[0]}` — not found."
        path = "/about-ip"
    else:
        head = f"Fetched {len(items)} of {len(citations)} IPOS manual sections."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")
        path = "/about-ip"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_manuals_provenance(f"{_IPOS_BASE}{path}"),
    )


@ipos_mcp.tool(annotations=READ_ONLY)
async def list_ipos_manuals() -> ListEnvelope[dict]:
    """List the IPOS examination / work manuals bundled in the IPOS manuals corpus.

    Each entry carries the canonical manual key (``peg``, ``tm``,
    ``designs``), the citation-ready short name, the full manual title,
    and the canonical IPOS URL. Per CONNECTOR_STANDARDS.md §5.8,
    ``list_*`` is a soft fit for vocabulary enumerators — kept
    intentionally.

    Related tools: search_ipos_manuals, get_ipos_manual_section.
    """
    manuals = await _list_manuals()
    items: list[dict] = [_dump(m) for m in manuals]  # type: ignore[misc]
    return ListEnvelope[dict](
        summary=f"IPOS Singapore manuals — {len(items)} manuals.",
        items=items,
        provenance=_manuals_provenance(f"{_IPOS_BASE}/about-ip"),
    )


# Avoid Pydantic deprecation warning by referencing imported but unused names
# (used as re-exports for downstream tests that patch the SectionInput /
# ManualSectionInput symbols at this module's path).
_ = SectionInput, ManualSectionInput


__all__ = ["ipos_mcp"]
