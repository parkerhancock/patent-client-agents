"""UPC MCP tools — decisions/orders feed + statutes corpus.

Two surfaces:

* **Decisions** scrape the public listing at
  ``unifiedpatentcourt.org/.../decisions-and-orders``. The listing
  itself isn't auth-gated, but per-decision detail pages are Cloudflare-
  challenged — these tools deliberately stay on the listing and the
  direct PDF URLs. CONNECTOR_STANDARDS.md classification:
  ``category=substantive_law``, ``transport=mcp_proxy``,
  ``update_strategy=live_proxy``. Live-proxy substantive-law connectors
  carry the standard provenance fields only — no ``corpus_*``.
* **Statutes** read from a pre-built SQLite/FTS5 corpus produced by
  ``patent-client-agents-build-upc-statutes-corpus``. Classification:
  ``category=substantive_law``, ``transport=mcp_local``. Provenance
  additionally carries ``corpus_synced_at`` / ``corpus_version`` per §4,
  sourced from
  :func:`patent_client_agents.upc_statutes.get_corpus_status` so the
  values track the bundled corpus without per-call hardcoding.

Neither surface requires credentials, so the tools are unconditionally
registered.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.upc_decisions import (
    DecisionSearchInput,
    UpcDecisionsClient,
    list_divisions,
    list_languages,
    search_decisions,
)
from patent_client_agents.upc_statutes import (
    StatuteSearchInput,
    UpcStatutesClient,
    get_corpus_status,
    list_instruments,
    search,
)

upc_mcp = FastMCP("UPC")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9).
#
# Two source-specific provenance helpers — decisions are live-proxy
# (standard fields only), statutes are mcp_local (carry corpus_* fields).
# The statutes corpus_synced_at / corpus_version values flow from
# :func:`patent_client_agents.upc_statutes.get_corpus_status` so the
# bundled corpus drives the freshness stamp without a code change here
# (CONNECTOR_STANDARDS.md §4).
# ──────────────────────────────────────────────────────────────────────

_UPC_DECISIONS_BASE = "https://www.unifiedpatentcourt.org"
_UPC_DECISIONS_NAME = "Unified Patent Court"
_UPC_STATUTES_NAME = "Unified Patent Court"


def _upc_provenance(path: str) -> Any:
    """Build a Provenance for a UPC decisions URL (live proxy, no corpus_*)."""
    return make_provenance(
        source_url=f"{_UPC_DECISIONS_BASE}{path}",
        source_name=_UPC_DECISIONS_NAME,
    )


def _upc_statutes_provenance(source_url: str) -> Any:
    """Build a Provenance for the UPC statutes corpus (carries corpus_*).

    Reads ``corpus_synced_at`` / ``corpus_version`` from
    :func:`patent_client_agents.upc_statutes.get_corpus_status` so the
    values track the bundled corpus without per-call hardcoding
    (CONNECTOR_STANDARDS.md §4).
    """
    status = get_corpus_status()
    return make_provenance(
        source_url=source_url,
        source_name=_UPC_STATUTES_NAME,
        corpus_synced_at=status["corpus_synced_at"],
        corpus_version=status["corpus_version"],
    )


def _dump(obj: object) -> Any:
    """Serialize a Pydantic model or pass through.

    Recursive — handles ``None``, lists (recursing per-element), and dicts.
    Return type is ``Any`` because the helper genuinely produces multiple
    shapes (dict for models, list for sequences, None for empties); call
    sites narrow at use.
    """
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, list):
        return [_dump(item) for item in obj]
    return obj


def _stub_decision(record: dict) -> dict:
    """Lean projection of a UPC decision listing row (§5.5).

    Keeps the scalar fields an agent needs to triage hits without
    pulling all PDF attachment URLs into context. Use ``full=True`` to
    get the upstream-shaped row (with ``pdf_urls`` and ``raw_references``).
    """
    parties = record.get("parties") or []
    return {
        "case_id": record.get("case_id"),
        "court": record.get("court"),
        "type_of_action": record.get("type_of_action"),
        "parties": parties,
        "detail_url": record.get("detail_url"),
        # First PDF URL (most rows carry exactly one; lean stub keeps it
        # so an agent can quote the canonical document without paging
        # to the full record).
        "primary_pdf_url": (record.get("pdf_urls") or [None])[0],
    }


def _summarize_decision(record: dict) -> str:
    """One-line Markdown summary of a single UPC decision row."""
    case_id = record.get("case_id") or "(no case id)"
    court = record.get("court") or "(unknown court)"
    type_of_action = record.get("type_of_action") or "(unknown action)"
    parties = record.get("parties") or []
    head = f"**UPC {case_id}** — {court}"
    line = f"Type: {type_of_action}."
    if parties:
        line += f" Parties: {' v. '.join(parties)}."
    return f"{head}\n{line}"


def _summarize_instrument(record: dict) -> str:
    """One-line Markdown summary of a single UPC statutes instrument."""
    short = record.get("short_name") or "(no short name)"
    title = record.get("title") or "(no title)"
    lang = record.get("language") or "?"
    pages = record.get("pdf_pages")
    head = f"**UPC {short}** ({lang}) — {title}"
    line = f"{pages} page(s)." if pages else "Full text included."
    return f"{head}\n{line}"


_UPC_DECISIONS_FANOUT_CONCURRENCY = 5
_UPC_STATUTES_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------------------
# Decisions and Orders
# ---------------------------------------------------------------------------


@upc_mcp.tool(annotations=READ_ONLY)
async def search_upc_decisions(
    page: Annotated[int, "0-indexed page number, default 0 (most recent)"] = 0,
    judgement_type: Annotated[
        str | None,
        "Filter to 'order' or 'decision'; omit for both",
    ] = None,
    court_type: Annotated[
        str | None,
        (
            "Court-type ID: '1' = Court of Appeal, '2' = Central CFI, "
            "'3' = Local CFI, '4' = Regional CFI. Omit for all."
        ),
    ] = None,
    division: Annotated[
        str | None,
        "Specific division ID — use list_upc_divisions to discover.",
    ] = None,
    proceedings_lang: Annotated[
        str | None,
        "Procedural-language ID — use list_upc_languages to discover.",
    ] = None,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: case_id, court, "
        "type_of_action, parties, detail_url, primary_pdf_url. When True, "
        "every hit carries the upstream row (with full pdf_urls list and "
        "raw_references) — prefer ``get_upc_decision`` for one record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Unified Patent Court (UPC) decisions and orders by court, division, or language.

    Returns a page of decisions with canonical case IDs (``UPC_CFI_<n>/<yyyy>``,
    ``UPC_CoA_<n>/<yyyy>``, or ``ACT_<n>/<yyyy>``), court, type of action,
    parties, and direct URLs to the PDF/A document(s). Lean stubs by default;
    pass ``full=True`` for the upstream-shaped row. Pagination via the
    ``page`` arg; ``more_available`` reflects ``total_pages`` from the pager.

    Related tools: get_upc_decision, list_upc_divisions, list_upc_languages,
    search_upc_statutes.
    """
    params = DecisionSearchInput(
        page=page,
        judgement_type=judgement_type,
        court_type=court_type,
        division=division,
        proceedings_lang=proceedings_lang,
    )
    response = await search_decisions(params)
    dumped = _dump(response) or {}
    hits = list(dumped.get("hits") or [])  # type: ignore[union-attr]
    items = hits if full else [_stub_decision(h) for h in hits]
    total_pages = dumped.get("total_pages")  # type: ignore[union-attr]
    current_page = dumped.get("page", page)  # type: ignore[union-attr]
    more = bool(total_pages and current_page + 1 < int(total_pages))

    filter_bits: list[str] = []
    if judgement_type:
        filter_bits.append(f"type={judgement_type}")
    if court_type:
        filter_bits.append(f"court_type={court_type}")
    if division:
        filter_bits.append(f"division={division}")
    if proceedings_lang:
        filter_bits.append(f"lang={proceedings_lang}")
    label = " ".join(filter_bits) or "(no filters)"
    page_info = f"page {current_page}"
    if total_pages:
        page_info += f"/{total_pages}"

    return ListEnvelope[dict](
        summary=f"UPC decisions — {label}: {len(items)} hits ({page_info}).",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_upc_provenance("/en/decisions-and-orders"),
    )


@upc_mcp.tool(annotations=READ_ONLY)
async def get_upc_decision(
    case_id: Annotated[
        str | list[str],
        (
            "Canonical UPC case identifier, or a list for portfolio workflows. "
            "Examples: 'UPC_CFI_1747/2025', 'UPC_CoA_335/2023', "
            "'ACT_551054/2023', ['UPC_CFI_1747/2025', 'UPC_CoA_335/2023']. "
            "Hyphenated variants like 'UPC-CFI-478/2025' are accepted and "
            "normalized."
        ),
    ],
) -> ListEnvelope[dict]:
    """Fetch one or more Unified Patent Court (UPC) decisions by case identifier.

    Walks the decisions listing until each requested case is found.
    Accepts either a single case identifier or a list (§5.4); the response
    is always a ListEnvelope so the shape is stable. Bounded concurrent
    fan-out internally; order matches the input.

    Related tools: search_upc_decisions, list_upc_divisions, list_upc_languages.
    """
    case_ids = [case_id] if isinstance(case_id, str) else list(case_id)
    if not case_ids:
        raise ValidationError("get_upc_decision requires at least one case_id")

    semaphore = asyncio.Semaphore(_UPC_DECISIONS_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UpcDecisionsClient, cid: str) -> dict | None:
        async with semaphore:
            record = await client.get_decision(cid)
        return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with UpcDecisionsClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, cid) for cid in case_ids])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [cid for cid, r in zip(case_ids, fetched, strict=True) if r is None]

    if len(case_ids) == 1 and items:
        summary = _summarize_decision(items[0])
    elif len(case_ids) == 1:
        summary = f"UPC decision {case_ids[0]} — not found."
    else:
        head = f"Fetched {len(items)} of {len(case_ids)} UPC decisions."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    path = "/en/decisions-and-orders" + (f"?case_id={case_ids[0]}" if len(case_ids) == 1 else "")
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_upc_provenance(path),
    )


@upc_mcp.tool(annotations=READ_ONLY)
async def list_upc_divisions() -> ListEnvelope[dict]:
    """List the Unified Patent Court (UPC) division filter options.

    Returns the dropdown values used by the ``division`` argument on
    ``search_upc_decisions``. Includes Central / Local / Regional
    Divisions and the Court of Appeal seat. Per CONNECTOR_STANDARDS.md
    §5.8, ``list_*`` is a soft fit for vocabulary enumerators — kept
    intentionally so the name signals "scoped enumeration" to agents.

    Related tools: search_upc_decisions, list_upc_languages.
    """
    divisions = await list_divisions()
    items: list[dict] = [_dump(d) for d in divisions]  # type: ignore[misc]
    return ListEnvelope[dict](
        summary=f"UPC divisions — {len(items)} options.",
        items=items,
        provenance=_upc_provenance("/en/decisions-and-orders"),
    )


@upc_mcp.tool(annotations=READ_ONLY)
async def list_upc_languages() -> ListEnvelope[dict]:
    """List the Unified Patent Court (UPC) procedural-language filter options.

    Returns the dropdown values used by the ``proceedings_lang`` argument
    on ``search_upc_decisions`` (English, French, German, plus minority
    procedural languages used by specific Local Divisions). Per
    CONNECTOR_STANDARDS.md §5.8, ``list_*`` is a soft fit for vocabulary
    enumerators — kept intentionally.

    Related tools: search_upc_decisions, list_upc_divisions.
    """
    langs = await list_languages()
    items: list[dict] = [_dump(lang) for lang in langs]  # type: ignore[misc]
    return ListEnvelope[dict](
        summary=f"UPC procedural languages — {len(items)} options.",
        items=items,
        provenance=_upc_provenance("/en/decisions-and-orders"),
    )


# ---------------------------------------------------------------------------
# Statutes
# ---------------------------------------------------------------------------


@upc_mcp.tool(annotations=READ_ONLY)
async def search_upc_statutes(
    query: Annotated[str, "Search query against the UPC statutes corpus."],
    instrument: Annotated[
        str | None,
        (
            "Optional instrument key — 'upca', 'rop', 'fees', or 'coc'. "
            "Use 'statute' as an alias for the UPCA Annex I portion. "
            "Omit to search across all instruments."
        ),
    ] = None,
    language: Annotated[
        str,
        "ISO 639-1: 'en' (default), 'fr', or 'de'.",
    ] = "en",
    per_page: Annotated[int, "Hits per page, 1..100."] = 10,
    page: Annotated[int, "1-indexed page number."] = 1,
) -> ListEnvelope[dict]:
    """Search the Unified Patent Court (UPC) statutes corpus (UPCA, RoP, Fees, CoC).

    Returns ranked snippets with ``<mark>...</mark>`` highlights around
    matched terms. Use this for citation lookups like ``"Article 33"``
    or topical searches like ``"opt-out withdrawal"``. Once you've
    located a provision, call ``get_upc_section`` to fetch the full
    instrument text.

    Related tools: get_upc_section, list_upc_instruments.
    """
    params = StatuteSearchInput(
        query=query,
        instrument=instrument,
        language=language,
        per_page=per_page,
        page=page,
    )
    response = await search(params)
    dumped = _dump(response) or {}
    # Upstream ``UpcStatuteSearchHit`` is already lean (5 fields:
    # instrument, short_name, language, snippet, rank) so no
    # ``full=True`` toggle is needed per §5.5.
    items = list(dumped.get("hits") or [])  # type: ignore[union-attr]
    has_more = bool(dumped.get("has_more"))  # type: ignore[union-attr]

    instr_label = instrument or "all"
    return ListEnvelope[dict](
        summary=(
            f"UPC statutes — `{query}` (instrument={instr_label}, lang={language}): "
            f"{len(items)} hits (page {page})."
        ),
        items=items,
        more_available=has_more,
        next_cursor=None,
        provenance=_upc_statutes_provenance(
            "https://www.unifiedpatentcourt.org/en/court/legal-documents"
        ),
    )


@upc_mcp.tool(annotations=READ_ONLY)
async def get_upc_section(
    instrument: Annotated[
        str | list[str],
        (
            "Instrument key, or a list for portfolio reads. "
            "One of 'upca', 'rop', 'fees', 'coc' (or 'statute' as an alias "
            "for the UPCA Annex I portion). Examples: 'upca', "
            "['upca', 'rop']."
        ),
    ],
    language: Annotated[str, "ISO 639-1: 'en' (default), 'fr', or 'de'."] = "en",
) -> ListEnvelope[dict]:
    """Fetch the full plain text of one or more Unified Patent Court (UPC) legal instruments.

    Note: section-level (per-Article, per-Rule) retrieval is not yet
    available — this returns the entire instrument text. Pair with
    ``search_upc_statutes`` to locate a specific provision and quote the
    snippet. Accepts either a single instrument key or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable. Bounded
    concurrent fan-out internally; order matches the input.

    Related tools: search_upc_statutes, list_upc_instruments.
    """
    keys = [instrument] if isinstance(instrument, str) else list(instrument)
    if not keys:
        raise ValidationError("get_upc_section requires at least one instrument key")

    semaphore = asyncio.Semaphore(_UPC_STATUTES_FANOUT_CONCURRENCY)

    async def _fetch_one(client: UpcStatutesClient, key: str) -> dict | None:
        async with semaphore:
            record = await client.get_instrument(instrument=key, language=language)
        return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with UpcStatutesClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, k) for k in keys])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [k for k, r in zip(keys, fetched, strict=True) if r is None]

    if len(keys) == 1 and items:
        summary = _summarize_instrument(items[0])
    elif len(keys) == 1:
        summary = f"UPC instrument {keys[0]} — not found."
    else:
        head = f"Fetched {len(items)} of {len(keys)} UPC instruments."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_upc_statutes_provenance(
            "https://www.unifiedpatentcourt.org/en/court/legal-documents"
        ),
    )


@upc_mcp.tool(annotations=READ_ONLY)
async def list_upc_instruments(
    language: Annotated[
        str | None,
        "Filter to a single language; omit for all.",
    ] = None,
) -> ListEnvelope[dict]:
    """List the instruments bundled in the Unified Patent Court (UPC) statutes corpus.

    Each entry carries the instrument key, citation-ready short name,
    full title, language, source PDF URL, and page count. Pass an
    instrument key to ``get_upc_section`` for the full plain text, or
    use ``search_upc_statutes`` to query across all instruments. Per
    CONNECTOR_STANDARDS.md §5.8, ``list_*`` is a soft fit for vocabulary
    enumerators — kept intentionally.

    Related tools: search_upc_statutes, get_upc_section.
    """
    instruments = await list_instruments(language=language)
    items: list[dict] = [_dump(i) for i in instruments]  # type: ignore[misc]
    lang_label = language or "all"
    return ListEnvelope[dict](
        summary=f"UPC statutes instruments (lang={lang_label}) — {len(items)} entries.",
        items=items,
        provenance=_upc_statutes_provenance(
            "https://www.unifiedpatentcourt.org/en/court/legal-documents"
        ),
    )


__all__ = ["upc_mcp"]
