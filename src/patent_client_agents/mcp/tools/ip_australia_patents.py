"""IP Australia — Patent Search MCP tools.

Read-only access to the live Australian patent register via IP
Australia's OAuth 2.0 Patent Search API. Env-gated: registers only
when ``IPAUSTRALIA_CLIENT_ID`` and ``IPAUSTRALIA_CLIENT_SECRET`` are
both set.

Set ``IPAUSTRALIA_ENV=sandbox`` to target ``test.api.ipaustralia.gov.au``.
The default is production.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from mcp_data_core.mcp.conditional import conditional_tool
from patent_client_agents.ip_australia_patents import IpAustraliaPatentsClient

ip_australia_patents_mcp = FastMCP("IP Australia — Patents")

_IPA_REQUIRED_ENV: list[str] = ["IPAUSTRALIA_CLIENT_ID", "IPAUSTRALIA_CLIENT_SECRET"]

# ──────────────────────────────────────────────────────────────────────
# Envelope helpers (CONNECTOR_STANDARDS.md §5.9). IP Australia's three
# OAuth APIs share a common host but distinct base paths; one
# provenance helper per data type keeps source URLs accurate.
# ──────────────────────────────────────────────────────────────────────

_IPA_BASE = "https://production.api.ipaustralia.gov.au"
_IPA_NAME = "IP Australia"
_IPA_API_PATH = "/public/australian-patent-search-api/v1"


def _ipa_patents_provenance(path: str) -> Any:
    """Build a Provenance for an Australian Patent Search API path."""
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


def _stub_ipa_patent(row: dict) -> dict:
    """Lean projection of an Australian patent search row (§5.5)."""
    return {
        "application_number": row.get("applicationNumber"),
        "patent_number": row.get("patentNumber"),
        "title": row.get("title"),
        "status": row.get("status"),
        "application_date": row.get("applicationDate"),
        "grant_date": row.get("grantDate"),
        "ipc_classifications": row.get("ipcClassifications") or [],
    }


def _summarize_ipa_patent(record: dict) -> str:
    """Markdown summary for a single Australian patent record (§7.1 step 3)."""
    appno = record.get("applicationNumber") or "(no appl#)"
    pat_no = record.get("patentNumber")
    title = record.get("title") or "(no title)"
    status = record.get("status") or "(unknown status)"
    filing = record.get("applicationDate") or "?"
    grant = record.get("grantDate")
    head = f"**AU patent application {appno}** — {title}"
    line = f"Status: {status}. Filed {filing}"
    if pat_no and grant:
        line += f"; granted as AU {pat_no} on {grant}."
    elif pat_no:
        line += f"; granted as AU {pat_no}."
    else:
        line += "."
    return f"{head}\n{line}"


_IPA_PATENTS_FANOUT_CONCURRENCY = 5


# ---------------------------------------------------------------------------
# search_ipa_patents
# ---------------------------------------------------------------------------


@conditional_tool(ip_australia_patents_mcp, requires_env=_IPA_REQUIRED_ENV, annotations=READ_ONLY)
async def search_ipa_patents(
    query: Annotated[
        str,
        "Free-text search string. Matches title, abstract, applicant, and "
        "patent / application number. Example: 'blockchain authentication'.",
    ],
    status: Annotated[
        list[str] | None,
        "Filter by patent lifecycle status (e.g. ['GRANTED', 'ACCEPTED']).",
    ] = None,
    changed_since: Annotated[
        str | None,
        "ISO date (YYYY-MM-DD). Only patents updated on or after this date.",
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
        "When False (default), each hit is a lean stub: application "
        "number, patent number, title, status, filing/grant dates, IPC "
        "classifications. When True, every hit carries the upstream-"
        "shaped row — prefer ``get_ipa_patent`` for one record at full "
        "depth.",
    ] = False,
) -> ListEnvelope[dict]:
    """Search Australian patents at IP Australia by title, applicant, or number.

    Returns a lean stub per hit by default so result sets stay small.
    Use ``get_ipa_patent`` for one full record; pass ``full=True`` for
    upstream-shaped rows across the result set. ``changed_since`` makes
    incremental sync against the AusPat register trivial.

    Related tools: get_ipa_patent, search_ipa_trademarks, search_ipa_designs.
    """
    async with IpAustraliaPatentsClient() as client:
        result = await client.search(
            query=query,
            status=status,
            changed_since=changed_since,
            sort_field=sort_field,
            sort_direction=sort_direction,
        )

    dumped = _dump(result)
    rows = list(dumped.get("results") or [])
    total = dumped.get("total")
    items = rows if full else [_stub_ipa_patent(r) for r in rows]
    shown = len(items)
    summary_total = f"{shown} of {total} hits" if total is not None else f"{shown} hits"
    more = bool(total is not None and shown < int(total))
    return ListEnvelope[dict](
        summary=f"IP Australia patents — `{query}`: {summary_total}.",
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_ipa_patents_provenance("/search/quick"),
    )


# ---------------------------------------------------------------------------
# get_ipa_patent
# ---------------------------------------------------------------------------


@conditional_tool(ip_australia_patents_mcp, requires_env=_IPA_REQUIRED_ENV, annotations=READ_ONLY)
async def get_ipa_patent(
    application_number: Annotated[
        str | list[str],
        "Australian patent / application number (digits-only string, "
        "e.g. '2019204205'), or a list for portfolio workflows. "
        "Pass a list to fetch many records concurrently; the response "
        "shape stays a ListEnvelope.",
    ],
) -> ListEnvelope[dict]:
    """Get full Australian patent records by application number.

    Accepts either a single application number or a list (§5.4) and
    fans out internally with bounded concurrency; order matches the
    input. Returns bibliographic data, status, applicants, inventors,
    IPC classifications, and priority claims.

    Related tools: search_ipa_patents, get_ipa_trademark, get_ipa_design.
    """
    numbers = (
        [application_number] if isinstance(application_number, str) else list(application_number)
    )
    if not numbers:
        raise ValidationError("get_ipa_patent requires at least one application_number")

    semaphore = asyncio.Semaphore(_IPA_PATENTS_FANOUT_CONCURRENCY)

    async def _fetch_one(client: IpAustraliaPatentsClient, num: str) -> dict:
        async with semaphore:
            record = await client.get_patent(num)
            return _dump(record)

    async with IpAustraliaPatentsClient() as client:
        results = await asyncio.gather(*[_fetch_one(client, n) for n in numbers])

    if len(results) == 1:
        summary = _summarize_ipa_patent(results[0])
        path = f"/patent/{numbers[0]}"
    else:
        summary = f"Fetched {len(results)} Australian patents: {', '.join(numbers)}."
        path = "/patent"

    return ListEnvelope[dict](
        summary=summary,
        items=results,
        provenance=_ipa_patents_provenance(path),
    )


__all__ = ["ip_australia_patents_mcp"]
