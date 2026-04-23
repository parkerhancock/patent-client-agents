"""USPTO Assignment Center API client."""

from __future__ import annotations

import logging
from typing import Any

from law_tools_core.base_client import BaseAsyncClient

from .models import AssignmentRecord, AssignmentSearchResponse

logger = logging.getLogger(__name__)


class AssignmentCenterClient(BaseAsyncClient):
    """Async client for the USPTO Assignment Center API.

    Provides programmatic access to patent assignment records, supporting
    searches by assignee name, assignor name, patent number, application
    number, and other criteria.

    Example:
        async with AssignmentCenterClient() as client:
            # Search by assignee
            results = await client.search_by_assignee("Apple Inc", limit=100)
            for record in results:
                print(f"{record.reel_frame}: {record.assignees}")

            # Search by assignor
            results = await client.search_by_assignor("Samsung", limit=50)

            # Search by patent number
            results = await client.search_by_patent("10000000")
    """

    DEFAULT_BASE_URL = "https://assignmentcenter.uspto.gov"
    CACHE_NAME = "uspto_assignments"

    async def _search(
        self,
        criteria: list[dict[str, str]],
        *,
        start_row: int = 1,
        limit: int = 100,
        use_pagination: bool = True,
        timeout: float = 60.0,
    ) -> AssignmentSearchResponse:
        """Execute a search against the Assignment Center API.

        Args:
            criteria: List of search criteria dicts with 'property' and 'searchBy' keys.
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            use_pagination: Whether to add pagination parameters. Some search types
                (e.g., patent number) don't work well with pagination params.
            timeout: Request timeout in seconds.

        Returns:
            AssignmentSearchResponse containing matching records.
        """
        # Build search criteria
        search_criteria = list(criteria)

        # Add pagination params (some searches don't work with these)
        if use_pagination and start_row > 1:
            search_criteria.append({"property": str(start_row), "searchBy": "startRow"})
            search_criteria.append({"property": str(start_row + limit - 1), "searchBy": "endRow"})
        search_criteria.append({"property": str(min(limit, 1000)), "searchBy": "rowsNeeded"})

        payload = {"searchCriteria": search_criteria}

        http_response = await self._request(
            "POST",
            "/ipas/search/api/v2/public/patent/exportPublicPatentData",
            json=payload,
            context="Assignment search",
            timeout=timeout,
        )
        response_data: Any = http_response.json()

        # API returns a list with one element containing searchCriteria and data
        if isinstance(response_data, list) and len(response_data) > 0:
            return AssignmentSearchResponse.model_validate(response_data[0])
        return AssignmentSearchResponse.model_validate({"searchCriteria": [], "data": []})

    async def search_by_assignee(
        self,
        assignee_name: str,
        *,
        start_row: int = 1,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[AssignmentRecord]:
        """Search assignments by assignee name.

        Args:
            assignee_name: Name of the assignee (company or person receiving rights).
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            timeout: Request timeout in seconds.

        Returns:
            List of AssignmentRecord objects matching the search.
        """
        criteria = [{"property": assignee_name, "searchBy": "assigneeName"}]
        response = await self._search(criteria, start_row=start_row, limit=limit, timeout=timeout)
        return response.data

    async def search_by_assignor(
        self,
        assignor_name: str,
        *,
        start_row: int = 1,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[AssignmentRecord]:
        """Search assignments by assignor name.

        Args:
            assignor_name: Name of the assignor (company or person transferring rights).
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            timeout: Request timeout in seconds.

        Returns:
            List of AssignmentRecord objects matching the search.
        """
        criteria = [{"property": assignor_name, "searchBy": "assignorName"}]
        response = await self._search(criteria, start_row=start_row, limit=limit, timeout=timeout)
        return response.data

    async def search_by_patent(
        self,
        patent_number: str,
        *,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[AssignmentRecord]:
        """Search assignments by patent number.

        Args:
            patent_number: USPTO patent number.
            limit: Maximum number of results.
            timeout: Request timeout in seconds.

        Returns:
            List of AssignmentRecord objects for the patent.
        """
        criteria = [{"property": patent_number, "searchBy": "patentNumber"}]
        # Patent searches don't work well with pagination params
        response = await self._search(criteria, limit=limit, use_pagination=False, timeout=timeout)
        return response.data

    async def search_by_application(
        self,
        application_number: str,
        *,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[AssignmentRecord]:
        """Search assignments by application number.

        Args:
            application_number: USPTO application number.
            limit: Maximum number of results.
            timeout: Request timeout in seconds.

        Returns:
            List of AssignmentRecord objects for the application.
        """
        criteria = [{"property": application_number, "searchBy": "applicationNumber"}]
        # Application searches don't work well with pagination params
        response = await self._search(criteria, limit=limit, use_pagination=False, timeout=timeout)
        return response.data

    async def search_by_reel_frame(
        self,
        reel_frame: str,
        *,
        timeout: float = 60.0,
    ) -> list[AssignmentRecord]:
        """Search assignments by reel/frame number.

        Args:
            reel_frame: Reel/frame identifier (e.g., "52614/446").
            timeout: Request timeout in seconds.

        Returns:
            List of AssignmentRecord objects (typically one) for the reel/frame.
        """
        criteria = [{"property": reel_frame, "searchBy": "reelFrame"}]
        # Reel/frame searches don't work well with pagination params
        response = await self._search(criteria, limit=10, use_pagination=False, timeout=timeout)
        return response.data

    async def search(
        self,
        *,
        assignee_name: str | None = None,
        assignor_name: str | None = None,
        patent_number: str | None = None,
        application_number: str | None = None,
        reel_frame: str | None = None,
        correspondent_name: str | None = None,
        pct_number: str | None = None,
        publication_number: str | None = None,
        start_execution_date: str | None = None,
        end_execution_date: str | None = None,
        start_row: int = 1,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[AssignmentRecord]:
        """Search assignments with multiple criteria.

        At least one search criterion must be provided.

        Args:
            assignee_name: Filter by assignee name.
            assignor_name: Filter by assignor name.
            patent_number: Filter by patent number.
            application_number: Filter by application number.
            reel_frame: Filter by reel/frame (e.g., "52614/446").
            correspondent_name: Filter by correspondent/attorney name.
            pct_number: Filter by PCT application number.
            publication_number: Filter by publication number.
            start_execution_date: Filter by execution date start (MM/YYYY).
            end_execution_date: Filter by execution date end (MM/YYYY).
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            timeout: Request timeout in seconds.

        Returns:
            List of AssignmentRecord objects matching all criteria.

        Raises:
            ValueError: If no search criteria provided.
        """
        criteria: list[dict[str, str]] = []

        field_map = {
            "assigneeName": assignee_name,
            "assignorName": assignor_name,
            "patentNumber": patent_number,
            "applicationNumber": application_number,
            "reelFrame": reel_frame,
            "correspondentName": correspondent_name,
            "pctNumber": pct_number,
            "publicationNumber": publication_number,
            "startExecutionDate": start_execution_date,
            "endExecutionDate": end_execution_date,
        }

        for search_by, value in field_map.items():
            if value is not None:
                criteria.append({"property": value, "searchBy": search_by})

        if not criteria:
            raise ValueError("At least one search criterion must be provided")

        response = await self._search(criteria, start_row=start_row, limit=limit, timeout=timeout)
        return response.data

    async def search_all(
        self,
        *,
        assignee_name: str | None = None,
        assignor_name: str | None = None,
        batch_size: int = 1000,
        max_results: int | None = None,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> list[AssignmentRecord]:
        """Search and paginate through all matching assignments.

        Automatically handles pagination to retrieve all matching records.

        Args:
            assignee_name: Filter by assignee name.
            assignor_name: Filter by assignor name.
            batch_size: Number of records per request (max 1000).
            max_results: Maximum total results to return (None for unlimited).
            timeout: Request timeout per batch.
            **kwargs: Additional search criteria passed to search().

        Returns:
            List of all AssignmentRecord objects matching the criteria.
        """
        all_records: list[AssignmentRecord] = []
        start_row = 1
        batch_size = min(batch_size, 1000)

        while True:
            records = await self.search(
                assignee_name=assignee_name,
                assignor_name=assignor_name,
                start_row=start_row,
                limit=batch_size,
                timeout=timeout,
                **kwargs,
            )

            if not records:
                break

            all_records.extend(records)

            if max_results and len(all_records) >= max_results:
                all_records = all_records[:max_results]
                break

            if len(records) < batch_size:
                break

            start_row += batch_size

        return all_records


__all__ = ["AssignmentCenterClient"]
