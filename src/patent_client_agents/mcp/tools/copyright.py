"""U.S. Copyright Office MCP tools."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.copyright import CopyrightClient

copyright_mcp = FastMCP("Copyright")


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers — U.S. Copyright Office Public Records.
# Source name mirrors coverage/sources.yaml (US/USCO/Registrations).
# ──────────────────────────────────────────────────────────────────────

_USCO_BASE = "https://api.publicrecords.copyright.gov"
_USCO_NAME = "U.S. Copyright Office — Public Records"


def _uscopyright_provenance(path: str) -> Any:
    """Build a Provenance pointing at ``{base}{path}``."""
    return make_provenance(
        source_url=f"{_USCO_BASE}{path}",
        source_name=_USCO_NAME,
    )


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


def _first(values: object) -> str | None:
    """Return the first element of a list-valued field, or None."""
    if isinstance(values, list) and values:
        first = values[0]
        return first if isinstance(first, str) else None
    if isinstance(values, str) and values:
        return values
    return None


def _stub_copyright(record: dict) -> dict:
    """Lean projection of a Copyright Public Records hit (§5.5).

    Picks 8 scalar fields agents need for triage. Use ``full=True`` on
    ``search_copyright`` to get every upstream field per row.
    """
    return {
        "public_records_id": record.get("public_records_id"),
        "title": _first(record.get("title_of_work")),
        "registration_number": record.get("copyright_number_for_display")
        or _first(record.get("registration_number")),
        "registration_class": _first(record.get("registration_class")),
        "type_of_record": record.get("type_of_record"),
        "type_of_work": record.get("type_of_work"),
        "claimant": _first(record.get("claimant")),
        "representative_date": record.get("representative_date") or None,
    }


def _summarize_record(record: dict) -> str:
    """One-line Markdown summary of a single copyright record."""
    prid = record.get("public_records_id") or "(no id)"
    title = _first(record.get("title_of_work")) or "(no title)"
    reg = record.get("copyright_number_for_display") or _first(record.get("registration_number"))
    claimant = _first(record.get("claimant")) or "(no claimant)"
    status = record.get("registration_status") or "(unknown status)"
    type_of_record = record.get("type_of_record") or "record"
    head = f"**U.S. Copyright {type_of_record} {prid}** — {title}"
    line = f"Claimant: {claimant}. Status: {status}"
    if reg:
        line += f"; registration {reg}."
    else:
        line += "."
    return f"{head}\n{line}"


_GET_RECORD_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------


@copyright_mcp.tool(annotations=READ_ONLY)
async def search_copyright(
    query: Annotated[
        str,
        "Search query: a title, a claimant/author name, a registration "
        "number (e.g. 'TX 1234567'), or any keyword.",
    ],
    field: Annotated[
        str,
        "Which field to search. 'keyword' (default) — all fields; "
        "'title' — work title only; 'name' — claimant/author only.",
    ] = "keyword",
    page: Annotated[int, "Page number (1-based)."] = 1,
    page_size: Annotated[int, "Results per page (default 10, max ~50)."] = 10,
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: public records "
        "id, title, registration number, registration class, type of "
        "record, type of work, first claimant, and representative date. "
        "When True, each hit carries the full upstream record (every "
        "title/claimant/date/class list, plus relevance score).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search U.S. Copyright Office registrations and recorded documents by keyword.

    Covers post-1978 Voyager registrations, digitized card-catalog
    records, and recorded documents (transfers, assignments, licenses).
    Returns lean stubs by default. Pass the ``public_records_id`` from
    any hit to ``get_copyright_record`` to fetch the full record.

    Related tools: get_copyright_record.
    """
    async with CopyrightClient() as client:
        response = await client.search(query, field=field, page=page, page_size=page_size)

    raw_results = [_dump(r) for r in response.records]
    items = raw_results if full else [_stub_copyright(r) for r in raw_results]  # type: ignore[arg-type]

    metadata = _dump(response.metadata)
    total = metadata.get("hit_count") if isinstance(metadata, dict) else None  # type: ignore[union-attr]
    shown = len(items)
    more = bool(total and (page * page_size) < int(total))
    summary_total = f"{shown} of {total} hits" if total else f"{shown} hits"
    return ListEnvelope[dict](
        summary=f"U.S. Copyright Office — `{query}` (by {field}): {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_uscopyright_provenance("/search_service_external/simple_search_dsl"),
    )


# ---------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------


@copyright_mcp.tool(annotations=READ_ONLY)
async def get_copyright_record(
    public_records_id: Annotated[
        str | list[str],
        "Public Records identifier — the opaque ID returned by "
        "``search_copyright`` in each hit's ``public_records_id`` "
        "field. NOT a registration number (like 'TX 1234567'); to look "
        "up a registration number, call ``search_copyright`` with the "
        "number as the query. Examples: 'voyager_12345', "
        "'card_catalog_CC19381945B_390000-391999.1449', or a list of "
        "such IDs for portfolio workflows.",
    ],
) -> ListEnvelope[dict]:
    """Get one or more U.S. Copyright Office records by their Public Records identifier.

    Accepts either a single identifier or a list (per §5.4); the response
    is always a ListEnvelope so the shape is stable. Returns the full
    registration or recordation record (titles, claimants, dates, class,
    work type, deposit dates, card-catalog image URLs). Bounded
    concurrent fan-out internally.

    Related tools: search_copyright.
    """
    ids = [public_records_id] if isinstance(public_records_id, str) else list(public_records_id)

    semaphore = asyncio.Semaphore(_GET_RECORD_FANOUT_CONCURRENCY)

    async def _fetch_one(client: CopyrightClient, prid: str) -> dict | None:
        async with semaphore:
            record = await client.get_record(prid)
            return _dump(record) if record is not None else None  # type: ignore[return-value]

    async with CopyrightClient() as client:
        fetched = await asyncio.gather(*[_fetch_one(client, n) for n in ids])

    items: list[dict] = [r for r in fetched if r is not None]
    not_found = [n for n, r in zip(ids, fetched, strict=True) if r is None]

    if len(ids) == 1 and items:
        summary = _summarize_record(items[0])
    elif len(ids) == 1:
        summary = f"U.S. Copyright record {ids[0]} — not found."
    else:
        head = f"Fetched {len(items)} of {len(ids)} U.S. Copyright records."
        summary = head + (f" Not found: {', '.join(not_found)}." if not_found else "")

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        provenance=_uscopyright_provenance("/search_service_external/simple_search_dsl"),
    )
