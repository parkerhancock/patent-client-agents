"""IP Australia — Designs Search MCP tools.

Read-only access to the live Australian designs register via IP
Australia's OAuth 2.0 Designs Search API. Env-gated: registers only
when ``IPAUSTRALIA_CLIENT_ID`` and ``IPAUSTRALIA_CLIENT_SECRET`` are
both set.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_tool
from patent_client_agents.ip_australia_designs import IpAustraliaDesignsClient

ip_australia_designs_mcp = FastMCP("IP Australia — Designs")

_IPA_REQUIRED_ENV: list[str] = ["IPAUSTRALIA_CLIENT_ID", "IPAUSTRALIA_CLIENT_SECRET"]

_IPA_BASE = "https://production.api.ipaustralia.gov.au"
_IPA_NAME = "IP Australia"
_IPA_API_PATH = "/public/australian-design-search-api/v1"


def _ipa_designs_provenance(path: str) -> Any:
    """Build a Provenance for an Australian Designs Search API path."""
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


def _stub_ipa_design(row: dict) -> dict:
    """Lean projection of an Australian design search row (§5.5)."""
    return {
        "design_number": row.get("designNumber"),
        "application_number": row.get("applicationNumber"),
        "title": row.get("title"),
        "status": row.get("status"),
        "application_date": row.get("applicationDate"),
        "registration_date": row.get("registrationDate"),
        "locarno_classes": row.get("locarnoClasses") or [],
    }


def _summarize_ipa_design(record: dict) -> str:
    """Markdown summary for a single Australian design record (§7.1 step 3)."""
    dno = record.get("designNumber") or "(no design#)"
    title = record.get("title") or "(no title)"
    status = record.get("status") or "(unknown status)"
    filing = record.get("applicationDate") or "?"
    reg = record.get("registrationDate")
    locarno = record.get("locarnoClasses") or []
    locarno_str = ", ".join(str(c) for c in locarno) if locarno else "(no Locarno classes)"
    head = f"**AU design {dno}** — {title}"
    line = f"Status: {status}. Filed {filing}"
    if reg:
        line += f"; registered {reg}"
    line += f". Locarno: {locarno_str}."
    return f"{head}\n{line}"


_IPA_DESIGNS_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------------------
# search_ipa_designs
# ---------------------------------------------------------------------------


@conditional_tool(ip_australia_designs_mcp, requires_env=_IPA_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipa_designs(
    query: Annotated[
        str,
        "Free-text search string. Example: 'clothing'.",
    ],
    classification: Annotated[
        list[str] | None,
        "Filter by Locarno classification codes (e.g. ['0202c'] — clothing accessories).",
    ] = None,
    status: Annotated[
        list[str] | None,
        "Filter by lifecycle status (e.g. ['REGISTERED']).",
    ] = None,
    changed_since: Annotated[
        str | None,
        "ISO date (YYYY-MM-DD). Only designs updated on or after this date.",
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
        "When False (default), each hit is a lean stub: design number, "
        "application number, title, status, filing/registration dates, "
        "Locarno classes. When True, every hit carries the upstream-"
        "shaped row — prefer ``get_ipa_design`` for one record at full "
        "depth.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Australian registered designs at IP Australia by title, applicant, or number.

    Returns a lean stub per hit by default. Use ``get_ipa_design`` for
    one full record; pass ``full=True`` for upstream-shaped rows
    across the result set. ``changed_since`` enables incremental sync.

    Related tools: get_ipa_design, search_ipa_patents, search_ipa_trademarks.
    """
    async with IpAustraliaDesignsClient() as client:
        result = await client.search(
            query=query,
            classification=classification,
            status=status,
            changed_since=changed_since,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )

    dumped = _dump(result)
    rows = list(dumped.get("results") or [])
    total = dumped.get("total")
    items = rows if full else [_stub_ipa_design(r) for r in rows]
    shown = len(items)
    summary_total = f"{shown} of {total} hits" if total is not None else f"{shown} hits"
    more = bool(total is not None and shown < int(total))
    return ListEnvelope[dict](
        summary=f"IP Australia designs — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_ipa_designs_provenance("/search/quick"),
    )


# ---------------------------------------------------------------------------
# get_ipa_design
# ---------------------------------------------------------------------------


@conditional_tool(ip_australia_designs_mcp, requires_env=_IPA_REQUIRED_ENV, annotations=READ_ONLY)
async def get_ipa_design(
    application_number: Annotated[
        str | list[str],
        "Australian design number (the canonical Designs Search "
        "identifier; e.g. '202410123'), or a list for portfolio "
        "workflows. Pass a list to fetch many records concurrently; the "
        "response shape stays a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Get full Australian registered design records by design number.

    Accepts either a single design number or a list (§5.4) and fans
    out internally with bounded concurrency; order matches the input.
    Returns title, status, owners, Locarno classification, priority
    claims, and key prosecution dates.

    Related tools: search_ipa_designs, get_ipa_patent, get_ipa_trademark.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_ipa_design requires at least one application_number")

    semaphore = asyncio.Semaphore(_IPA_DESIGNS_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IpAustraliaDesignsClient, num: str) -> dict:
        async with semaphore:
            record = await client.get_design(num)
            return _dump(record)

    async with IpAustraliaDesignsClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(results) == 1:
        summary = _summarize_ipa_design(results[0])
        path = f"/design/{numbers[0]}"
    else:
        summary = f"Fetched {len(results)} Australian designs: {', '.join(numbers)}."
        path = "/design"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_ipa_designs_provenance(path),
    )


__all__ = ["ip_australia_designs_mcp"]
