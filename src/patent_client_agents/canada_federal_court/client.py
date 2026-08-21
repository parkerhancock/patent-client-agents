"""Async client for Canada's public Federal Court Court Files service."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import httpx

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import NotFoundError

from .models import (
    CourtDivision,
    DocketStatus,
    FederalCourtCase,
    FederalCourtCaseRecord,
    FederalCourtCaseSearchResponse,
    FederalCourtDocketEntry,
    FederalCourtDocketResponse,
    FederalCourtIntellectualProperty,
    FederalCourtParty,
    FederalCourtRelatedCase,
)

DEFAULT_BASE_URL = "https://www-u.fct-cf.gc.ca"
COURT_FILES_URL = f"{DEFAULT_BASE_URL}/en/court-files-and-decisions/court-files"

_BROWSER_HEADERS = {
    "Accept": "application/json",
    "Referer": COURT_FILES_URL,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36"
    ),
}

_CLOSED_MARKERS = (
    "notice of discontinuance",
    "proceeding is discontinued",
    "action is discontinued",
    "application is discontinued",
    "proceeding is dismissed",
    "action is dismissed",
    "application is dismissed",
    "final decision",
    "final judgment",
)
_PENDING_MARKERS = (
    "trial scheduled",
    "hearing scheduled",
    "case management conference scheduled",
    "case management conference to be held",
    "case management conference will be held",
    "seeking first case management conference",
    "will proceed to trial",
)


def assess_docket_status(entries: list[FederalCourtDocketEntry]) -> DocketStatus:
    """Infer a cautious status from explicit language in recent docket entries."""
    if not entries:
        return DocketStatus(
            assessment="unknown",
            basis="The Registry returned no recorded entries and no official status field.",
        )

    recent = sorted(entries, key=lambda entry: entry.entry_number, reverse=True)[:10]
    combined = "\n".join(
        " ".join(
            part for part in (entry.summary, entry.registry_notes, entry.command_phrase_en) if part
        ).lower()
        for entry in recent
    )
    closed_marker = next((marker for marker in _CLOSED_MARKERS if marker in combined), None)
    if closed_marker:
        return DocketStatus(
            assessment="likely_closed",
            basis=f"A recent recorded entry contains the terminal phrase {closed_marker!r}.",
        )

    latest_text = " ".join(
        part
        for part in (recent[0].summary, recent[0].registry_notes, recent[0].command_phrase_en)
        if part
    ).lower()
    pending_marker = next((marker for marker in _PENDING_MARKERS if marker in latest_text), None)
    if pending_marker:
        return DocketStatus(
            assessment="likely_pending",
            basis=f"The latest recorded entry contains the prospective phrase {pending_marker!r}.",
        )

    return DocketStatus(
        assessment="unknown",
        basis="The Court does not publish an official status field and recent entries are not dispositive.",
    )


class CanadaFederalCourtClient(BaseAsyncClient):
    """Read-only client for official Federal Court case-file JSON endpoints."""

    DEFAULT_BASE_URL = DEFAULT_BASE_URL
    CACHE_NAME = "canada_federal_court"
    DEFAULT_TIMEOUT = 60.0

    def __init__(self, *, client: httpx.AsyncClient | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("ttl_seconds", 900)
        super().__init__(client=client, headers=_BROWSER_HEADERS, **kwargs)

    async def _get_data(self, path: str, *, params: dict[str, Any]) -> tuple[int, list[dict]]:
        payload = await self._request_json("GET", path, params=params, context=path)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise ValueError(f"Unexpected Federal Court response shape from {path}")
        return int(payload.get("Count", len(payload["data"]))), payload["data"]

    async def search_party_cases(
        self,
        party_name: str,
        *,
        division: CourtDivision = "t",
        filed_from: date | None = None,
        filed_to: date | None = None,
        patent_only: bool = True,
        limit: int = 25,
    ) -> FederalCourtCaseSearchResponse:
        """Search case files by party/corporation name, newest filings first."""
        query = party_name.strip()
        if len(query) < 2:
            raise ValueError("party_name must contain at least 2 characters")
        if (filed_from is None) != (filed_to is None):
            raise ValueError("filed_from and filed_to must be supplied together")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        path = "/CourtFilesAndDecisions/ProceedingsQueriesPartyInfo"
        params: dict[str, Any] = {"division": division, "name": query.replace(".", "xxyxx")}
        if filed_from and filed_to:
            if filed_from > filed_to:
                raise ValueError("filed_from must be on or before filed_to")
            path += "Dates"
            params.update(
                {
                    "from": filed_from.strftime("%m-%d-%Y"),
                    "to": filed_to.strftime("%m-%d-%Y"),
                }
            )

        upstream_count, rows = await self._get_data(path, params=params)
        cases = [FederalCourtCase.model_validate(row) for row in rows]
        if patent_only:
            cases = [case for case in cases if case.is_patent_case]
        cases.sort(key=lambda case: case.filed_date or date.min, reverse=True)
        filtered_count = len(cases)
        return FederalCourtCaseSearchResponse(
            query=query,
            upstream_count=upstream_count,
            filtered_count=filtered_count,
            cases=cases[:limit],
        )

    async def get_case(
        self,
        court_number: str,
        *,
        division: CourtDivision = "t",
    ) -> FederalCourtCaseRecord:
        """Fetch case metadata, parties/counsel, IP references, and related cases."""
        number = court_number.strip().upper()
        params = {"division": division, "courtnumber": number}
        (_, case_rows), (_, party_rows), (_, ip_rows), (_, related_rows) = await asyncio.gather(
            self._get_data("/CourtFilesAndDecisions/proceedingQueriesAddInfo", params=params),
            self._get_data(
                "/CourtFilesAndDecisions/PublicPartiesListInfo",
                params={"courtnumber": number},
            ),
            self._get_data("/CourtFilesAndDecisions/PartyInfoIntlProp", params=params),
            self._get_data(
                "/CourtFilesAndDecisions/RelatedListInfo",
                params={"courtnumber": number},
            ),
        )
        if not case_rows:
            raise NotFoundError(f"Federal Court file not found: {number}")
        return FederalCourtCaseRecord(
            case=FederalCourtCase.model_validate(case_rows[0]),
            parties=[FederalCourtParty.model_validate(row) for row in party_rows],
            intellectual_property=[
                FederalCourtIntellectualProperty.model_validate(row) for row in ip_rows
            ],
            related_cases=[FederalCourtRelatedCase.model_validate(row) for row in related_rows],
        )

    async def list_docket_entries(
        self,
        court_number: str,
        *,
        division: CourtDivision = "t",
        limit: int = 100,
    ) -> FederalCourtDocketResponse:
        """Fetch recorded docket entries and a conservative inferred status."""
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        number = court_number.strip().upper()
        total_count, rows = await self._get_data(
            "/CourtFilesAndDecisions/proceedingQueriesRE",
            params={"division": division, "courtnumber": number},
        )
        entries = [FederalCourtDocketEntry.model_validate(row) for row in rows]
        for entry in entries:
            if entry.can_download and not entry.is_confidential and entry.document_id:
                entry.download_url = (
                    f"{self.base_url}/CourtFilesAndDecisions/downloadFileFromAlfresco"
                    f"?foremostNum={entry.document_id}"
                )
        entries.sort(key=lambda entry: entry.entry_number, reverse=True)
        return FederalCourtDocketResponse(
            court_number=number,
            total_count=total_count,
            status=assess_docket_status(entries),
            entries=entries[:limit],
        )


__all__ = [
    "COURT_FILES_URL",
    "CanadaFederalCourtClient",
    "assess_docket_status",
]
