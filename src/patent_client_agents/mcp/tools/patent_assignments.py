"""USPTO Patent Assignment MCP tools.

The trademark-assignment half of the original combined ``assignments``
module lives with ``law-tools``; this file carries only the patent-side
tools backed by ``patent_client_agents.uspto_assignments``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any, cast

from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, make_provenance
from law_tools_core.exceptions import ValidationError
from law_tools_core.mcp.annotations import READ_ONLY
from patent_client_agents.uspto_assignments import AssignmentCenterClient
from patent_client_agents.uspto_assignments.client import _SEARCH_AXIS_TO_API

patent_assignments_mcp = FastMCP("PatentAssignments")


# ──────────────────────────────────────────────────────────────────────
# Envelope helpers — Assignment Center is a distinct USPTO endpoint
# from ODP (assignment-api.uspto.gov vs api.uspto.gov), so it gets its
# own provenance helper. See CONNECTOR_STANDARDS.md §5.9 + uspto.py for
# the canonical template.
# ──────────────────────────────────────────────────────────────────────

_ASSIGNMENT_BASE = "https://assignment-api.uspto.gov"
_ASSIGNMENT_NAME = "USPTO Patent Assignment Center"


def _patent_assignment_provenance(path: str) -> Any:
    return make_provenance(
        source_url=f"{_ASSIGNMENT_BASE}{path}",
        source_name=_ASSIGNMENT_NAME,
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


def _stub_patent_assignment(record: Any) -> dict:
    """Lean projection (§5.5) of a patent assignment recordation."""
    data = record.model_dump() if hasattr(record, "model_dump") else dict(record)
    assignors = data.get("assignors") or []
    properties = data.get("properties") or []
    first_assignor = (
        assignors[0].get("assignor_name") if assignors and isinstance(assignors[0], dict) else None
    )
    assignees = data.get("assignees") or []
    first_assignee = assignees[0] if assignees else None
    first_property = properties[0] if properties and isinstance(properties[0], dict) else {}
    reel_frame = (
        f"{data.get('reel_number')}/{data.get('frame_number')}"
        if data.get("reel_number") is not None and data.get("frame_number") is not None
        else None
    )
    return {
        "reel_frame": reel_frame,
        "conveyance": data.get("conveyance"),
        "assignor": first_assignor,
        "assignee": first_assignee,
        "assignor_execution_date": data.get("assignor_execution_date"),
        "number_of_properties": data.get("number_of_properties"),
        "application_number": first_property.get("application_number"),
        "patent_number": first_property.get("patent_number"),
        "publication_number": first_property.get("publication_number"),
    }


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
    full: Annotated[
        bool,
        "When False (the default), each hit is a lean stub: reel/frame, "
        "conveyance, first assignor, first assignee, execution date, "
        "number of properties, plus the lead property's application/"
        "patent/publication number. When True, every hit is the full "
        "Assignment Center record (all properties, all assignors, "
        "correspondent, etc.).",
    ] = False,
) -> ListEnvelope[dict]:
    """Search USPTO patent assignment recordations by assignee, assignor, conveyance, or patent identifier.

    Returns recordations with reel/frame, conveyance type, assignors,
    assignees, correspondent, and affected properties. Lean by default
    (§5.5); use ``full=True`` for the upstream record per hit. To pull
    assignments for a specific application, use ``get_patent_assignment``;
    for the underlying prosecution context, use ``get_application`` or
    ``get_patent``.

    Related tools: get_patent_assignment, get_application, get_patent.
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
            by=by,  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
            exact=exact,
            executed_between=executed_between,
            conveyance=conveyance,
            offset=offset,
            limit=limit,
        )

    raw_records = list(result.records)
    items = (
        [_dump(r) for r in raw_records]
        if full
        else [_stub_patent_assignment(r) for r in raw_records]
    )
    shown = len(items)
    total = result.total
    more = bool(result.truncated or (total and shown + offset < int(total)))
    summary_total = f"{shown} of {total}" if total else f"{shown}"
    summary = f"USPTO patent assignments (by {by}) — `{query}`: {summary_total} hits"
    if result.truncated:
        summary += f" (USPTO capped at ~{shown}; narrow to access more)"
    summary += "."

    return ListEnvelope[dict](
        summary=summary,
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_patent_assignment_provenance(
            "/PatentAssignmentSearch/assignment/search/searchByPropertyMethod"
        ),
    )
