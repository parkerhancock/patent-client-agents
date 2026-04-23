"""USPTO ODP PTAB Interferences client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..models import PtabInterferenceResponse
from .base import PaginationModel, SearchPayload, UsptoOdpBaseClient, _prune


class PtabInterferencesClient(UsptoOdpBaseClient):
    """Client for USPTO ODP PTAB Interferences API.

    Provides methods to search and retrieve PTAB interference decisions.
    """

    async def search(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> PtabInterferenceResponse:
        """Search PTAB interference decisions.

        Args:
            query: Lucene-style search query.
            fields: Fields to return.
            facets: Fields to aggregate.
            filters: Filter expressions.
            range_filters: Range filter expressions.
            sort: Sort expression.
            limit: Maximum results.
            offset: Results to skip.

        Returns:
            PtabInterferenceResponse with matching interference decisions.
        """
        payload = SearchPayload(
            q=query,
            fields=list(fields) if fields else None,
            facets=list(facets) if facets else None,
            filters=list(filters) if filters else None,
            range_filters=list(range_filters) if range_filters else None,
            sort=[sort] if sort else None,
            pagination=PaginationModel(offset=offset, limit=limit),
        ).model_dump_pruned()

        data = await self._search_with_payload(
            "/api/v1/patent/interferences/decisions/search",
            payload,
            empty_bag_key="patentInterferenceDataBag",
            context="search interferences",
        )
        data.setdefault("patentInterferenceDataBag", [])
        return PtabInterferenceResponse(**data)

    async def get_decision(self, document_identifier: str) -> PtabInterferenceResponse:
        """Get a single PTAB interference decision by document identifier.

        Args:
            document_identifier: The document identifier.

        Returns:
            PtabInterferenceResponse with the interference decision data.
        """
        from law_tools_core.exceptions import ValidationError

        document_identifier = document_identifier.strip()
        if not document_identifier:
            raise ValidationError("document_identifier is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/interferences/decisions/{document_identifier}",
            context=f"get interference decision {document_identifier}",
        )
        if "patentInterferenceDataBag" not in data:
            data = {"count": 1, "patentInterferenceDataBag": [data]}
        return PtabInterferenceResponse(**data)

    async def get_decisions_by_number(self, interference_number: str) -> PtabInterferenceResponse:
        """Get all decisions for a PTAB interference by interference number.

        Args:
            interference_number: The interference number.

        Returns:
            PtabInterferenceResponse with all decisions for the interference.
        """
        from law_tools_core.exceptions import ValidationError

        interference_number = interference_number.strip()
        if not interference_number:
            raise ValidationError("interference_number is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/interferences/{interference_number}/decisions",
            context=f"get decisions for interference {interference_number}",
        )
        data.setdefault("patentInterferenceDataBag", [])
        return PtabInterferenceResponse(**data)

    async def download(
        self,
        *,
        query: str | None = None,
        fields: Sequence[str] | None = None,
        filters: Sequence[str] | None = None,
        range_filters: Sequence[str] | None = None,
        sort: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PtabInterferenceResponse:
        """Download PTAB interference decisions search results."""
        payload: dict[str, Any] = {}
        if query:
            payload["q"] = query
        if fields:
            payload["fields"] = list(fields)
        if filters:
            payload["filters"] = list(filters)
        if range_filters:
            payload["rangeFilters"] = list(range_filters)
        if sort:
            payload["sort"] = sort
        if limit is not None or offset is not None:
            pagination: dict[str, Any] = {}
            if offset is not None:
                pagination["offset"] = offset
            if limit is not None:
                pagination["limit"] = limit
            payload["pagination"] = pagination
        if file_format:
            payload["format"] = file_format

        data = await self._search_with_payload(
            "/api/v1/patent/interferences/decisions/search/download",
            _prune(payload),
            empty_bag_key="patentInterferenceDataBag",
            context="download interferences",
        )
        data.setdefault("patentInterferenceDataBag", [])
        return PtabInterferenceResponse(**data)


__all__ = ["PtabInterferencesClient"]
