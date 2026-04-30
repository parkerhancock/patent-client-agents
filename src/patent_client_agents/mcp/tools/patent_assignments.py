"""USPTO Patent Assignment MCP tools.

The trademark-assignment half of the original combined ``assignments``
module lives with ``law-tools``; this file carries only the patent-side
tools backed by ``patent_client_agents.uspto_assignments``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from fastmcp import FastMCP

from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.uspto_assignments import AssignmentCenterClient
from patent_client_agents.uspto_assignments.client import _SEARCH_AXIS_TO_API

patent_assignments_mcp = FastMCP("PatentAssignments")


def _dump(obj: object) -> object:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore[union-attr]
    return obj


def _parse_date(value: str | None, *, field: str) -> date | None:
    if value is None:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValidationError(
        f"{field} must be a date in YYYY-MM-DD, YYYYMMDD, or MM/DD/YYYY format; got {value!r}"
    )


_VALID_AXES = tuple(_SEARCH_AXIS_TO_API.keys())


@patent_assignments_mcp.tool(annotations=READ_ONLY)
async def search_patent_assignments(
    query: Annotated[
        str,
        "Value to search for (e.g. 'Apple Inc', '16136935', '52614/446').",
    ],
    by: Annotated[
        str,
        "What kind of value `query` is. One of: assignee, assignor, "
        "correspondent, application_number, patent_number, "
        "publication_number, reel_frame, international_registration_number, "
        "pct_number.",
    ],
    exact: Annotated[
        bool,
        "True for exact match, False (default) for contains match. Ignored "
        "for number axes, where USPTO accepts either.",
    ] = False,
    executed_after: Annotated[
        str | None,
        "Narrow to recordations whose assignor execution date is on or "
        "after this date (YYYY-MM-DD). Pair with ``executed_before`` for a "
        "range. Note: only assignor execution date is honored by USPTO; "
        "recordation, mail, and receipt date filters are ignored.",
    ] = None,
    executed_before: Annotated[
        str | None,
        "Narrow to recordations whose assignor execution date is on or "
        "before this date (YYYY-MM-DD).",
    ] = None,
    conveyance: Annotated[
        str | None,
        "Contains-match against conveyance text (e.g. 'ASSIGNMENT', 'SECURITY', 'CHANGE OF NAME').",
    ] = None,
    offset: Annotated[
        int,
        "Number of records to skip from the start of the result set.",
    ] = 0,
    limit: Annotated[
        int | None,
        "Maximum records to return. None (default) fetches everything "
        "matching, capped at USPTO's ~10,000 for very-broad queries.",
    ] = None,
) -> dict:
    """Search USPTO patent assignment recordations.

    Returns recordations with reel/frame, conveyance type, assignors,
    assignees, correspondent, and affected properties. Each call hits a
    single endpoint with full conveyance data populated.
    """
    if by not in _VALID_AXES:
        raise ValidationError(f"`by` must be one of {_VALID_AXES}; got {by!r}")
    after = _parse_date(executed_after, field="executed_after")
    before = _parse_date(executed_before, field="executed_before")
    if (after is None) != (before is None):
        raise ValidationError(
            "executed_after and executed_before must be set together (or both omitted)"
        )
    executed_between = (after, before) if after and before else None

    async with AssignmentCenterClient() as client:
        result = await client.search(
            query=query,
            by=by,  # type: ignore[arg-type]
            exact=exact,
            executed_between=executed_between,
            conveyance=conveyance,
            offset=offset,
            limit=limit,
        )

    payload: dict = {
        "records": [_dump(r) for r in result.records],
        "total": result.total,
        "truncated": result.truncated,
    }
    if result.truncated:
        payload["warning"] = (
            f"USPTO capped this query at {len(result)} of {result.total}+ matching "
            f"records. Narrow your query (use a more specific value, add "
            f"executed_after/before, or filter conveyance) to access records "
            f"beyond the cap."
        )
    return payload
