"""USPTO Trademark MCP tools (TESS search, TMEP, TSDR, trademark assignments).

Tools backed by:

- ``patent_client_agents.uspto_tmsearch`` — TESS Elasticsearch search.
  Needs an AWS WAF token (see token_manager docs); install with the
  ``[tmsearch]`` extra to enable in-process token minting via Playwright.
- ``patent_client_agents.tmep`` — TMEP corpus search/lookup. No auth.
- ``patent_client_agents.uspto_tsdr`` — TSDR status / documents.
  Requires ``USPTO_TSDR_API_KEY``.
- ``patent_client_agents.uspto_trademark_assignments`` — Assignment Center
  records. No auth.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.tmep import SearchInput, get_section, search
from patent_client_agents.uspto_tmsearch import TmsearchClient
from patent_client_agents.uspto_trademark_assignments import TrademarkAssignmentClient
from patent_client_agents.uspto_tsdr import TsdrClient

trademarks_mcp = FastMCP("Trademarks")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


def _dump_list(items: list) -> dict:
    return {"results": [_dump(i) for i in items]}


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). See uspto.py for the
# canonical template; this file adds source-specific helpers for TM Search
# (TESS) and TSDR.
# ──────────────────────────────────────────────────────────────────────

_TMSEARCH_BASE = "https://tmsearch.uspto.gov"
_TMSEARCH_NAME = "USPTO Trademark Search (TESS)"
_TSDR_BASE = "https://tsdrapi.uspto.gov"
_TSDR_NAME = "USPTO TSDR"


def _tmsearch_provenance(path: str) -> Any:
    return make_provenance(source_url=f"{_TMSEARCH_BASE}{path}", source_name=_TMSEARCH_NAME)


def _tsdr_provenance(path: str) -> Any:
    return make_provenance(source_url=f"{_TSDR_BASE}{path}", source_name=_TSDR_NAME)


def _stub_trademark(record: dict) -> dict:
    """Lean projection of a TESS trademark search row (§5.5)."""
    return {
        "serial_number": record.get("serialNumber"),
        "registration_number": record.get("registrationNumber"),
        "wordmark": record.get("wordmark") or record.get("markIdentification"),
        "owner_name": record.get("ownerName"),
        "filing_date": record.get("filingDate"),
        "registration_date": record.get("registrationDate"),
        "status_code": record.get("statusCode"),
        "status_text": record.get("statusText") or record.get("status"),
    }


def _summarize_trademark(record: dict) -> str:
    """One-line Markdown summary of a single trademark record."""
    serial = record.get("serialNumber") or "(no serial)"
    mark = record.get("wordmark") or record.get("markIdentification") or "(no mark)"
    owner = record.get("ownerName") or "(no owner)"
    status = record.get("statusText") or record.get("status") or "(unknown status)"
    reg = record.get("registrationNumber")
    head = f"**US trademark {serial}** — {mark} (owner: {owner})"
    line = f"Status: {status}."
    if reg:
        line = f"Registration {reg}. {line}"
    return f"{head}\n{line}"


def _classify_tm_identifier(value: str) -> str:
    """Return 'serial' or 'registration' from a numeric trademark identifier.

    USPTO serial numbers are 8 digits; registration numbers are typically
    7. Anything else raises ``ValidationError`` — auto-detection should be
    a help, not a guess.
    """
    raw = value.strip()
    if not raw.isdigit():
        raise ValidationError(
            f"trademark identifier must be all digits; got {value!r}. "
            f"Accepts 8-digit serial numbers (e.g. '97123456') or 7-digit "
            f"registration numbers (e.g. '1234567')."
        )
    if len(raw) == 8:
        return "serial"
    if len(raw) in (6, 7):
        return "registration"
    raise ValidationError(
        f"trademark identifier {value!r} has {len(raw)} digits; expected 8 (serial) "
        f"or 6-7 (registration)."
    )


_TM_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------
# Trademark Search (TESS)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_trademarks(
    query: Annotated[
        str,
        "Search query — a wordmark, owner name, or goods/services description.",
    ],
    search_by: Annotated[
        str,
        "Which field to search. 'wordmark' (default) — trademark text; 'owner' — registrant name; "
        "'goods_services' — goods/services description. The legacy 'general' alias is "
        "equivalent to 'wordmark'.",
    ] = "wordmark",
    paginate_all: Annotated[
        bool,
        "When true, auto-paginates through all matching results (wordmark/owner only). "
        "Ignored for goods_services.",
    ] = False,
    max_results: Annotated[
        int,
        "Cap on total results when paginate_all=True.",
    ] = 500,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: serial, wordmark, owner, "
        "status, filing/registration dates, registration number. When True, returns "
        "the full TESS record per hit (large; prefer ``get_trademark`` for one).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO trademarks by wordmark, owner, or goods/services (TESS).

    Returns lean stubs by default. Use ``get_trademark`` for a full record by
    serial or registration number, and ``get_trademark_status`` for current
    TSDR status on one or many marks.

    Related tools: get_trademark, get_trademark_status, get_trademark_documents,
    search_trademark_assignments.
    """
    field = search_by.strip().lower()
    if field == "general":
        field = "wordmark"
    if field not in ("wordmark", "owner", "goods_services"):
        raise ValidationError(
            f"search_by must be 'wordmark', 'owner', or 'goods_services'; got {search_by!r}"
        )

    async with TmsearchClient() as client:
        if paginate_all:
            if field == "goods_services":
                raise ValidationError(
                    "paginate_all is not supported for search_by='goods_services'"
                )
            kwargs: dict = {"max_results": max_results}
            if field == "owner":
                kwargs["owner"] = query
            else:
                kwargs["wordmark"] = query
            raw_results = await client.search_all(**kwargs)
            results = [_dump(r) for r in raw_results]
        else:
            if field == "wordmark":
                response = await client.search(wordmark=query)
            elif field == "owner":
                response = await client.search_owner(query)
            else:  # goods_services
                response = await client.search(goods_services=query)
            results = [_dump(r) for r in (response.results or [])]

    items = results if full else [_stub_trademark(r) for r in results]
    return ListEnvelope[dict](
        summary=f"USPTO trademarks (by {field}) — `{query}`: {len(items)} hits.",
        items=items,
        provenance=_tmsearch_provenance("/prod-stage-v1-0-0/tmsearch"),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark(
    serial_number: Annotated[
        str | list[str],
        "USPTO trademark serial number (8 digits, e.g. '97123456') OR registration "
        "number (typically 7 digits, e.g. '1234567'). Auto-detected by digit count. "
        "Pass a list for portfolio workflows; the response shape stays a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Get one or more USPTO trademark records (TESS) by serial or registration number.

    Auto-detects serial vs. registration by digit count (8 → serial, 6-7 →
    registration). Accepts either a single string or a list (§5.4); the
    response is always a ListEnvelope so the shape is stable.

    Returns full trademark details: wordmark, owner, goods/services, filing
    and registration dates, status. For current status only (no full record),
    use ``get_trademark_status`` (TSDR).

    Related tools: search_trademarks, get_trademark_status, get_trademark_documents.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_trademark requires at least one identifier")

    semaphore = asyncio.Semaphore(_TM_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TmsearchClient, ident: str) -> dict | None:
        kind = _classify_tm_identifier(ident)
        async with semaphore:
            if kind == "serial":
                record = await client.get_by_serial(ident)
            else:
                record = await client.get_by_registration(ident)
        return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with TmsearchClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [n for n, r in zip(numbers, fetched, strict=True) if r is None]

    if len(numbers) == 1 and items:
        summary = _summarize_trademark(items[0])
    elif len(numbers) == 1:
        summary = f"USPTO trademark {numbers[0]} — not found."
    else:
        head = f"Fetched {len(items)} of {len(numbers)} USPTO trademarks."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    # Provenance: per-record path for single ID, base path for multi.
    if len(numbers) == 1:
        kind = _classify_tm_identifier(numbers[0])
        path = f"/prod-stage-v1-0-0/tmsearch?{kind}={numbers[0]}"
    else:
        path = "/prod-stage-v1-0-0/tmsearch"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tmsearch_provenance(path),
    )


# ---------------------------------------------------------------
# TSDR (Trademark Status & Document Retrieval)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_status(
    serial_number: Annotated[
        str | list[str],
        "USPTO trademark serial number, or a list for portfolio status checks. "
        "Examples: '97123456', ['97123456', '97654321'].",
    ],
) -> ListEnvelope[dict]:
    """Get current trademark status from TSDR for one or many marks.

    Accepts a single serial number or a list (§5.4) and returns a
    ListEnvelope of TSDR status records: filing date, registration date,
    mark text, status code and description. Bounded concurrent fan-out
    internally. Requires ``USPTO_TSDR_API_KEY``.

    Replaces the deleted ``batch_trademark_status`` — pass a list here
    instead.

    Related tools: get_trademark, get_trademark_documents, get_trademark_last_update.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_trademark_status requires at least one serial number")

    semaphore = asyncio.Semaphore(_TM_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TsdrClient, n: str) -> dict:
        async with semaphore:
            return _dump(await client.get_status(n))  # type: ignore[return-value]

    async with TsdrClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = f"TSDR status for USPTO trademark {numbers[0]}."
        path = f"/ts/cd/casestatus/sn{numbers[0]}/info.xml"
    else:
        summary = f"TSDR status for {len(numbers)} USPTO trademarks: {', '.join(numbers)}."
        path = "/ts/cd/casestatus"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tsdr_provenance(path),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_documents(
    serial_number: Annotated[str, "USPTO trademark serial number (8 digits)."],
) -> ListEnvelope[dict]:
    """List prosecution documents (office actions, responses, registration certs) from TSDR.

    Returns a ListEnvelope of document records for one trademark application.
    Requires ``USPTO_TSDR_API_KEY``.

    Related tools: get_trademark_status, get_trademark, search_trademarks.
    """
    async with TsdrClient() as client:
        docs = await client.get_documents(serial_number)

    items = [_dump(d) for d in docs]
    return ListEnvelope[dict](
        summary=(
            f"TSDR prosecution documents for USPTO trademark {serial_number} "
            f"— {len(items)} documents."
        ),
        items=items,
        provenance=_tsdr_provenance(f"/ts/cd/casedocs/sn{serial_number}/index.xml"),
    )


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_trademark_last_update(
    serial_number: Annotated[
        str | list[str],
        "USPTO trademark serial number, or a list for portfolio checks. "
        "Examples: '97123456', ['97123456', '97654321'].",
    ],
) -> ListEnvelope[dict]:
    """Get last-update timestamps for one or many trademark cases (TSDR).

    Returns a ListEnvelope of records reporting when each trademark case was
    last modified at the USPTO. Useful for change-detection sweeps across a
    portfolio. Requires ``USPTO_TSDR_API_KEY``.

    Related tools: get_trademark_status, get_trademark_documents.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_trademark_last_update requires at least one serial number")

    semaphore = asyncio.Semaphore(_TM_FANOUT_CONCURRENCY)

    async def _fetch_one(client: TsdrClient, n: str) -> dict:
        async with semaphore:
            return _dump(await client.get_last_update(n))  # type: ignore[return-value]

    async with TsdrClient() as client:
        items = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(numbers) == 1:
        summary = f"TSDR last-update for USPTO trademark {numbers[0]}."
        path = f"/ts/cd/caselastupdate/sn{numbers[0]}"
    else:
        summary = f"TSDR last-update for {len(numbers)} trademarks: {', '.join(numbers)}."
        path = "/ts/cd/caselastupdate"

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_tsdr_provenance(path),
    )


# ---------------------------------------------------------------
# TMEP (Trademark Manual of Examining Procedure)
# ---------------------------------------------------------------


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_tmep(
    query: Annotated[str, "Search query for the TMEP"],
) -> dict:
    """Search the Trademark Manual of Examining Procedure.

    Returns matching TMEP sections with relevance-ranked snippets.
    Useful for finding examination guidance on trademark registration
    issues.
    """
    result = await search(SearchInput(query=query))
    return _dump(result)  # type: ignore[return-value]


@trademarks_mcp.tool(annotations=READ_ONLY)
async def get_tmep_section(
    section: Annotated[str, "TMEP section number (e.g. '1207', '1207.01(a)') or href"],
) -> dict:
    """Get a specific TMEP section by number.

    Returns the full text of the requested section from the Trademark
    Manual of Examining Procedure.
    """
    result = await get_section(section)
    return _dump(result)  # type: ignore[return-value]


# ---------------------------------------------------------------
# Trademark Assignment Center
# ---------------------------------------------------------------


_TM_ASSIGNMENT_AXES = (
    "assignee",
    "assignor",
    "serial_number",
    "registration_number",
    "reel_frame",
)


@trademarks_mcp.tool(annotations=READ_ONLY)
async def search_trademark_assignments(
    query: Annotated[
        str,
        "Value to search for (e.g. 'Apple Inc', '97123456', '9006/0093').",
    ],
    by: Annotated[
        str,
        "What kind of value `query` is. One of: assignee, assignor, "
        "serial_number, registration_number, reel_frame.",
    ],
    limit: Annotated[
        int,
        "Maximum records to return per request (max 1000).",
    ] = 100,
    start_row: Annotated[
        int,
        "1-based starting row for pagination.",
    ] = 1,
) -> dict:
    """Search USPTO trademark assignment recordations.

    Returns recordations with reel/frame, conveyance, assignors,
    assignees, and affected trademark properties. No auth required.
    """
    axis = by.strip().lower()
    if axis not in _TM_ASSIGNMENT_AXES:
        raise ValidationError(f"`by` must be one of {_TM_ASSIGNMENT_AXES}; got {by!r}")

    async with TrademarkAssignmentClient() as client:
        if axis == "assignee":
            records = await client.search_by_assignee(query, start_row=start_row, limit=limit)
        elif axis == "assignor":
            records = await client.search_by_assignor(query, start_row=start_row, limit=limit)
        elif axis == "serial_number":
            records = await client.search_by_serial(query, start_row=start_row, limit=limit)
        elif axis == "registration_number":
            records = await client.search_by_registration(query, start_row=start_row, limit=limit)
        else:  # reel_frame
            records = await client.search_by_reel_frame(query, start_row=start_row, limit=limit)

    return _dump_list(records)
