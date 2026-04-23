"""USPTO ODP PTAB Appeals client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..models import PtabAppealResponse
from .base import PaginationModel, SearchPayload, UsptoOdpBaseClient, _prune


class PtabAppealsClient(UsptoOdpBaseClient):
    """Client for USPTO ODP PTAB Appeals API.

    Provides methods to search and retrieve PTAB ex parte appeal decisions.
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
    ) -> PtabAppealResponse:
        """Search PTAB appeal decisions.

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
            PtabAppealResponse with matching appeal decisions.
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
            "/api/v1/patent/appeals/decisions/search",
            payload,
            empty_bag_key="patentAppealDataBag",
            context="search appeals",
        )
        data.setdefault("patentAppealDataBag", [])
        return PtabAppealResponse(**data)

    async def get_decision(self, document_identifier: str) -> PtabAppealResponse:
        """Get a single PTAB appeal decision by document identifier.

        Args:
            document_identifier: The document identifier.

        Returns:
            PtabAppealResponse with the appeal decision data.
        """
        from law_tools_core.exceptions import ValidationError

        document_identifier = document_identifier.strip()
        if not document_identifier:
            raise ValidationError("document_identifier is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/appeals/decisions/{document_identifier}",
            context=f"get appeal decision {document_identifier}",
        )
        if "patentAppealDataBag" not in data:
            data = {"count": 1, "patentAppealDataBag": [data]}
        return PtabAppealResponse(**data)

    async def get_decisions_by_number(self, appeal_number: str) -> PtabAppealResponse:
        """Get all decisions for a PTAB appeal by appeal number.

        Args:
            appeal_number: The appeal number.

        Returns:
            PtabAppealResponse with all decisions for the appeal.
        """
        from law_tools_core.exceptions import ValidationError

        appeal_number = appeal_number.strip()
        if not appeal_number:
            raise ValidationError("appeal_number is required")

        data = await self._request_json(
            "GET",
            f"/api/v1/patent/appeals/{appeal_number}/decisions",
            context=f"get decisions for appeal {appeal_number}",
        )
        data.setdefault("patentAppealDataBag", [])
        return PtabAppealResponse(**data)

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
    ) -> PtabAppealResponse:
        """Download PTAB appeal decisions search results."""
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
            "/api/v1/patent/appeals/decisions/search/download",
            _prune(payload),
            empty_bag_key="patentAppealDataBag",
            context="download appeals",
        )
        data.setdefault("patentAppealDataBag", [])
        return PtabAppealResponse(**data)


__all__ = ["PtabAppealsClient"]
