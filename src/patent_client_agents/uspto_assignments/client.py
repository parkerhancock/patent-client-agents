"""USPTO Assignment Center API client."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Literal

from mcp_data_core.base_client import BaseAsyncClient
from mcp_data_core.exceptions import NotFoundError

from .models import AssignmentDetail, AssignmentRecord, SearchResults

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
    ``assignmentcenter.uspto.gov/ipas/search/api/v3/public/search/patent``
    (v2 was retired by USPTO's July 24, 2026 Assignment Center update).
    This client reverse-engineers it to provide search across every
    indexed axis (assignee, assignor, correspondent, application,
    patent, publication, reel/frame, PCT, international registration)
    with conveyance-type populated, server-side execution-date
    filtering, conveyance-text contains-filtering, and pagination.

    v3 behavior changes from v2:

    - Search hits no longer include ``properties`` (and report
      ``noOfProperties=0``); use :meth:`details` to fetch the affected
      properties for a recordation.
    - Server-side conveyance filtering is gone (the v3 server returns
      zero rows for it), so ``conveyance`` is matched client-side here.
    - ``totalRows`` for broad name queries is unreliable: the server
      caps its scan (observed at 10,000) and may silently omit older
      recordations for high-volume names. Number-axis searches
      (application, patent, reel/frame, ...) remain exact.

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
                Matched client-side since USPTO's v3 API dropped the
                server-side filter; when set, ``total`` reports the
                matched count (a lower bound if ``limit`` stopped
                paging early) rather than USPTO's row count.
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
        # USPTO's v3 API dropped server-side conveyance filtering (a
        # ``searchBy: "conveyance"`` filterBy entry now returns zero
        # rows), so conveyance is matched client-side over fetched
        # pages. Offset then applies to the filtered stream, which
        # forces paging from page 1.
        conveyance_needle = conveyance.upper() if conveyance is not None else None
        if conveyance_needle is None:
            start_page = offset // _INTERNAL_PAGE_SIZE + 1
            skip_in_first_page = offset % _INTERNAL_PAGE_SIZE
            target = limit
        else:
            start_page = 1
            skip_in_first_page = 0
            target = None if limit is None else offset + limit

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
                "/ipas/search/api/v3/public/search/patent",
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
            server_batch_empty = not batch
            if conveyance_needle is not None:
                batch = [
                    r for r in batch if r.conveyance and conveyance_needle in r.conveyance.upper()
                ]
            if page == start_page and skip_in_first_page:
                batch = batch[skip_in_first_page:]
            records.extend(batch)

            if server_batch_empty:
                break
            if target is not None and len(records) >= target:
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
        if conveyance_needle is not None:
            # Server total counts unfiltered rows; report what matched
            # instead, then apply offset to the filtered stream.
            total = len(records)
            records = records[offset:]
        if limit is not None:
            records = records[:limit]
        return SearchResults(records=records, total=total, truncated=truncated)

    async def details(
        self,
        reel_number: int | str,
        frame_number: int | str,
        *,
        timeout: float = 60.0,
    ) -> AssignmentDetail:
        """Fetch the full recordation detail for one reel/frame.

        This is the only v3 surface that returns the affected
        properties — USPTO's July 2026 update removed them from search
        hits. Frame numbers may be padded or unpadded (``"0327"`` or
        ``327``).

        Returns:
            :class:`AssignmentDetail` with typed ``properties`` plus
            the raw ``assignment`` dict (assignee and correspondent
            addresses, recordation/mail/receipt dates, pageCount,
            imageURL, ...).

        Raises:
            NotFoundError: If no recordation exists at that reel/frame.
        """
        payload = {
            "reelNumber": str(reel_number),
            "frameNumber": str(frame_number),
            "searchBy": "reelFrame",
            "dataFilter": {"filterBy": [], "rowsPerPage": 10, "currentPage": 1},
        }
        response = await self._request(
            "POST",
            "/ipas/search/api/v3/public/search/patent",
            json=payload,
            context="Assignment detail",
            timeout=timeout,
        )
        body: Any = response.json()
        success = body.get("successResponse") if isinstance(body, dict) else None
        data = success.get("data") if isinstance(success, dict) else None
        if not isinstance(data, dict) or not data.get("assignment"):
            raise NotFoundError(
                f"No assignment recordation found at reel/frame {reel_number}/{frame_number}"
            )
        return AssignmentDetail.model_validate(data)


def _format_yyyymmdd(d: date) -> str:
    """Format a date as YYYYMMDD for the USPTO date-filter API."""
    return d.strftime("%Y%m%d")


__all__ = ["AssignmentCenterClient", "SearchAxis"]
