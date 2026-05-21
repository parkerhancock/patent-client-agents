"""IP Australia — Trade Mark Search MCP tools.

Read-only access to the live Australian trade marks register (the
former ATMOSS surface) via IP Australia's OAuth 2.0 Trade Mark Search
API. Env-gated: registers only when ``IPAUSTRALIA_CLIENT_ID`` and
``IPAUSTRALIA_CLIENT_SECRET`` are both set.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_tool
from patent_client_agents.ip_australia_trademarks import IpAustraliaTrademarksClient

ip_australia_trademarks_mcp = FastMCP("IP Australia — Trade Marks")

_IPA_REQUIRED_ENV: list[str] = ["IPAUSTRALIA_CLIENT_ID", "IPAUSTRALIA_CLIENT_SECRET"]

_IPA_BASE = "https://production.api.ipaustralia.gov.au"
_IPA_NAME = "IP Australia"
_IPA_API_PATH = "/public/australian-trade-mark-search-api/v1"


def _ipa_trademarks_provenance(path: str) -> Any:
    """Build a Provenance for an Australian Trade Mark Search API path."""
    return make_provenance(
        source_url=f"{_IPA_BASE}{_IPA_API_PATH}{path}",
        source_name=_IPA_NAME,
    )


def _dump(obj: object) -> dict[str, Any]:
    """Serialize a Pydantic model to a dict via ``model_dump(by_alias=True)``."""
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump(by_alias=True))  # type: ignore[union-attr]  # ty: ignore[call-non-callable]
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    raise TypeError(f"_dump expected a Pydantic model or dict, got {type(obj).__name__}")


def _stub_ipa_trademark(row: dict) -> dict:
    """Lean projection of an Australian trade mark search row (§5.5)."""
    return {
        "serial_number": row.get("serialNumber"),
        "word_mark": row.get("wordMark"),
        "status": row.get("status"),
        "mark_type": row.get("markType"),
        "application_date": row.get("applicationDate"),
        "registration_date": row.get("registrationDate"),
        "nice_classes": row.get("niceClasses") or [],
    }


def _summarize_ipa_trademark(record: dict) -> str:
    """Markdown summary for a single Australian trade mark record (§7.1 step 3)."""
    serial = record.get("serialNumber") or "(no serial#)"
    word = record.get("wordMark") or "(no verbal element)"
    status = record.get("status") or "(unknown status)"
    filing = record.get("applicationDate") or "?"
    reg = record.get("registrationDate")
    head = f"**AU trade mark {serial}** — {word}"
    line = f"Status: {status}. Filed {filing}"
    if reg:
        line += f"; registered {reg}."
    else:
        line += "."
    return f"{head}\n{line}"


_IPA_TRADEMARKS_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------------------
# search_ipa_trademarks
# ---------------------------------------------------------------------------


@conditional_tool(
    ip_australia_trademarks_mcp, requires_env=_IPA_REQUIRED_ENV, annotations=READ_ONLY
)
async def search_ipa_trademarks(
    query: Annotated[
        str,
        "Free-text search string. Example: 'VEGEMITE'.",
    ],
    quick_search_type: Annotated[
        list[str] | None,
        "Filter by mark type (e.g. ['WORD'] or ['IMAGE']).",
    ] = None,
    status: Annotated[
        list[str] | None,
        "Filter by lifecycle status (e.g. ['REGISTERED', 'PENDING']).",
    ] = None,
    changed_since: Annotated[
        str | None,
        "ISO date (YYYY-MM-DD). Only marks updated on or after this date.",
    ] = None,
    sort_field: Annotated[
        str | None,
        "Optional sort field, e.g. 'NUMBER'.",
    ] = None,
    sort_direction: Annotated[
        str | None,
        "'ASCENDING' or 'DESCENDING' (defaults to ASCENDING when sort_field set).",
    ] = None,
    full: Annotated[
        bool,
        "When False (default), each hit is a lean stub: serial number, "
        "word mark, status, mark type, filing/registration dates, Nice "
        "classes. When True, every hit carries the upstream-shaped row "
        "— prefer ``get_ipa_trademark`` for one record at full depth.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Australian trade marks at IP Australia by word mark, applicant, or number.

    Returns a lean stub per hit by default. Use ``get_ipa_trademark``
    for one full record; pass ``full=True`` for upstream-shaped rows
    across the result set. ``changed_since`` makes incremental sync
    against the Australian trade marks register trivial.

    Related tools: get_ipa_trademark, search_ipa_patents, search_ipa_designs.
    """
    async with IpAustraliaTrademarksClient() as client:
        result = await client.search(
            query=query,
            quick_search_type=quick_search_type,
            status=status,
            changed_since=changed_since,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )

    dumped = _dump(result)
    rows = list(dumped.get("results") or [])
    total = dumped.get("total")
    items = rows if full else [_stub_ipa_trademark(r) for r in rows]
    shown = len(items)
    summary_total = f"{shown} of {total} hits" if total is not None else f"{shown} hits"
    more = bool(total is not None and shown < int(total))
    return ListEnvelope[dict](
        summary=f"IP Australia trade marks — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_ipa_trademarks_provenance("/search/quick"),
    )


# ---------------------------------------------------------------------------
# get_ipa_trademark
# ---------------------------------------------------------------------------


@conditional_tool(
    ip_australia_trademarks_mcp, requires_env=_IPA_REQUIRED_ENV, annotations=READ_ONLY
)
async def get_ipa_trademark(
    serial_number: Annotated[
        str | list[str],
        "Australian trade mark serial number (e.g. '1234567'), or a "
        "list for portfolio workflows. Pass a list to fetch many "
        "records concurrently; the response shape stays a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Get full Australian trade mark records by serial number.

    Accepts either a single serial number or a list (§5.4) and fans
    out internally with bounded concurrency; order matches the input.
    Returns the word mark, status, applicants, Nice classification,
    goods and services, and key prosecution dates.

    Related tools: search_ipa_trademarks, get_ipa_patent, get_ipa_design.
    """
    numbers = [serial_number] if isinstance(serial_number, str) else list(serial_number)
    if not numbers:
        raise ValidationError("get_ipa_trademark requires at least one serial_number")

    semaphore = asyncio.Semaphore(_IPA_TRADEMARKS_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IpAustraliaTrademarksClient, sn: str) -> dict:
        async with semaphore:
            record = await client.get_trademark(sn)
            return _dump(record)

    async with IpAustraliaTrademarksClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(results) == 1:
        summary = _summarize_ipa_trademark(results[0])
        path = f"/trade-mark/{numbers[0]}"
    else:
        summary = f"Fetched {len(results)} Australian trade marks: {', '.join(numbers)}."
        path = "/trade-mark"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_ipa_trademarks_provenance(path),
    )


__all__ = ["ip_australia_trademarks_mcp"]
