"""USITC MCP tools — EDIS investigations + documents, DataWeb, HTS, IDS.

The U.S. International Trade Commission (USITC) exposes four public
surfaces wrapped here:

* **EDIS** — Electronic Document Information System (``edis.usitc.gov``).
  Section 337 patent investigations and their full document records.
  Bearer token via ``USITC_EDIS_TOKEN``.
* **DataWeb** — official US import/export trade statistics
  (``datawebws.usitc.gov``). Bearer token via ``USITC_DATAWEB_TOKEN``.
* **HTS** — Harmonized Tariff Schedule (``hts.usitc.gov``). No auth.
* **IDS** — Intellectual Property Search investigation index. No auth.
"""

from __future__ import annotations

import asyncio
import base64
from datetime import date as _date
from pathlib import PurePosixPath
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, ResponseEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.filenames import usitc_attachment as _usitc_name
from law_tools_core.mcp import (
    BulkItem,
    download_bulk_response,
    download_response,
    fetch_with_cache,
    register_source,
)
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.usitc import (
    DataWebClient,
    EdisClient,
    EdisDocument,
    HtsClient,
    IdsClient,
)
from patent_client_agents.usitc.client import build_dataweb_query

usitc_mcp = FastMCP("USITC")

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9).
#
# One provenance helper for the whole USITC connector — the source
# name is shared ("U.S. International Trade Commission (USITC)") and
# each call points at the relevant USITC sub-host (EDIS, DataWeb, HTS,
# IDS) via the ``path`` argument or a full URL.
# ──────────────────────────────────────────────────────────────────────

_USITC_SOURCE_NAME = "U.S. International Trade Commission (USITC)"
_EDIS_BASE = "https://edis.usitc.gov"
_DATAWEB_BASE = "https://datawebws.usitc.gov"
_HTS_BASE = "https://hts.usitc.gov"
_IDS_BASE = "https://ids.usitc.gov"

# Bounded fan-out for list-accepting get_usitc_investigation (§5.4).
# EDIS responses are XML-parsed in-process — the cap keeps a 25-item
# portfolio from opening 25 sockets simultaneously while still amortizing
# Akamai TLS handshakes across the batch.
_USITC_FANOUT_CONCURRENCY = 5


def _usitc_provenance(path: str) -> Any:
    """Build a Provenance pointing at the appropriate USITC sub-host.

    ``path`` may be a full URL (https://...) or a path that will be
    appended to ``edis.usitc.gov`` (the default sub-host for the
    investigations/documents/attachments surface).
    """
    source_url = path if path.startswith("http") else f"{_EDIS_BASE}{path}"
    return make_provenance(source_url=source_url, source_name=_USITC_SOURCE_NAME)


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict (or pass through dicts).

    Every caller passes a Pydantic model from the upstream client; the
    fallback exists to be defensive if a dict slips through. Typed as
    ``dict[str, Any]`` so call sites can use ``.get(...)`` without
    per-call narrowing.
    """
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _parse_iso_date(value: str | None, *, field_name: str) -> _date | None:
    if not value:
        return None
    try:
        return _date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field_name} must be ISO date YYYY-MM-DD; got {value!r}") from exc


# ---------------------------------------------------------------------------
# Download fetcher (registered on import)
# ---------------------------------------------------------------------------


async def _fetch_usitc_attachment(path: str) -> tuple[bytes, str]:
    """Fetch a USITC EDIS attachment.

    Path format: ``{document_id}/attachments/{attachment_id}`` (remainder
    after stripping the ``usitc/documents/`` prefix).
    """
    parts = path.split("/")
    if len(parts) == 3 and parts[1] == "attachments":
        document_id, attachment_id = int(parts[0]), int(parts[2])
    elif len(parts) == 2:
        document_id, attachment_id = int(parts[0]), int(parts[1])
    else:
        raise ValueError(f"Expected {{doc_id}}/attachments/{{att_id}}, got: {path}")

    async with EdisClient() as client:
        result = await client.download_attachment(document_id, attachment_id)
        content = base64.b64decode(result.content_base64)
        filename = result.filename or f"usitc_{document_id}_{attachment_id}.pdf"
        return content, filename


register_source("usitc/documents", _fetch_usitc_attachment, "application/pdf")


# ---------------------------------------------------------------------------
# Lean projections + summarizers
# ---------------------------------------------------------------------------


def _stub_investigation(record: dict) -> dict:
    """Lean projection of a USITC EDIS investigation row (§5.5).

    Drops the upstream ``document_list_uri`` (an EDIS-auth-required URL
    agents can't follow directly) and keeps the scalar fields needed
    to triage a hit.
    """
    return {
        "investigation_number": record.get("investigation_number"),
        "title": record.get("title"),
        "investigation_status": record.get("investigation_status"),
        "investigation_phase": record.get("investigation_phase"),
        "investigation_type": record.get("investigation_type"),
        "docket_number": record.get("docket_number"),
    }


def _summarize_usitc_investigation(record: dict) -> str:
    """One-line Markdown summary of a single USITC EDIS investigation."""
    number = record.get("investigation_number") or "(no investigation number)"
    title = record.get("title") or "(no title)"
    status = record.get("investigation_status") or "(unknown status)"
    phase = record.get("investigation_phase")
    inv_type = record.get("investigation_type")
    head = f"**USITC investigation {number}** — {title}"
    line = f"Status: {status}."
    if phase:
        line += f" Phase: {phase}."
    if inv_type:
        line += f" Type: {inv_type}."
    return f"{head}\n{line}"


def _clean_edis_document(doc: object) -> dict:
    """Dump an EdisDocument and remove upstream URLs that require EDIS auth."""
    item = _dump(doc)
    # attachment_list_uri points to edis.usitc.gov and requires a token —
    # agents should use list_usitc_attachments(document_id=...) instead
    if isinstance(item, dict):
        item.pop("attachment_list_uri", None)
    return item  # type: ignore[return-value]


def _stub_edis_document(record: dict) -> dict:
    """Lean projection of an EDIS document row (§5.5)."""
    return {
        "id": record.get("id"),
        "investigation_number": record.get("investigation_number"),
        "document_type": record.get("document_type"),
        "title": record.get("title"),
        "security_level": record.get("security_level"),
        "filed_by": record.get("filed_by"),
        "firm_organization": record.get("firm_organization"),
        "document_date": record.get("document_date"),
        "official_received_date": record.get("official_received_date"),
    }


def _stub_hts_result(record: dict) -> dict:
    """Lean projection of an HTS search hit (§5.5).

    The upstream ``HtsSearchResult`` is already small (4 fields), but
    we name them explicitly so the lean default is stable across any
    upstream field additions.
    """
    return {
        "hts_number": record.get("hts_number"),
        "description": record.get("description"),
        "heading": record.get("heading"),
        "chapter": record.get("chapter"),
    }


def _stub_ids_investigation(record: dict) -> dict:
    """Lean projection of an IDS (USITC IP Search) investigation row (§5.5)."""
    return {
        "investigation_id": record.get("investigation_id"),
        "investigation_number": record.get("investigation_number"),
        "title": record.get("title"),
        "topic": record.get("topic"),
        "investigation_status": record.get("investigation_status"),
        "investigation_type": record.get("investigation_type"),
        "docket_number": record.get("docket_number"),
        "start_date": record.get("start_date"),
        "end_date": record.get("end_date"),
    }


def _parse_edis_date(date_str: str | None) -> str | None:
    """Extract YYYY-MM-DD from EDIS date strings.

    Handles both '2005-01-25 00:00:00.0' and '2024/05/16 00:00:00' formats.
    """
    if not date_str:
        return None
    if len(date_str) < 10:
        return None
    return date_str[:10].replace("/", "-")


# ---------------------------------------------------------------------------
# Tools — investigations
# ---------------------------------------------------------------------------


@usitc_mcp.tool(annotations=READ_ONLY)
async def search_usitc_investigations(
    investigation_number: Annotated[
        str | None,
        "Investigation number in EDIS format (e.g. '337-1234'). "
        "Used as a path segment per EDIS API — pass without the 'TA-' infix.",
    ] = None,
    phase: Annotated[
        str | None, "Phase filter (e.g. 'Violation', 'Preliminary', 'Final', 'Review2')."
    ] = None,
    investigation_type: Annotated[
        str | None,
        "Type filter (e.g. 'Sec 337', 'Import Injury', "
        "'Industry and Economic Analysis', 'Tariff Affairs & Trade Agreements').",
    ] = None,
    status: Annotated[
        str | None, "Status filter: 'PreInstitution', 'Active', 'Inactive', or 'Cancelled'."
    ] = None,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub (investigation "
        "number, title, status, phase, type, docket number). When True, "
        "every hit carries the full EDIS investigation record — prefer "
        "``get_usitc_investigation`` for one record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search U.S. International Trade Commission (USITC) Section 337 investigations via EDIS.

    EDIS is the USITC Electronic Document Information System. Filter by
    investigation number (path lookup), phase, type, or status. Lean
    stubs by default; pass ``full=True`` for the upstream record.

    Related tools: get_usitc_investigation, list_usitc_attachments,
    search_usitc_documents, download_usitc_investigation_documents.
    """
    kwargs: dict = {}
    if investigation_type:
        kwargs["investigationType"] = investigation_type
    if status:
        kwargs["investigationStatus"] = status

    async with EdisClient() as client:
        results = await client.list_investigations(
            investigation_number=investigation_number,
            investigation_phase=phase,
            **kwargs,
        )

    dumped = [_dump(r) for r in results]
    items = dumped if full else [_stub_investigation(r) for r in dumped]  # type: ignore[arg-type]

    filter_bits: list[str] = []
    if investigation_number:
        filter_bits.append(f"investigation_number={investigation_number}")
    if phase:
        filter_bits.append(f"phase={phase}")
    if investigation_type:
        filter_bits.append(f"type={investigation_type}")
    if status:
        filter_bits.append(f"status={status}")
    label = " ".join(filter_bits) or "(no filters)"

    path = (
        f"/data/investigation/{investigation_number}"
        if investigation_number
        else "/data/investigation"
    )
    return ListEnvelope[dict](
        summary=f"USITC investigations — {label}: {len(items)} hits.",
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_usitc_provenance(path),
    )


@usitc_mcp.tool(annotations=READ_ONLY)
async def get_usitc_investigation(
    investigation_number: Annotated[
        str | list[str],
        "USITC investigation number in EDIS format (e.g. '337-1234'), or a "
        "list of such numbers for portfolio workflows. Pass without the "
        "'TA-' infix (use '337-1234', not '337-TA-1234').",
    ],
) -> ListEnvelope[dict]:
    """Fetch one or more U.S. International Trade Commission (USITC) investigations from EDIS.

    EDIS (Electronic Document Information System) treats the investigation
    number as a path segment, so the underlying call is a per-record GET
    against ``/data/investigation/{investigation_number}``. Accepts either
    a single number or a list (§5.4); the response is always a
    ListEnvelope so the shape is stable. Bounded concurrent fan-out
    internally; order matches the input.

    Related tools: search_usitc_investigations, list_usitc_attachments,
    search_usitc_documents, download_usitc_investigation_documents.
    """
    numbers = (
        [investigation_number]
        if isinstance(investigation_number, str)
        else list(investigation_number)
    )
    if not numbers:
        raise ValidationError("get_usitc_investigation requires at least one investigation_number")

    semaphore = asyncio.Semaphore(_USITC_FANOUT_CONCURRENCY)

    async def _fetch_one(client: EdisClient, number: str) -> dict | None:
        async with semaphore:
            results = await client.list_investigations(investigation_number=number)
        if not results:
            return None
        # EDIS returns a list even for a single-number path lookup;
        # prefer an exact investigation_number match, else fall back to
        # the first row (some EDIS rows carry the full investigation
        # number including a phase suffix).
        dumped_rows = [_dump(r) for r in results]
        for row in dumped_rows:
            if isinstance(row, dict) and row.get("investigation_number") == number:
                return row
        first = dumped_rows[0]
        return first if isinstance(first, dict) else None

    async with EdisClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [n for n, r in zip(numbers, fetched, strict=True) if r is None]

    if len(numbers) == 1 and items:
        summary = _summarize_usitc_investigation(items[0])
    elif len(numbers) == 1:
        summary = f"USITC investigation {numbers[0]} — not found."
    else:
        head = f"Fetched {len(items)} of {len(numbers)} USITC investigations."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    path = f"/data/investigation/{numbers[0]}" if len(numbers) == 1 else "/data/investigation"
    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_usitc_provenance(path),
    )


# ---------------------------------------------------------------------------
# Tools — documents
# ---------------------------------------------------------------------------


@usitc_mcp.tool(annotations=READ_ONLY)
async def search_usitc_documents(
    investigation_number: Annotated[
        str | None,
        "Investigation number in EDIS format (e.g. '337-1234'). Partial numbers allowed.",
    ] = None,
    investigation_phase: Annotated[
        str | None, "Phase filter (e.g. 'Violation', 'Final', 'Review2')."
    ] = None,
    document_type: Annotated[
        str | None,
        "Document type (e.g. 'Motion', 'Order', 'Notice', 'Brief Filed With ALJ'). "
        "Must match exactly — partial matches not allowed.",
    ] = None,
    firm_org: Annotated[
        str | None,
        "Firm/organization name. Each word is treated as an OR search.",
    ] = None,
    security_level: Annotated[
        str | None, "Security level filter: 'Public', 'Confidential', or 'Limited'."
    ] = None,
    date_from: Annotated[
        str | None,
        "Filter documents on or after this date (YYYY-MM-DD). "
        "Triggers server-side pagination through all results.",
    ] = None,
    date_to: Annotated[
        str | None,
        "Filter documents on or before this date (YYYY-MM-DD). "
        "Triggers server-side pagination through all results.",
    ] = None,
    page_number: Annotated[
        int,
        "Page number (100 results per page). If ``more_available`` is true, "
        "increment to get the next page.",
    ] = 1,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub. When True, every hit "
        "carries the full EDIS document record.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search U.S. International Trade Commission (USITC) EDIS documents.

    Returns documents from the Electronic Document Information System
    (EDIS): ID, type, title, security level, filing party, date, firm,
    and investigation context. Use ``investigation_number`` to scope to
    a specific investigation. Up to 100 results per page; check
    ``more_available`` and increment ``page_number`` to paginate.

    When ``date_from`` or ``date_to`` is set, the server fetches all
    matching documents from EDIS (up to 3000) and filters by
    ``document_date``, then returns the requested page of filtered
    results.

    Related tools: search_usitc_investigations, list_usitc_attachments,
    download_usitc_attachment, download_usitc_investigation_documents.
    """
    kwargs: dict = {}
    if investigation_number:
        kwargs["investigationNumber"] = investigation_number
    if investigation_phase:
        kwargs["investigationPhase"] = investigation_phase
    if document_type:
        kwargs["documentType"] = document_type
    if firm_org:
        kwargs["firmOrg"] = firm_org
    if security_level:
        kwargs["securityLevel"] = security_level

    use_date_filter = date_from is not None or date_to is not None
    page_size = 100

    if not use_date_filter:
        kwargs["pageNumber"] = page_number
        async with EdisClient() as client:
            results = await client.list_documents(**kwargs)
        dumped = [_clean_edis_document(r) for r in results]
        items = dumped if full else [_stub_edis_document(r) for r in dumped]
        more = len(results) >= page_size
        return ListEnvelope[dict](
            summary=(
                f"USITC documents — page {page_number}: {len(items)} hits"
                + (f" (investigation {investigation_number})." if investigation_number else ".")
            ),
            items=items,
            more_available=more,
            next_cursor=None,
            provenance=_usitc_provenance("/data/document"),
        )

    # Server-side: fetch all pages from EDIS, filter by date, then paginate
    max_pages = 30
    all_docs: list = []
    async with EdisClient() as client:
        for api_page in range(1, max_pages + 1):
            kwargs["pageNumber"] = api_page
            batch = await client.list_documents(**kwargs)
            if not batch:
                break
            all_docs.extend(batch)

    filtered = []
    for doc in all_docs:
        doc_date = _parse_edis_date(doc.document_date)
        if doc_date is None:
            continue
        if date_from and doc_date < date_from:
            continue
        if date_to and doc_date > date_to:
            continue
        filtered.append(doc)

    start = (page_number - 1) * page_size
    page_results = filtered[start : start + page_size]
    dumped_page = [_clean_edis_document(r) for r in page_results]
    items = dumped_page if full else [_stub_edis_document(r) for r in dumped_page]
    return ListEnvelope[dict](
        summary=(
            f"USITC documents — page {page_number}: {len(items)} of {len(filtered)} "
            f"matched (date_from={date_from!r}, date_to={date_to!r})."
        ),
        items=items,
        more_available=start + page_size < len(filtered),
        next_cursor=None,
        provenance=_usitc_provenance("/data/document"),
    )


@usitc_mcp.tool(annotations=READ_ONLY)
async def list_usitc_attachments(
    document_id: Annotated[int, "EDIS document ID to list attachments for."],
) -> ListEnvelope[dict]:
    """List attachments for a U.S. International Trade Commission (USITC) EDIS document.

    EDIS (Electronic Document Information System) groups one or more
    attachments under each document record. Use
    ``download_usitc_attachment`` to fetch a specific attachment as a PDF.

    Related tools: search_usitc_documents, download_usitc_attachment,
    download_usitc_investigation_documents.
    """
    async with EdisClient() as client:
        results = await client.list_attachments(document_id)

    items: list[dict] = []
    for att in results:
        item = _dump(att)
        if isinstance(item, dict):
            # download_uri points at edis.usitc.gov and requires the
            # EDIS bearer token — strip it so agents use the registered
            # ``usitc/documents/{doc}/attachments/{att}`` resource path.
            item.pop("download_uri", None)
            items.append(item)

    return ListEnvelope[dict](
        summary=f"USITC document {document_id} — {len(items)} attachments.",
        items=items,
        provenance=_usitc_provenance(f"/data/attachment/{document_id}"),
    )


# ---------------------------------------------------------------------------
# Tools — HTS (Harmonized Tariff Schedule)
# ---------------------------------------------------------------------------


@usitc_mcp.tool(annotations=READ_ONLY)
async def search_hts_tariffs(
    query: Annotated[str, "Keyword to search HTS tariff codes (free text)."],
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub (hts_number, "
        "description, heading, chapter). When True, returns the upstream "
        "row verbatim — currently the same four fields, but stable across "
        "upstream additions.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search the U.S. Harmonized Tariff Schedule (HTS) for commodity classification codes.

    The HTS is the U.S. International Trade Commission (USITC) tariff
    classification taxonomy used by Customs and Border Protection to
    assess import duties. Keyword search returns HTS numbers,
    descriptions, headings, and chapters.

    No companion ``get_hts_tariff`` exists — HTS is a closed taxonomy
    whose canonical reference is the schedule itself; agents that need a
    specific code should search for it or use the public HTS site.

    Related tools: run_dataweb_report, search_usitc_investigations.
    """
    async with HtsClient() as client:
        results = await client.search(keyword=query)

    dumped = [_dump(r) for r in results]
    items = dumped if full else [_stub_hts_result(r) for r in dumped]  # type: ignore[arg-type]
    return ListEnvelope[dict](
        summary=f"USITC HTS — `{query}`: {len(items)} hits.",
        items=items,
        more_available=False,
        next_cursor=None,
        provenance=_usitc_provenance(f"{_HTS_BASE}/reststop/search?keyword={query}"),
    )


# ---------------------------------------------------------------------------
# Tools — DataWeb (trade statistics)
# ---------------------------------------------------------------------------


@usitc_mcp.tool(annotations=READ_ONLY)
async def run_dataweb_report(
    trade_type: Annotated[
        str,
        "Trade type: 'Import', 'Export', 'GenImp', 'TotExp', 'Balance', 'ForeignExp', 'ImpExp'.",
    ] = "Import",
    classification: Annotated[
        str,
        "Classification system: 'HTS', 'SITC', 'NAIC', 'SIC', 'QUICK', 'EXPERT'.",
    ] = "HTS",
    years: Annotated[
        str,
        "Comma-separated years, e.g. '2023,2024'. Defaults to '2024'.",
    ] = "2024",
    data_metrics: Annotated[
        str,
        "Comma-separated metrics: 'CONS_CUSTOMS_VALUE', 'CONS_FIR_UNIT_QUANT', "
        "'CONS_QUANTITY_2'. Defaults to 'CONS_CUSTOMS_VALUE'.",
    ] = "CONS_CUSTOMS_VALUE",
    commodities: Annotated[
        str | None,
        "Comma-separated commodity codes to filter (e.g. '8542,8541'). None = all commodities.",
    ] = None,
    granularity: Annotated[
        str,
        "HTS digit level: '2', '4', '6', '8', '10'. Default '2'.",
    ] = "2",
    aggregate_countries: Annotated[
        bool,
        "If true, aggregate all countries. If false, break out by country.",
    ] = True,
    aggregate_commodities: Annotated[
        bool,
        "If true, aggregate commodities. If false, break out by commodity code.",
    ] = True,
    scale: Annotated[
        str,
        "Value scale: '1' (actual dollars), '1000' (thousands), '1000000' (millions).",
    ] = "1",
    timeline: Annotated[
        str,
        "Time aggregation: 'Annual' or 'Monthly'.",
    ] = "Annual",
) -> ResponseEnvelope[dict]:
    """Pull US import/export statistics from USITC DataWeb (the official trade-statistics interface).

    DataWeb is the U.S. International Trade Commission's public trade-data
    interface. Query by commodity, country, and time period; returns
    tabular data with column headers and row values. Requires
    ``USITC_DATAWEB_TOKEN`` environment variable.

    Related tools: search_hts_tariffs, search_usitc_investigations.
    """
    year_list = [y.strip() for y in years.split(",")]
    metric_list = [m.strip() for m in data_metrics.split(",")]
    commodity_list = [c.strip() for c in commodities.split(",")] if commodities else None

    query = build_dataweb_query(
        trade_type=trade_type,
        classification=classification,
        years=year_list,
        timeline=timeline,
        data_metrics=metric_list,
        scale=scale,
        commodities=commodity_list,
        granularity=granularity,
        aggregate_countries=aggregate_countries,
        aggregate_commodities=aggregate_commodities,
    )

    async with DataWebClient() as client:
        result = await client.run_report(query)
    details = _dump(result)
    if not isinstance(details, dict):
        details = {"raw": details}

    row_count: int | None = None
    dto = details.get("dto") if isinstance(details, dict) else None
    if isinstance(dto, dict):
        # DataWeb's ``dto`` payload nests result rows under different keys
        # across runs; best-effort row count for the summary.
        for candidate in ("rows", "results", "data"):
            value = dto.get(candidate)
            if isinstance(value, list):
                row_count = len(value)
                break

    year_label = ",".join(year_list)
    head = f"**USITC DataWeb {trade_type} report** ({classification}, years {year_label})"
    if row_count is not None:
        head += f"\n{row_count} row(s); metrics: {', '.join(metric_list)}."
    else:
        head += f"\nMetrics: {', '.join(metric_list)}."

    return ResponseEnvelope[dict](
        summary=head,
        details=details,
        provenance=_usitc_provenance(f"{_DATAWEB_BASE}/dataweb/api/v2/report2/runReport"),
    )


# ---------------------------------------------------------------------------
# Tools — IDS (USITC IP Search)
# ---------------------------------------------------------------------------


@usitc_mcp.tool(annotations=READ_ONLY)
async def list_ids_investigations(
    limit: Annotated[
        int, "Max records to return (default 200; 4000+ exist, full payload exceeds MCP budget)."
    ] = 200,
    offset: Annotated[int, "Records to skip for pagination."] = 0,
    investigation_number_contains: Annotated[
        str | None, "Filter to investigations whose number contains this substring (e.g. '337-1')."
    ] = None,
    title_contains: Annotated[
        str | None,
        "Filter to investigations whose title contains this substring (case-insensitive).",
    ] = None,
    include_parties: Annotated[
        bool,
        "Include participants/staff arrays. Off by default — they're ~85% of payload size.",
    ] = False,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub. When True, every hit "
        "carries the full IDS record (still subject to ``include_parties``).",
    ] = False,
) -> ListEnvelope[dict]:
    """List U.S. International Trade Commission (USITC) IDS (Intellectual Property Search) investigations.

    The IDS endpoint returns ~4000 records in a single 11 MB payload.
    By default the tool drops ``participants``/``staff_contacts`` (the
    bulk of that payload) and returns the first ``limit`` records as
    lean stubs. ``total`` reports the unfiltered upstream size so
    callers can paginate or refine via ``investigation_number_contains``
    / ``title_contains``.

    Related tools: search_usitc_investigations, get_usitc_investigation,
    search_usitc_documents.
    """
    async with IdsClient() as client:
        results = await client.list_investigations()

    if investigation_number_contains:
        needle = investigation_number_contains
        results = [r for r in results if needle in (r.investigation_number or "")]
    if title_contains:
        needle = title_contains.lower()
        results = [r for r in results if needle in (r.title or "").lower()]

    total = len(results)
    page = results[offset : offset + limit]

    exclude = None if include_parties else {"participants", "staff_contacts"}
    dumped = [r.model_dump(exclude=exclude) for r in page]
    items = dumped if full else [_stub_ids_investigation(r) for r in dumped]

    return ListEnvelope[dict](
        summary=(
            f"USITC IDS investigations — {len(items)} of {total} total "
            f"(offset {offset}, limit {limit})."
        ),
        items=items,
        more_available=offset + len(page) < total,
        next_cursor=None,
        provenance=_usitc_provenance(f"{_IDS_BASE}/investigations.json"),
    )


# ---------------------------------------------------------------------------
# Tools — downloads (Shape E — shape preserved, docstring polish only)
# ---------------------------------------------------------------------------


_USITC_BULK_CAP = 25
_USITC_PAGE_LIMIT = 50  # safety: don't walk more than 50 pages of doc listings


@usitc_mcp.tool(annotations=READ_ONLY)
async def download_usitc_investigation_documents(
    investigation_number: Annotated[
        str,
        "USITC EDIS investigation number (e.g. '337-TA-1234'). Every "
        "attachment for every document in this investigation is a candidate.",
    ],
    item_ids: Annotated[
        list[str] | None,
        "Specific items keyed as '{document_id}/attachments/{attachment_id}' "
        "(matches the canonical EDIS path). None means 'all attachments matching "
        "the other filters'.",
    ] = None,
    document_types: Annotated[
        list[str] | None,
        "Filter to these EDIS document types (e.g. ['Motion', 'Order', "
        "'Brief Filed With ALJ']). Must match exactly.",
    ] = None,
    after: Annotated[
        str | None,
        "Include only documents officially received on or after this date (ISO YYYY-MM-DD).",
    ] = None,
    before: Annotated[
        str | None,
        "Include only documents officially received on or before this date (ISO YYYY-MM-DD).",
    ] = None,
) -> dict:
    """Bulk-download U.S. International Trade Commission (USITC) EDIS attachments for one investigation.

    EDIS (Electronic Document Information System) two-level enumeration:
    pages through every document in the investigation, then lists each
    document's attachments. Cap: 25 attachments per call (USITC PDFs are
    routinely huge — exhibits often hundreds of MB each).

    The cap applies to *attachments*, not documents — a single EDIS
    document can carry multiple PDFs. Narrow with ``item_ids``,
    ``document_types``, or date range to fit under the cap. Use
    ``search_usitc_documents`` and ``list_usitc_attachments`` to preview.

    Related tools: download_usitc_attachment, list_usitc_attachments,
    search_usitc_documents, get_usitc_investigation.
    """
    after_d = _parse_iso_date(after, field_name="after")
    before_d = _parse_iso_date(before, field_name="before")
    type_set = set(document_types) if document_types else None
    id_set = set(item_ids) if item_ids else None

    # Fast path: when the caller already knows the exact attachments,
    # skip the full per-investigation page walk (~60s for 337-1380's
    # 600 docs against a slow EDIS day) and just hand the explicit IDs
    # straight to the bulk-download fetcher.
    if id_set:
        bulk_items_fast: list[BulkItem] = []
        for item in id_set:
            try:
                doc_part, _attachments_kw, att_part = item.split("/", 2)
                doc_id = int(doc_part)
                att_id = int(att_part)
            except (ValueError, AttributeError):
                raise ValidationError(
                    f"item_ids entries must look like '<doc_id>/attachments/<att_id>'; got {item!r}"
                ) from None
            bulk_items_fast.append(
                BulkItem(
                    item_id=item,
                    resource_path=f"usitc/documents/{item}",
                    metadata={
                        "document_id": doc_id,
                        "attachment_id": att_id,
                        "investigation_number": investigation_number,
                    },
                )
            )
        if len(bulk_items_fast) > _USITC_BULK_CAP:
            raise ValidationError(
                f"item_ids has {len(bulk_items_fast)} entries; max {_USITC_BULK_CAP} per call."
            )

        async def _fetcher_fast(item: BulkItem) -> tuple[bytes, str]:
            return await fetch_with_cache(item.resource_path)

        return await download_bulk_response(
            bulk_items_fast,
            _fetcher_fast,
            container_label=f"{investigation_number}_documents",
            container_metadata={
                "container": investigation_number,
                "investigation_number": investigation_number,
            },
            content_type_single="application/pdf",
        )

    # 1. Page through documents for the investigation. EDIS doesn't return a
    # total count — walk pages in parallel batches and stop at the first
    # empty page.
    documents: list[EdisDocument] = []
    async with EdisClient() as client:
        page_batch = 8
        page = 1
        while page <= _USITC_PAGE_LIMIT:
            stop = min(page + page_batch, _USITC_PAGE_LIMIT + 1)
            batches = await asyncio.gather(
                *(
                    client.list_documents(investigationNumber=investigation_number, pageNumber=p)
                    for p in range(page, stop)
                )
            )
            empty_seen = False
            for b in batches:
                if not b:
                    empty_seen = True
                    break
                documents.extend(b)
            if empty_seen:
                break
            page = stop

        # 2. Filter docs by type/date BEFORE listing attachments — every
        # attachment-list call is a separate HTTP round trip.
        def _doc_passes(doc: EdisDocument) -> bool:
            if type_set and doc.document_type not in type_set:
                return False
            doc_date = _parse_edis_date(doc.official_received_date or doc.document_date)
            if after_d or before_d:
                try:
                    parsed = _date.fromisoformat(doc_date) if doc_date else None
                except ValueError:
                    parsed = None
                if after_d and (parsed is None or parsed < after_d):
                    return False
                if before_d and (parsed is None or parsed > before_d):
                    return False
            return True

        filtered_docs = [d for d in documents if _doc_passes(d)]

        # 3. Concurrent attachment listing — 20 in flight is enough to
        # absorb EDIS latency without tripping rate limits in practice.
        sem = asyncio.Semaphore(20)

        async def _list(doc):
            async with sem:
                atts = await client.list_attachments(doc.id)
                return doc, atts

        listings = await asyncio.gather(*(_list(d) for d in filtered_docs))

        candidates: list[dict] = []
        for doc, attachments in listings:
            doc_date = _parse_edis_date(doc.official_received_date or doc.document_date)
            for att in attachments:
                item_id = f"{doc.id}/attachments/{att.id}"
                if id_set and item_id not in id_set:
                    continue
                candidates.append(
                    {
                        "item_id": item_id,
                        "document_id": doc.id,
                        "attachment_id": att.id,
                        "document_type": doc.document_type,
                        "document_title": doc.title,
                        "document_date": doc_date,
                        "firm_organization": doc.firm_organization,
                        "filed_by": doc.filed_by,
                        "attachment_title": att.title,
                        "page_count": att.page_count,
                        "file_size": att.file_size,
                        "original_file_name": att.original_file_name,
                    }
                )

    if not candidates:
        raise ValidationError(
            f"No USITC attachments in investigation {investigation_number} match the given filters."
        )
    if len(candidates) > _USITC_BULK_CAP:
        raise ValidationError(
            f"Investigation {investigation_number} has {len(candidates)} attachments "
            f"matching the filters; max {_USITC_BULK_CAP} per call. Narrow with "
            f"item_ids, document_types, or date range — or paginate manually with "
            f"list_usitc_attachments."
        )

    bulk_items = [
        BulkItem(
            item_id=c["item_id"],
            resource_path=f"usitc/documents/{c['item_id']}",
            metadata={k: v for k, v in c.items() if k != "item_id"},
        )
        for c in candidates
    ]

    async def _fetcher(item: BulkItem) -> tuple[bytes, str]:
        return await fetch_with_cache(item.resource_path)

    return await download_bulk_response(
        bulk_items,
        _fetcher,
        container_label=f"{investigation_number}_documents",
        container_metadata={
            "container": investigation_number,
            "investigation_number": investigation_number,
        },
        content_type_single="application/pdf",
    )


@usitc_mcp.tool(annotations=READ_ONLY)
async def download_usitc_attachment(
    document_id: Annotated[int, "EDIS document ID."],
    attachment_id: Annotated[int, "EDIS attachment ID."],
) -> dict:
    """Download a U.S. International Trade Commission (USITC) EDIS attachment as a PDF.

    EDIS (Electronic Document Information System) stores party filings
    as document/attachment pairs. Returns a signed ``download_url`` (or
    ``file_path`` in local stdio mode) plus ``filename``,
    ``content_type``, ``size_bytes``, ``document_id``, ``attachment_id``.

    Related tools: list_usitc_attachments, search_usitc_documents,
    download_usitc_investigation_documents.
    """
    async with EdisClient() as client:
        result = await client.download_attachment(document_id, attachment_id)
        ext = (PurePosixPath(result.filename or "").suffix.lstrip(".") or "pdf").lower()
        filename = _usitc_name(
            document_id=document_id,
            attachment_id=attachment_id,
            extension=ext,
        )
        content = base64.b64decode(result.content_base64)
        return await download_response(
            f"usitc/documents/{document_id}/attachments/{attachment_id}",
            content,
            filename=filename,
            content_type=result.content_type or "application/pdf",
            document_id=document_id,
            attachment_id=attachment_id,
        )
