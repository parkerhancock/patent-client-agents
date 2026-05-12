"""USPTO Trademark Assignment Center API client."""

from __future__ import annotations

from typing import Any

from law_tools_core.base_client import BaseAsyncClient

from .models import TrademarkAssignmentRecord, TrademarkAssignmentSearchResponse


class TrademarkAssignmentClient(BaseAsyncClient):
    """Async client for the USPTO Trademark Assignment Center API.

    Provides programmatic access to trademark assignment records, supporting
    searches by assignee name, assignor name, serial number, registration
    number, and other criteria.

    Example:
        async with TrademarkAssignmentClient() as client:
            # Search by assignee
            results = await client.search_by_assignee("Apple Inc", limit=100)
            for record in results:
                print(f"{record.reel_frame}: {record.assignees}")

            # Search by assignor
            results = await client.search_by_assignor("Samsung", limit=50)

            # Search by serial number
            results = await client.search_by_serial("97123456")
    """

    DEFAULT_BASE_URL = "https://assignmentcenter.uspto.gov"
    CACHE_NAME = "uspto_trademark_assignments"

    async def _search(
        self,
        criteria: list[dict[str, str]],
        *,
        start_row: int = 1,
        limit: int = 100,
        use_pagination: bool = True,
        timeout: float = 60.0,
    ) -> TrademarkAssignmentSearchResponse:
        """Execute a search against the Trademark Assignment Center API.

        Args:
            criteria: List of search criteria dicts with 'property' and 'searchBy' keys.
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            use_pagination: Whether to add pagination parameters.
            timeout: Request timeout in seconds.

        Returns:
            TrademarkAssignmentSearchResponse containing matching records.
        """
        search_criteria = list(criteria)

        # Add pagination params
        if use_pagination and start_row > 1:
            search_criteria.append({"property": str(start_row), "searchBy": "startRow"})
            search_criteria.append({"property": str(start_row + limit - 1), "searchBy": "endRow"})
        search_criteria.append({"property": str(min(limit, 1000)), "searchBy": "rowsNeeded"})

        payload = {"searchCriteria": search_criteria}

        http_response = await self._request(
            "POST",
            "/ipas/search/api/v2/public/trademark/exportTradeMarkData",
            json=payload,
            context="Trademark assignment search",
            timeout=timeout,
        )
        response_data: Any = http_response.json()

        # API returns a list with one element containing searchCriteria and data
        if isinstance(response_data, list) and len(response_data) > 0:
            return TrademarkAssignmentSearchResponse.model_validate(response_data[0])
        return TrademarkAssignmentSearchResponse.model_validate({"searchCriteria": [], "data": []})

    async def search_by_assignee(
        self,
        assignee_name: str,
        *,
        start_row: int = 1,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[TrademarkAssignmentRecord]:
        """Search assignments by assignee name.

        Args:
            assignee_name: Name of the assignee (company or person receiving rights).
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            timeout: Request timeout in seconds.

        Returns:
            List of TrademarkAssignmentRecord objects matching the search.
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
    ) -> list[TrademarkAssignmentRecord]:
        """Search assignments by assignor name.

        Args:
            assignor_name: Name of the assignor (company or person transferring rights).
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            timeout: Request timeout in seconds.

        Returns:
            List of TrademarkAssignmentRecord objects matching the search.
        """
        criteria = [{"property": assignor_name, "searchBy": "assignorName"}]
        response = await self._search(criteria, start_row=start_row, limit=limit, timeout=timeout)
        return response.data

    async def search_by_serial(
        self,
        serial_number: str,
        *,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[TrademarkAssignmentRecord]:
        """Search assignments by trademark serial number.

        Args:
            serial_number: USPTO trademark serial number.
            limit: Maximum number of results.
            timeout: Request timeout in seconds.

        Returns:
            List of TrademarkAssignmentRecord objects for the serial number.
        """
        criteria = [{"property": serial_number, "searchBy": "serialNumber"}]
        response = await self._search(criteria, limit=limit, use_pagination=False, timeout=timeout)
        return response.data

    async def search_by_registration(
        self,
        registration_number: str,
        *,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[TrademarkAssignmentRecord]:
        """Search assignments by trademark registration number.

        Args:
            registration_number: USPTO trademark registration number.
            limit: Maximum number of results.
            timeout: Request timeout in seconds.

        Returns:
            List of TrademarkAssignmentRecord objects for the registration.
        """
        criteria = [{"property": registration_number, "searchBy": "registrationNumber"}]
        response = await self._search(criteria, limit=limit, use_pagination=False, timeout=timeout)
        return response.data

    async def search_by_reel_frame(
        self,
        reel_frame: str,
        *,
        timeout: float = 60.0,
    ) -> list[TrademarkAssignmentRecord]:
        """Search assignments by reel/frame number.

        Args:
            reel_frame: Reel/frame identifier (e.g., "9006/0093").
            timeout: Request timeout in seconds.

        Returns:
            List of TrademarkAssignmentRecord objects (typically one) for the reel/frame.
        """
        criteria = [{"property": reel_frame, "searchBy": "reelFrame"}]
        response = await self._search(criteria, limit=10, use_pagination=False, timeout=timeout)
        return response.data

    async def search(
        self,
        *,
        assignee_name: str | None = None,
        assignor_name: str | None = None,
        serial_number: str | None = None,
        registration_number: str | None = None,
        reel_frame: str | None = None,
        correspondent_name: str | None = None,
        domestic_representative: str | None = None,
        international_registration: str | None = None,
        start_execution_date: str | None = None,
        end_execution_date: str | None = None,
        start_row: int = 1,
        limit: int = 100,
        timeout: float = 60.0,
    ) -> list[TrademarkAssignmentRecord]:
        """Search assignments with multiple criteria.

        At least one search criterion must be provided.

        Args:
            assignee_name: Filter by assignee name.
            assignor_name: Filter by assignor name.
            serial_number: Filter by trademark serial number.
            registration_number: Filter by trademark registration number.
            reel_frame: Filter by reel/frame (e.g., "9006/0093").
            correspondent_name: Filter by correspondent/attorney name.
            domestic_representative: Filter by domestic representative.
            international_registration: Filter by international registration number.
            start_execution_date: Filter by execution date start (MM/YYYY).
            end_execution_date: Filter by execution date end (MM/YYYY).
            start_row: Starting row for pagination (1-based).
            limit: Maximum number of results (max 1000 per request).
            timeout: Request timeout in seconds.

        Returns:
            List of TrademarkAssignmentRecord objects matching all criteria.

        Raises:
            ValueError: If no search criteria provided.
        """
        criteria: list[dict[str, str]] = []

        field_map = {
            "assigneeName": assignee_name,
            "assignorName": assignor_name,
            "serialNumber": serial_number,
            "registrationNumber": registration_number,
            "reelFrame": reel_frame,
            "correspondentName": correspondent_name,
            "domesticRepresentative": domestic_representative,
            "internationalRegistration": international_registration,
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
    ) -> list[TrademarkAssignmentRecord]:
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
            List of all TrademarkAssignmentRecord objects matching the criteria.
        """
        all_records: list[TrademarkAssignmentRecord] = []
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


__all__ = ["TrademarkAssignmentClient"]
