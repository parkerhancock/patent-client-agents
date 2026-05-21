"""Async client for the US Copyright Office Public Records API.

Queries the undocumented search API at api.publicrecords.copyright.gov.
Requires HTTP/2 — HTTP/1.1 requests are rejected by the server.
No authentication required.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_data_core import BaseAsyncClient
from mcp_data_core.exceptions import McpDataCoreError
from patent_client_agents.copyright.models import (
    Claimant,
    CopyrightRecord,
    Histogram,
    SearchMetadata,
    SearchResponse,
)

logger = logging.getLogger(__name__)


class CopyrightError(McpDataCoreError):
    """Error from the Copyright Office API."""


class CopyrightClient(BaseAsyncClient):
    """Async client for the Copyright Office Public Records search API.

    Uses the undocumented JSON API behind publicrecords.copyright.gov.
    Requires HTTP/2 (the server rejects HTTP/1.1 with a 500 error).

    Example::

        async with CopyrightClient() as client:
            response = await client.search("Mickey Mouse")
            for record in response.records:
                print(record.title_of_work, record.registration_number)
    """

    DEFAULT_BASE_URL: str = "https://api.publicrecords.copyright.gov/search_service_external"
    CACHE_NAME: str = "copyright"
    DEFAULT_TIMEOUT: float = 30.0
    HTTP2: bool = True

    def __init__(self, **kwargs: Any) -> None:
        # api.publicrecords.copyright.gov rejects requests without a
        # browser-style Accept header; httpx's default
        # ``Accept: */*`` works but specifying explicitly is safer.
        super().__init__(
            headers={
                "Accept": "application/json, text/plain, */*",
            },
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        field: str = "keyword",
        page: int = 1,
        page_size: int = 10,
        sort_order: str = "asc",
    ) -> SearchResponse:
        """Search copyright registrations and recorded documents.

        Args:
            query: Search query text.
            field: Field to search. One of ``"keyword"`` (all fields),
                ``"title"``, or ``"name"``.
            page: Page number (1-based).
            page_size: Results per page (max varies, default 10).
            sort_order: ``"asc"`` or ``"desc"``.

        Returns:
            Search response with metadata, histogram facets, and records.
        """
        if field not in ("keyword", "title", "name"):
            msg = f"Invalid field: {field!r}. Must be 'keyword', 'title', or 'name'."
            raise ValueError(msg)

        data = await self._request_json(
            "GET",
            "/simple_search_dsl",
            params={
                "query": query,
                "field_type": field,
                "page_number": str(page),
                "records_per_page": str(page_size),
                "sort_order": sort_order,
                "model": "",
            },
        )
        return self._parse_response(data)

    async def search_by_title(
        self,
        title: str,
        *,
        page: int = 1,
        page_size: int = 10,
    ) -> SearchResponse:
        """Search copyright records by work title."""
        return await self.search(title, field="title", page=page, page_size=page_size)

    async def search_by_name(
        self,
        name: str,
        *,
        page: int = 1,
        page_size: int = 10,
    ) -> SearchResponse:
        """Search copyright records by claimant/author name."""
        return await self.search(name, field="name", page=page, page_size=page_size)

    async def get_record(self, public_records_id: str) -> CopyrightRecord | None:
        """Get a specific copyright record by its public records ID.

        Since the API doesn't have a dedicated detail endpoint, this
        searches by the parsed registration number extracted from the ID.

        Args:
            public_records_id: The unique record ID
                (e.g. ``"card_catalog_CC19381945B_390000-391999.1449"``).

        Returns:
            The matching record, or None if not found.
        """
        response = await self.search(public_records_id, field="keyword", page_size=5)
        for record in response.records:
            if record.public_records_id == public_records_id:
                return record
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(data: dict[str, Any]) -> SearchResponse:
        """Parse raw API response into typed models."""
        raw_meta = data.get("metadata", {})
        raw_histogram = raw_meta.get("histogram", {}).get("filtered", {})

        metadata = SearchMetadata(
            took_ms=raw_meta.get("took_ms", 0),
            hit_count=raw_meta.get("hit_count", 0),
            hit_count_relation=raw_meta.get("hit_count_relation", "eq"),
            max_score=raw_meta.get("max_score", 0.0),
            query=raw_meta.get("query", ""),
            fields=raw_meta.get("fields", ""),
        )

        histogram = Histogram(
            type_of_record=raw_histogram.get("type_of_record", {}),
            type_of_work=raw_histogram.get("type_of_work", {}),
            registration_class=raw_histogram.get("registration_class", {}),
            registration_status=raw_histogram.get("registration_status", {}),
            system_of_origin=raw_histogram.get("system_of_origin", {}),
            recordation_item_type=raw_histogram.get("recordation_item_type", {}),
        )

        records = []
        for item in data.get("data", []):
            hit = item.get("hit", {})
            records.append(
                CopyrightRecord(
                    public_records_id=hit.get("public_records_id", ""),
                    title_of_work=hit.get("title_of_work", []),
                    registration_number=hit.get("registration_number", []),
                    copyright_number_for_display=hit.get("copyright_number_for_display", ""),
                    type_of_record=hit.get("type_of_record", ""),
                    registration_status=hit.get("registration_status", ""),
                    registration_class=hit.get("registration_class", []),
                    claimant=hit.get("claimant", []),
                    claimants=[Claimant(**c) for c in hit.get("claimants", [])],
                    publisher_name=hit.get("publisher_name", []),
                    type_of_work=hit.get("type_of_work"),
                    all_type_of_work=hit.get("all_type_of_work", []),
                    system_of_origin=hit.get("system_of_origin", ""),
                    application_date=hit.get("application_date", []),
                    first_published_date=hit.get("first_published_date", []),
                    fee_date=hit.get("fee_date", []),
                    deposit_received_date=hit.get("deposit_received_date", []),
                    representative_date=hit.get("representative_date", ""),
                    link_to_image_url=hit.get("link_to_image_url", []),
                    score=item.get("score", 0.0),
                )
            )

        return SearchResponse(
            metadata=metadata,
            histogram=histogram,
            records=records,
        )
