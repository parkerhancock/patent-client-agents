"""USPTO Assignment Center API client."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from law_tools_core.base_client import BaseAsyncClient

from .models import AssignmentRecord, SearchResults

logger = logging.getLogger(__name__)


SearchAxis = Literal[
    "assignee",
    "assignor",
    "correspondent",
    "application_number",
    "patent_number",
    "publication_number",
    "reel_frame",
    "international_registration_number",
    "pct_number",
]


_SEARCH_AXIS_TO_API: dict[str, str] = {
    "assignee": "assigneeName",
    "assignor": "assignorName",
    "correspondent": "correspondentName",
    "application_number": "applicationNumber",
    "patent_number": "patentNumber",
    "publication_number": "publicationNumber",
    "reel_frame": "reelFrame",
    "international_registration_number": "internationalRegistrationNumber",
    "pct_number": "pctNumber",
}

# USPTO caps very-broad queries at this many rows. Used to set the
# ``truncated`` flag so callers can warn agents that more data exists.
_USPTO_TOTAL_CAP = 10_000

# Internal page size — pinned to the API's stated maximum so order is
# stable across pages and pagination math is straightforward.
_INTERNAL_PAGE_SIZE = 1000


class AssignmentCenterClient(BaseAsyncClient):
    """Async client for the USPTO Assignment Center API.

    The Assignment Center exposes an undocumented JSON API at
    ``assignmentcenter.uspto.gov/ipas/search/api/v2/public/search/patent``.
    This client reverse-engineers it to provide search across every
    indexed axis (assignee, assignor, correspondent, application,
    patent, publication, reel/frame, PCT, international registration)
    with conveyance-type populated, server-side execution-date
    filtering, conveyance-text contains-filtering, and pagination.

    Example::

        async with AssignmentCenterClient() as client:
            result = await client.search(query="Apple Inc", by="assignee")
            for record in result:
                print(record.reel_frame, record.conveyance, record.assignees)
            if result.truncated:
                print(f"Capped at {len(result)} of {result.total}+ — narrow query")
    """

    DEFAULT_BASE_URL = "https://assignmentcenter.uspto.gov"
    CACHE_NAME = "uspto_assignments"

    async def search(
        self,
        *,
        query: str,
        by: SearchAxis,
        exact: bool = False,
        executed_between: tuple[date, date] | None = None,
        conveyance: str | None = None,
        offset: int = 0,
        limit: int | None = None,
        timeout: float = 60.0,
    ) -> SearchResults:
        """Search USPTO assignment recordations.

        Args:
            query: The value to search for (e.g. ``"Apple Inc"`` or
                ``"16136935"``).
            by: Which axis ``query`` is searching against. One of
                ``"assignee"``, ``"assignor"``, ``"correspondent"``,
                ``"application_number"``, ``"patent_number"``,
                ``"publication_number"``, ``"reel_frame"``,
                ``"international_registration_number"``, ``"pct_number"``.
            exact: ``True`` for exact-match (``Exact``); ``False`` for
                contains-match (``Contains``). Defaults to contains since
                that's the realistic default for name searches; ignored
                for number axes (USPTO accepts either).
            executed_between: ``(start, end)`` date tuple narrowing to
                recordations whose assignor execution date falls in the
                range (inclusive). USPTO honors only this date filter;
                ``recordationDate``, ``mailDate``, and ``receiptDate`` are
                silently ignored by the server.
            conveyance: Contains-match against the conveyance text
                (e.g. ``"ASSIGNMENT"``, ``"SECURITY"``, ``"CHANGE OF NAME"``).
            offset: Number of records to skip from the start of the
                result set. Defaults to 0.
            limit: Maximum number of records to return. ``None`` (default)
                fetches everything matching, paginating internally,
                capped at USPTO's ~10k for very-broad queries.
            timeout: Per-request HTTP timeout in seconds.

        Returns:
            :class:`SearchResults` (list-like) with ``records``,
            ``total`` (USPTO's total before slicing), and ``truncated``
            (``True`` iff USPTO's ~10k cap was hit and more data exists).

        Notes:
            USPTO ignores ``sortBy`` parameters; results come back in the
            server's internal order. Order is stable across calls within
            a fixed page size (which this client pins internally to
            keep ``offset`` deterministic), but may shift slightly if
            new recordations are added between calls.
        """
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit is not None and limit < 0:
            raise ValueError("limit must be >= 0 or None")

        api_search_by = _SEARCH_AXIS_TO_API[by]
        match_type = "Exact" if exact else "Contains"

        filter_by: list[dict[str, Any]] = []
        if executed_between is not None:
            start, end = executed_between
            filter_by.append(
                {
                    "property": "",
                    "startDate": _format_yyyymmdd(start),
                    "endDate": _format_yyyymmdd(end),
                    "searchBy": "executionDate",
                }
            )
        if conveyance is not None:
            filter_by.append(
                {
                    "property": conveyance,
                    "startDate": "",
                    "endDate": "",
                    "searchBy": "conveyance",
                }
            )

        start_page = offset // _INTERNAL_PAGE_SIZE + 1
        skip_in_first_page = offset % _INTERNAL_PAGE_SIZE

        records: list[AssignmentRecord] = []
        total = 0
        page = start_page

        while True:
            payload = {
                "searchCriteria": [
                    {
                        "property": query,
                        "searchBy": api_search_by,
                        "matchType": match_type,
                        "order": 1,
                        "relation": "AND",
                    }
                ],
                "dataFilter": {
                    "filterBy": filter_by,
                    "rowsPerPage": _INTERNAL_PAGE_SIZE,
                    "currentPage": page,
                },
            }
            response = await self._request(
                "POST",
                "/ipas/search/api/v2/public/search/patent",
                json=payload,
                context="Assignment search",
                timeout=timeout,
            )
            body: Any = response.json()
            success = body.get("successResponse") if isinstance(body, dict) else None
            if not isinstance(success, dict):
                break
            total = int(success.get("totalRows") or 0)
            data = success.get("data")
            if not isinstance(data, list):
                break

            batch = [AssignmentRecord.model_validate(r) for r in data]
            if page == start_page and skip_in_first_page:
                batch = batch[skip_in_first_page:]
            records.extend(batch)

            if not batch:
                break
            if limit is not None and len(records) >= limit:
                records = records[:limit]
                break
            # ``backendPagination=False`` means the server returned everything
            # in a single response (small result sets); no further pages.
            if not success.get("backendPagination"):
                break
            # Hard stop at USPTO's 10k cap to avoid runaway loops.
            if page * _INTERNAL_PAGE_SIZE >= _USPTO_TOTAL_CAP:
                break
            page += 1

        truncated = total >= _USPTO_TOTAL_CAP
        return SearchResults(records=records, total=total, truncated=truncated)


def _format_yyyymmdd(d: date) -> str:
    """Format a date as YYYYMMDD for the USPTO date-filter API."""
    return d.strftime("%Y%m%d")


__all__ = ["AssignmentCenterClient", "SearchAxis"]
