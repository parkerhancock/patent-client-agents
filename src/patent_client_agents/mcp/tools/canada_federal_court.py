"""MCP tools for Canada's official Federal Court case-file and docket service."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Annotated, Any, cast
from urllib.parse import quote_plus

from fastmcp import FastMCP

from mcp_data_core.envelope import ListEnvelope, make_provenance
from mcp_data_core.exceptions import McpDataCoreError, ValidationError
from mcp_data_core.mcp.annotations import READ_ONLY
from patent_client_agents.canada_federal_court import CanadaFederalCourtClient, CourtDivision

canada_federal_court_mcp = FastMCP("Canada Federal Court")

_SOURCE_NAME = "Federal Court of Canada — Court Files"
_BASE_URL = "https://www-u.fct-cf.gc.ca"
_COURT_FILES_PATH = "/en/court-files-and-decisions/court-files"
_FANOUT_CONCURRENCY = 5
_UNKNOWN_STATUS = {
    "assessment": "unknown",
    "basis": "The docket status lookup failed; case metadata remains available.",
    "inferred": True,
}


def _provenance(path: str = _COURT_FILES_PATH, *, status: str) -> Any:
    return make_provenance(
        source_url=f"{_BASE_URL}{path}",
        source_name=_SOURCE_NAME,
        as_of_status=status,
    )


def _parse_date(value: str | None, *, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} must be ISO date YYYY-MM-DD; got {value!r}") from exc


def _case_stub(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "court_number": record.get("court_number"),
        "style_of_cause": record.get("style_of_cause"),
        "nature_en": record.get("nature_en"),
        "filed_date": record.get("filed_date"),
        "city_en": record.get("city_en"),
        "parties": record.get("parties") or [],
        "status_assessment": record.get("status_assessment"),
    }


@canada_federal_court_mcp.tool(annotations=READ_ONLY)
async def search_canada_federal_court_patent_cases(
    party_name: Annotated[
        str,
        "Party or corporation name; searches both sides of Federal Court case files.",
    ],
    filed_from: Annotated[
        str | None, "Inclusive filing date, YYYY-MM-DD; requires filed_to."
    ] = None,
    filed_to: Annotated[
        str | None, "Inclusive filing date, YYYY-MM-DD; requires filed_from."
    ] = None,
    division: Annotated[
        str,
        "Court selector: 't' Federal Court, 'a' Federal Court of Appeal, 'b' both.",
    ] = "t",
    limit: Annotated[int, "Maximum results after patent filtering (1-100)."] = 25,
    patent_only: Annotated[
        bool,
        "Keep explicit patent/brevet nature labels only. False also returns ambiguous 'IP - Other' cases.",
    ] = True,
    assess_status: Annotated[
        bool,
        "Fetch each returned docket to infer likely_pending/likely_closed/unknown.",
    ] = True,
    full: Annotated[
        bool,
        "False returns lean case stubs; True returns all official search-result fields.",
    ] = False,
) -> ListEnvelope[dict]:
    """Find Canadian Federal Court patent cases involving a party, including pending-case clues.

    Searches the official Court Files service, not CanLII's published-decision
    collection. Results include both plaintiff/applicant and
    defendant/respondent matches. The Court does not publish an official
    open/closed field, so any status is explicitly labeled as a conservative
    docket-text inference; ``unknown`` is common and should not be treated as
    no pending litigation.

    Related tools: get_canada_federal_court_case,
    list_canada_federal_court_docket_entries, search_canlii_ip_cases.
    """
    if division not in {"t", "a", "b"}:
        raise ValidationError("division must be 't', 'a', or 'b'")
    resolved_division = cast("CourtDivision", division)
    if (filed_from is None) != (filed_to is None):
        raise ValidationError("filed_from and filed_to must be supplied together")
    start = _parse_date(filed_from, field="filed_from")
    end = _parse_date(filed_to, field="filed_to")

    async with CanadaFederalCourtClient() as client:
        response = await client.search_party_cases(
            party_name,
            division=resolved_division,
            filed_from=start,
            filed_to=end,
            patent_only=patent_only,
            limit=limit,
        )
        records = [case.model_dump(mode="json") for case in response.cases]

        if assess_status and records:
            semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)

            async def fetch_status(record: dict[str, Any]) -> None:
                try:
                    async with semaphore:
                        docket = await client.list_docket_entries(
                            str(record["court_number"]),
                            division=resolved_division,
                            limit=10,  # type: ignore[arg-type]
                        )
                    record["status_assessment"] = docket.status.model_dump()
                except (McpDataCoreError, ValueError):
                    record["status_assessment"] = dict(_UNKNOWN_STATUS)

            await asyncio.gather(*(fetch_status(record) for record in records))
        else:
            for record in records:
                record["status_assessment"] = {
                    "assessment": "unknown",
                    "basis": "Status assessment was not requested; the search response has no status field.",
                    "inferred": True,
                }

    items = records if full else [_case_stub(record) for record in records]
    status_label = "inferred per item" if assess_status else "not reported by upstream"
    more = response.filtered_count > len(items)
    result_label = "patent-filtered hits" if patent_only else "IP-related hits"
    return ListEnvelope[dict](
        summary=(
            f"Canada Federal Court patent cases for `{party_name}`: {len(items)} returned "
            f"from {response.filtered_count} {result_label} "
            f"({response.upstream_count} party-name hits before filtering). "
            "Party side/role and pending status are not official search fields."
        ),
        items=items,
        more_available=more,
        next_cursor=None,
        provenance=_provenance(status=status_label),
    )


@canada_federal_court_mcp.tool(annotations=READ_ONLY)
async def get_canada_federal_court_case(
    court_number: Annotated[
        str | list[str],
        "Federal Court file number or list, e.g. 'T-2962-24' or ['T-2962-24', 'T-675-24'].",
    ],
    division: Annotated[
        str,
        "Court selector: 't' Federal Court, 'a' Federal Court of Appeal, 'b' both.",
    ] = "t",
) -> ListEnvelope[dict]:
    """Get official Canadian Federal Court case metadata, parties/counsel, and patent references.

    The exact-file record includes the Registry's public party/counsel list,
    intellectual-property names and numbers, and related cases. It also
    includes a conservative status assessment from the recorded docket.

    Related tools: search_canada_federal_court_patent_cases,
    list_canada_federal_court_docket_entries.
    """
    if division not in {"t", "a", "b"}:
        raise ValidationError("division must be 't', 'a', or 'b'")
    resolved_division = cast("CourtDivision", division)
    numbers = [court_number] if isinstance(court_number, str) else court_number
    if not numbers:
        raise ValidationError("court_number list must not be empty")
    if len(numbers) > 25:
        raise ValidationError("court_number accepts at most 25 files per call")

    semaphore = asyncio.Semaphore(_FANOUT_CONCURRENCY)
    async with CanadaFederalCourtClient() as client:

        async def fetch(number: str) -> dict[str, Any]:
            async with semaphore:
                record, docket = await asyncio.gather(
                    client.get_case(number, division=resolved_division),
                    client.list_docket_entries(number, division=resolved_division, limit=10),
                )
            item = record.model_dump(mode="json")
            item["status_assessment"] = docket.status.model_dump()
            return item

        items = await asyncio.gather(*(fetch(number) for number in numbers))

    statuses = sorted({str(item["status_assessment"]["assessment"]) for item in items})
    return ListEnvelope[dict](
        summary=f"Fetched {len(items)} Canadian Federal Court file(s): {', '.join(numbers)}.",
        items=list(items),
        more_available=False,
        next_cursor=None,
        provenance=_provenance(status=", ".join(statuses)),
    )


@canada_federal_court_mcp.tool(annotations=READ_ONLY)
async def list_canada_federal_court_docket_entries(
    court_number: Annotated[str, "Federal Court file number, e.g. 'T-2962-24'."],
    division: Annotated[
        str,
        "Court selector: 't' Federal Court, 'a' Federal Court of Appeal, 'b' both.",
    ] = "t",
    limit: Annotated[int, "Maximum recorded entries, newest first (1-500)."] = 100,
    full: Annotated[
        bool,
        "False omits internal document/command fields; True returns the complete normalized entry.",
    ] = False,
) -> ListEnvelope[dict]:
    """List the official recorded docket entries for a Canadian Federal Court file.

    Entries are live Registry snapshots and may include downloadable public
    documents for eligible post-September-2022 IP cases. The envelope's
    status is inferred from explicit docket language and is not an official
    Court status.

    Related tools: get_canada_federal_court_case,
    search_canada_federal_court_patent_cases.
    """
    if division not in {"t", "a", "b"}:
        raise ValidationError("division must be 't', 'a', or 'b'")
    resolved_division = cast("CourtDivision", division)
    async with CanadaFederalCourtClient() as client:
        docket = await client.list_docket_entries(
            court_number,
            division=resolved_division,
            limit=limit,  # type: ignore[arg-type]
        )

    records = [entry.model_dump(mode="json") for entry in docket.entries]
    if not full:
        records = [
            {
                "entry_number": record.get("entry_number"),
                "document_date": record.get("document_date"),
                "office_en": record.get("office_en"),
                "summary": record.get("summary"),
                "document_number": record.get("document_number"),
                "download_url": record.get("download_url"),
            }
            for record in records
        ]
    encoded_number = quote_plus(court_number.strip().upper())
    return ListEnvelope[dict](
        summary=(
            f"Canada Federal Court {docket.court_number}: {len(records)} recorded entries. "
            f"Status assessment: {docket.status.assessment} ({docket.status.basis})"
        ),
        items=records,
        more_available=docket.total_count > len(docket.entries),
        next_cursor=None,
        provenance=_provenance(
            f"{_COURT_FILES_PATH}?courtNumber={encoded_number}",
            status=docket.status.assessment,
        ),
    )


__all__ = ["canada_federal_court_mcp"]
