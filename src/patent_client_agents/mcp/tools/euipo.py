"""EUIPO MCP tools — Trademark Search + Design Search.

Read-only access to the EUIPO Trademark and Design (RCD) registers via
OAuth 2.0 client_credentials. Env-gated: tools register only when
``EUIPO_CLIENT_ID`` and ``EUIPO_CLIENT_SECRET`` are both set. Same
client + subscription works for both products.

Set ``EUIPO_ENV=sandbox`` to point at the sandbox host (no identity-
document approval required, but the dataset is a frozen historical
snapshot + synthetic test rows). Production access requires emailing
ID documents to ``docs.apiplatform@euipo.europa.eu``.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_tool
from patent_client_agents.euipo_designs import EuipoDesignsClient
from patent_client_agents.euipo_trademarks import EuipoTrademarksClient
from patent_client_agents.shared.envelope import dump
from patent_client_agents.shared.fanout import FetchedList, as_id_list, fetch_many, fetched_summary
from patent_client_agents.shared.provenance import provenance_for

euipo_mcp = FastMCP("EUIPO")

_EUIPO_REQUIRED_ENV: list[str] = ["EUIPO_CLIENT_ID", "EUIPO_CLIENT_SECRET"]

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). EUIPO trademarks and
# designs are served from sibling REST APIs under the same host; one
# provenance helper covers both via a path argument.
# ──────────────────────────────────────────────────────────────────────

_EUIPO_BASE = "https://api.euipo.europa.eu"
_EUIPO_NAME = "EUIPO"


def _euipo_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}`` for EUIPO REST APIs."""
    return provenance_for(
        source_url=f"{_EUIPO_BASE}{path}",
        source_name=_EUIPO_NAME,
    )


def _first_applicant_name(record: dict) -> str | None:
    applicants = record.get("applicants") or []
    if applicants:
        first = applicants[0]
        if isinstance(first, dict):
            return first.get("name")
    return None


def _stub_euipo_trademark(record: dict) -> dict:
    """Lean projection of an EUIPO trademark search row (§5.5)."""
    word_mark = record.get("wordMarkSpecification") or {}
    verbal_element = word_mark.get("verbalElement") if isinstance(word_mark, dict) else None
    return {
        "application_number": record.get("applicationNumber"),
        "verbal_element": verbal_element,
        "owner_name": _first_applicant_name(record),
        "status": record.get("status"),
        "mark_feature": record.get("markFeature"),
        "application_date": record.get("applicationDate"),
        "registration_date": record.get("registrationDate"),
        "nice_classes": record.get("niceClasses") or [],
    }


def _stub_euipo_design(record: dict) -> dict:
    """Lean projection of an EUIPO design search row (§5.5)."""
    return {
        "design_number": record.get("designNumber"),
        "application_number": record.get("applicationNumber"),
        "owner_name": _first_applicant_name(record),
        "status": record.get("status"),
        "application_date": record.get("applicationDate"),
        "registration_date": record.get("registrationDate"),
        "locarno_classes": record.get("locarnoClasses") or [],
    }


def _summarize_euipo_trademark(record: dict) -> str:
    """One-line Markdown summary for a single EUIPO trademark record."""
    appno = record.get("applicationNumber") or "(no appno)"
    word_mark = record.get("wordMarkSpecification") or {}
    verbal = (
        word_mark.get("verbalElement") if isinstance(word_mark, dict) else None
    ) or "(no verbal element)"
    owner = _first_applicant_name(record) or "(no owner)"
    status = record.get("status") or "(unknown status)"
    filing = record.get("applicationDate") or "?"
    reg = record.get("registrationDate")
    head = f"**EUTM {appno}** — {verbal} (owner: {owner})"
    line = f"Status: {status}. Filed {filing}"
    if reg:
        line += f"; registered {reg}."
    else:
        line += "."
    return f"{head}\n{line}"


def _summarize_euipo_design(record: dict) -> str:
    """One-line Markdown summary for a single EUIPO design record."""
    design_no = record.get("designNumber") or "(no design#)"
    owner = _first_applicant_name(record) or "(no owner)"
    status = record.get("status") or "(unknown status)"
    filing = record.get("applicationDate") or "?"
    reg = record.get("registrationDate")
    locarno = record.get("locarnoClasses") or []
    locarno_str = ", ".join(locarno) if locarno else "(no Locarno classes)"
    head = f"**RCD {design_no}** — Locarno {locarno_str} (owner: {owner})"
    line = f"Status: {status}. Filed {filing}"
    if reg:
        line += f"; registered {reg}."
    else:
        line += "."
    return f"{head}\n{line}"


# ---------------------------------------------------------------------------
# Trademarks
# ---------------------------------------------------------------------------


@conditional_tool(euipo_mcp, requires_env=_EUIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_euipo_trademarks(
    query: Annotated[
        str | None,
        (
            "RSQL filter expression. Examples: "
            "'wordMarkSpecification.verbalElement==*Apple* and status==REGISTERED' "
            "or 'applicationDate>=2024-01-01 and niceClasses=all=(25,28)'. "
            "Omit for an unfiltered listing of the full register."
        ),
    ] = None,
    page: Annotated[int, "0-indexed page number"] = 0,
    size: Annotated[int, "Page size, 10..100"] = 25,
    sort: Annotated[
        str | None,
        "Sort spec, e.g. 'applicationDate:desc' or 'applicationNumber:asc'",
    ] = None,
    fields: Annotated[
        str | None,
        "EBNF field selector to trim the payload, e.g. '!(goodsAndServices)'",
    ] = None,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: application "
        "number, verbal element (mark text), owner, status, mark feature, "
        "filing date, registration date, Nice classes. When True, every "
        "hit carries the full EUIPO list-view row — prefer "
        "``get_euipo_trademark`` for one record at full depth.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search European Union trademarks (EUTMs + EU-designated IRs) using RSQL.

    Returns a lean stub per hit by default so result sets stay small.
    For the full record of a single mark, call ``get_euipo_trademark``.
    To return the upstream-shaped row for every hit, pass ``full=True``.

    Related tools: get_euipo_trademark, search_euipo_designs.
    """
    async with EuipoTrademarksClient() as client:
        result = await client.search(query=query, page=page, size=size, sort=sort, fields=fields)

    dumped = dump(result, by_alias=True)
    assert isinstance(dumped, dict)
    rows = list(dumped.get("trademarks") or [])
    total = dumped.get("totalElements")
    total_pages = dumped.get("totalPages")
    items = rows if full else [_stub_euipo_trademark(r) for r in rows]
    more = bool(total_pages is not None and page + 1 < int(total_pages))
    query_label = f"`{query}`" if query else "(unfiltered)"
    summary_total = f"{len(items)} of {total} hits" if total is not None else f"{len(items)} hits"
    return ListEnvelope[dict](
        summary=f"EUIPO trademarks — {query_label}: {summary_total} (page {page}).",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_euipo_provenance("/trademark-search/trademarks"),
    )


@conditional_tool(euipo_mcp, requires_env=_EUIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_euipo_trademark(
    application_number: Annotated[
        str | list[str],
        (
            "EUIPO trademark application number (the canonical EUTM identifier; "
            "also serves as the registration number once granted). 9-digit "
            "zero-padded string (e.g. '000274084') or 'W########[A]' for "
            "international registrations designating the EU. Pass a list for "
            "portfolio workflows; the response shape stays a ListEnvelope."
        ),
    ],
) -> FetchedList[dict]:
    """Get full European Union trademark records by EUTM application number.

    Accepts either a single application number or a list (§5.4) and fans
    out internally with bounded concurrency; order is preserved. Returns
    ~40 fields per mark including prosecution history, oppositions,
    cancellations, appeals, decisions, and the multilingual
    goods-and-services classification. Media bytes (image / sound / video /
    3D model) are served by dedicated client endpoints, not exposed here.

    Related tools: search_euipo_trademarks, get_euipo_design.
    """
    numbers = as_id_list(application_number, noun="EUIPO trademark application number")

    async with EuipoTrademarksClient() as client:

        async def _fetch_one(appno: str) -> dict:
            record = await client.get_trademark(appno)
            return dump(record, by_alias=True)  # type: ignore[return-value]

        results, not_found = await fetch_many(
            numbers, _fetch_one, single=isinstance(application_number, str)
        )

    if len(numbers) == 1:
        summary = _summarize_euipo_trademark(results[0])
        path = f"/trademark-search/trademarks/{numbers[0]}"
    else:
        summary = fetched_summary(len(results), len(numbers), "EUIPO trademarks", not_found)
        path = "/trademark-search/trademarks"

    return FetchedList[dict](
        summary=summary,
        items=results,
        not_found=not_found,
        provenance=_euipo_provenance(path),
    )


# ---------------------------------------------------------------------------
# Designs (RCDs)
# ---------------------------------------------------------------------------


@conditional_tool(euipo_mcp, requires_env=_EUIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def search_euipo_designs(
    query: Annotated[
        str | None,
        (
            "RSQL filter expression. Examples: "
            "'applicationDate>=2024-01-01 and locarnoClasses=in=(14.03,14.04)' "
            "or 'status==REGISTERED_AND_FULLY_PUBLISHED'. "
            "Omit for an unfiltered listing of the full register."
        ),
    ] = None,
    page: Annotated[int, "0-indexed page number"] = 0,
    size: Annotated[int, "Page size, 10..100"] = 25,
    sort: Annotated[str | None, "Sort spec, e.g. 'applicationDate:desc'"] = None,
    fields: Annotated[str | None, "EBNF field selector"] = None,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: design number, "
        "application number, owner, status, filing date, registration date, "
        "Locarno classes. When True, every hit carries the full EUIPO "
        "list-view row — prefer ``get_euipo_design`` for one record at "
        "full depth.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Registered Community Designs (EU registered designs) using RSQL.

    Returns a lean stub per hit by default. A multi-design application
    produces one entry per indexed design (e.g. ``099037115-0001``,
    ``099037115-0002``). For the full record of one design, call
    ``get_euipo_design``; for the upstream-shaped row across the result
    set, pass ``full=True``.

    Related tools: get_euipo_design, search_euipo_trademarks.
    """
    async with EuipoDesignsClient() as client:
        result = await client.search(query=query, page=page, size=size, sort=sort, fields=fields)

    dumped = dump(result, by_alias=True)
    assert isinstance(dumped, dict)
    rows = list(dumped.get("designs") or [])
    total = dumped.get("totalElements")
    total_pages = dumped.get("totalPages")
    items = rows if full else [_stub_euipo_design(r) for r in rows]
    more = bool(total_pages is not None and page + 1 < int(total_pages))
    query_label = f"`{query}`" if query else "(unfiltered)"
    summary_total = f"{len(items)} of {total} hits" if total is not None else f"{len(items)} hits"
    return ListEnvelope[dict](
        summary=f"EUIPO designs — {query_label}: {summary_total} (page {page}).",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_euipo_provenance("/design-search/designs"),
    )


@conditional_tool(euipo_mcp, requires_env=_EUIPO_REQUIRED_ENV, annotations=READ_ONLY)
async def get_euipo_design(
    design_number: Annotated[
        str | list[str],
        (
            "Registered Community Design number, format NNNNNNNNN-NNNN "
            "(9 digits + dash + 4 digits, e.g. '099037115-0001'). Pass a "
            "list for portfolio workflows; the response shape stays a "
            "ListEnvelope."
        ),
    ],
) -> FetchedList[dict]:
    """Get full Registered Community Design records by design number.

    Accepts either a single design number or a list (§5.4) and fans out
    internally with bounded concurrency; order is preserved. Returns
    prosecution history, multilingual product indications, view metadata
    (image angles), Locarno classification, priorities, and decisions.
    View image bytes and 3D model bytes are served by dedicated client
    endpoints, not exposed here.

    Related tools: search_euipo_designs, get_euipo_trademark.
    """
    numbers = as_id_list(design_number, noun="EUIPO design number")

    async with EuipoDesignsClient() as client:

        async def _fetch_one(dno: str) -> dict:
            record = await client.get_design(dno)
            return dump(record, by_alias=True)  # type: ignore[return-value]

        results, not_found = await fetch_many(
            numbers, _fetch_one, single=isinstance(design_number, str)
        )

    if len(numbers) == 1:
        summary = _summarize_euipo_design(results[0])
        path = f"/design-search/designs/{numbers[0]}"
    else:
        summary = fetched_summary(len(results), len(numbers), "EUIPO designs", not_found)
        path = "/design-search/designs"

    return FetchedList[dict](
        summary=summary,
        items=results,
        not_found=not_found,
        provenance=_euipo_provenance(path),
    )


__all__ = ["euipo_mcp"]
