"""MCP tools for the Japan Intellectual Property High Court case lists."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.japan_ip_high_court import (
    WORKBOOK_URL,
    JapanIpHighCourtClient,
    find_case,
    normalize_case_number,
)
from patent_client_agents.japan_ip_high_court.models import JapanIpHighCourtCaseList

japan_ip_high_court_mcp = FastMCP("Japan Intellectual Property High Court")

_SOURCE_NAME = "Japan Intellectual Property High Court — Patent and Utility-Model Case Lists"


def _provenance(case_list: JapanIpHighCourtCaseList) -> Any:
    as_of = case_list.as_of_date.isoformat() if case_list.as_of_date else "date not published"
    return make_provenance(
        source_url=WORKBOOK_URL,
        source_name=_SOURCE_NAME,
        as_of_status=f"official weekly workbook as of {as_of}; party names are not published",
    )


def _terms(query: str | list[str] | None) -> list[str]:
    if query is None:
        return []
    values = [query] if isinstance(query, str) else query
    terms = [normalize_case_number(value) for value in values if value.strip()]
    if not terms:
        raise ValidationError("query must contain at least one non-empty term")
    return terms


def _date_filter(value: str | None, *, field: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must use YYYY-MM-DD format") from exc


def _searchable(record: dict[str, Any]) -> str:
    return normalize_case_number(
        " ".join(str(value) for value in record.values() if value is not None)
    )


@japan_ip_high_court_mcp.tool(annotations=READ_ONLY)
async def search_japan_ip_high_court_cases(
    query: Annotated[
        str | list[str] | None,
        "Optional case number, patent/utility-model/application number, proceeding type, division, or disposition; a list is OR-matched.",
    ] = None,
    case_status: Annotated[
        Literal["pending", "closed", "all"],
        "Workbook sheet to search. Defaults to currently pending cases.",
    ] = "pending",
    date_from: Annotated[
        str | None,
        "Optional YYYY-MM-DD lower bound for scheduled judgment (pending) or termination (closed).",
    ] = None,
    date_to: Annotated[
        str | None,
        "Optional YYYY-MM-DD upper bound for scheduled judgment (pending) or termination (closed).",
    ] = None,
    limit: Annotated[int, "Maximum results (1-250)."] = 100,
) -> ListEnvelope[dict]:
    """Search the official Japanese IP High Court patent and utility-model case lists.

    The workbook covers pending and recently closed suits seeking cancellation
    of JPO patent or utility-model decisions. It is useful for monitoring a
    known Japanese patent/application number or court case number. It is not a
    general infringement docket and does not publish party names, pleadings,
    or docket entries.

    Related tool: get_japan_ip_high_court_case.
    """
    if not 1 <= limit <= 250:
        raise ValidationError("limit must be between 1 and 250")
    start = _date_filter(date_from, field="date_from")
    end = _date_filter(date_to, field="date_to")
    if start and end and start > end:
        raise ValidationError("date_from must not be after date_to")
    search_terms = _terms(query)

    async with JapanIpHighCourtClient() as client:
        case_list = await client.list_cases()
    records = [case.model_dump(mode="json") for case in case_list.cases]
    if case_status != "all":
        records = [record for record in records if record["case_status"] == case_status]
    if search_terms:
        records = [
            record
            for record in records
            if any(term in _searchable(record) for term in search_terms)
        ]

    def relevant_date(record: dict[str, Any]) -> date | None:
        value = record.get("scheduled_judgment_date") or record.get("termination_date")
        return date.fromisoformat(value) if value else None

    if start:
        records = [
            record
            for record in records
            if (record_date := relevant_date(record)) is not None and record_date >= start
        ]
    if end:
        records = [
            record
            for record in records
            if (record_date := relevant_date(record)) is not None and record_date <= end
        ]
    if case_status == "closed":
        records.sort(
            key=lambda record: (record.get("termination_date") or "", record["case_number"]),
            reverse=True,
        )
    else:
        records.sort(
            key=lambda record: (
                not bool(record.get("scheduled_judgment_date") or record.get("termination_date")),
                record.get("scheduled_judgment_date") or record.get("termination_date") or "",
                record["case_number"],
            )
        )
    total_matches = len(records)
    items = records[:limit]
    as_of = case_list.as_of_date.isoformat() if case_list.as_of_date else "unknown date"
    return ListEnvelope[dict](
        summary=(
            f"Japan IP High Court {case_status} patent and utility-model case list: "
            f"{len(items)} returned "
            f"from {total_matches} match(es), workbook as of {as_of}. "
            "The source does not publish party names and is not a general infringement docket."
        ),
        items=items,
        more_available=total_matches > len(items),
        next_cursor=None,
        provenance=_provenance(case_list),
    )


@japan_ip_high_court_mcp.tool(annotations=READ_ONLY)
async def get_japan_ip_high_court_case(
    case_number: Annotated[
        str | list[str],
        "Exact Japanese case number or list, e.g. '令和7年（行ケ）第10011号'.",
    ],
    case_status: Annotated[
        Literal["pending", "closed", "all"],
        "Limit lookup to one workbook sheet or search both.",
    ] = "all",
) -> ListEnvelope[dict]:
    """Get exact official Japanese IP High Court case-list records.

    Width variants in parentheses and whitespace are normalized. Related
    tool: search_japan_ip_high_court_cases.
    """
    values = [case_number] if isinstance(case_number, str) else case_number
    if not values:
        raise ValidationError("case_number list must not be empty")
    if len(values) > 25:
        raise ValidationError("case_number accepts at most 25 values per call")

    async with JapanIpHighCourtClient() as client:
        case_list = await client.list_cases()
    records = [
        find_case(case_list, value, case_status=case_status).model_dump(mode="json")
        for value in values
    ]
    return ListEnvelope[dict](
        summary=f"Fetched {len(records)} official Japan IP High Court case-list record(s).",
        items=records,
        more_available=False,
        next_cursor=None,
        provenance=_provenance(case_list),
    )


__all__ = ["japan_ip_high_court_mcp"]
