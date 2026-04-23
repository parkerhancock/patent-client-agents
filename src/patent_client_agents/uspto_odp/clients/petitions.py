"""USPTO ODP Petitions client."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..models import (
    PetitionDecisionFilter,
    PetitionDecisionIdentifierResponse,
    PetitionDecisionRange,
    PetitionDecisionResponse,
    PetitionDecisionSort,
)
from .base import UsptoOdpBaseClient, _prune, _serialize_model_list


class PetitionsClient(UsptoOdpBaseClient):
    """Client for USPTO ODP Petitions API.

    Provides methods to search and retrieve petition decisions.
    """

    async def search(
        self,
        *,
        q: str | None = None,
        filters: Sequence[PetitionDecisionFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[PetitionDecisionRange | dict[str, Any]] | None = None,
        sort: Sequence[PetitionDecisionSort | dict[str, Any]] | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> PetitionDecisionResponse:
        """Search petition decisions.

        Args:
            q: Lucene-style search query.
            filters: Filter objects or dicts.
            range_filters: Range filter objects or dicts.
            sort: Sort objects or dicts.
            fields: Fields to return.
            facets: Fields to aggregate.
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            PetitionDecisionResponse with matching decisions.
        """
        payload: dict[str, Any] = {}
        if q:
            payload["q"] = q
        if (filters_value := _serialize_model_list(filters)) is not None:
            payload["filters"] = filters_value
        if (ranges_value := _serialize_model_list(range_filters)) is not None:
            payload["rangeFilters"] = ranges_value
        if (sort_value := _serialize_model_list(sort)) is not None:
            payload["sort"] = sort_value
        if fields:
            payload["fields"] = list(fields)
        if facets:
            payload["facets"] = list(facets)
        if limit is not None or offset is not None:
            pagination: dict[str, Any] = {}
            if offset is not None:
                pagination["offset"] = offset
            if limit is not None:
                pagination["limit"] = limit
            payload["pagination"] = pagination

        data = await self._search_with_payload(
            "/api/v1/petition/decisions/search",
            _prune(payload),
            empty_bag_key="petitionDecisionDataBag",
            context="search petitions",
        )
        data.setdefault("petitionDecisionDataBag", [])
        return PetitionDecisionResponse(**data)

    async def download(
        self,
        *,
        q: str | None = None,
        filters: Sequence[PetitionDecisionFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[PetitionDecisionRange | dict[str, Any]] | None = None,
        sort: Sequence[PetitionDecisionSort | dict[str, Any]] | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        file_format: str | None = None,
    ) -> PetitionDecisionResponse:
        """Download petition decisions search results.

        Args:
            q: Lucene-style search query.
            filters: Filter objects or dicts.
            range_filters: Range filter objects or dicts.
            sort: Sort objects or dicts.
            fields: Fields to return.
            limit: Maximum results.
            offset: Results to skip.
            file_format: Output format ("json" or "csv").

        Returns:
            PetitionDecisionResponse with results.
        """
        payload: dict[str, Any] = {}
        if q:
            payload["q"] = q
        if (filters_value := _serialize_model_list(filters)) is not None:
            payload["filters"] = filters_value
        if (ranges_value := _serialize_model_list(range_filters)) is not None:
            payload["rangeFilters"] = ranges_value
        if (sort_value := _serialize_model_list(sort)) is not None:
            payload["sort"] = sort_value
        if fields:
            payload["fields"] = list(fields)
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
            "/api/v1/petition/decisions/search/download",
            _prune(payload),
            empty_bag_key="petitionDecisionDataBag",
            context="download petitions",
        )
        data.setdefault("petitionDecisionDataBag", [])
        return PetitionDecisionResponse(**data)

    async def get(
        self,
        petition_decision_record_identifier: str,
        *,
        include_documents: bool = False,
    ) -> PetitionDecisionIdentifierResponse:
        """Get a specific petition decision.

        Args:
            petition_decision_record_identifier: The petition decision ID.
            include_documents: Whether to include document list.

        Returns:
            PetitionDecisionIdentifierResponse with decision details.
        """
        from law_tools_core.exceptions import ValidationError

        identifier = petition_decision_record_identifier.strip()
        if not identifier:
            raise ValidationError("petition_decision_record_identifier is required")

        params = None
        if include_documents:
            params = {"includeDocuments": "true"}

        data = await self._request_json(
            "GET",
            f"/api/v1/petition/decisions/{identifier}",
            params=params,
            context=f"get petition {identifier}",
        )
        data.setdefault("petitionDecisionDataBag", [])
        return PetitionDecisionIdentifierResponse(**data)


__all__ = ["PetitionsClient"]
