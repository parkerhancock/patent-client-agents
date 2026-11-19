"""USPTO ODP Office Action Search client (ODP release 5.0)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from mcp_data_core.exceptions import ValidationError

from ..models import OdpFilter, OdpRangeFilter, OdpSort, OfficeActionResponse
from .base import UsptoOdpBaseClient, _build_search_payload, _normalize_download_bag

_BAG = "officeActionDataBag"


class OfficeActionSearchClient(UsptoOdpBaseClient):
    """Client for the ODP Office Action Search API.

    Covers office actions in public applications and patents filed in 2001 or
    later, with full-text search over the office action body. This is the
    successor to the legacy ``/api/v1/patent/oa/`` datasets served by
    :class:`patent_client_agents.uspto_office_actions.OfficeActionClient`.
    """

    async def search(
        self,
        *,
        q: str | None = None,
        filters: Sequence[OdpFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[OdpRangeFilter | dict[str, Any]] | None = None,
        sort: Sequence[OdpSort | dict[str, Any]] | None = None,
        fields: Sequence[str] | None = None,
        facets: Sequence[str] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> OfficeActionResponse:
        """Search office actions.

        Args:
            q: Search query, e.g. ``applicationNumberText:16123456`` or free
                text matched against the office action body.
            filters: Filter objects or dicts, e.g.
                ``[{"name": "documentCode", "value": ["CTNF"]}]``.
            range_filters: Range filter objects or dicts, e.g. on
                ``submissionDate``.
            sort: Sort objects or dicts.
            fields: Fields to return. Omit for the full record. Its
                ``officeActionText`` is the first 500 characters; use
                :meth:`get_text` for the whole action.
            facets: Fields to aggregate (``documentCode``, ``rejectionTypeBag``).
            limit: Maximum results to return.
            offset: Number of results to skip.
        """
        payload = _build_search_payload(
            q=q,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            fields=fields,
            facets=facets,
            limit=limit,
            offset=offset,
        )
        data = await self._search_with_payload(
            "/api/v1/patent/office-action/search",
            payload,
            empty_bag_key=_BAG,
            context="search office actions",
        )
        data.setdefault(_BAG, [])
        return OfficeActionResponse.model_validate(data)

    async def download(
        self,
        *,
        q: str | None = None,
        filters: Sequence[OdpFilter | dict[str, Any]] | None = None,
        range_filters: Sequence[OdpRangeFilter | dict[str, Any]] | None = None,
        sort: Sequence[OdpSort | dict[str, Any]] | None = None,
        fields: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> OfficeActionResponse:
        """Download office action search results as JSON.

        The download endpoint returns a reduced record (no office action text)
        and no total count; ``count`` is the number of records returned.
        """
        payload = _build_search_payload(
            q=q,
            filters=filters,
            range_filters=range_filters,
            sort=sort,
            fields=fields,
            limit=limit,
            offset=offset,
        )
        payload["format"] = "json"
        data = await self._search_with_payload(
            "/api/v1/patent/office-action/search/download",
            payload,
            empty_bag_key=_BAG,
            context="download office actions",
        )
        return OfficeActionResponse.model_validate(
            _normalize_download_bag(data, _BAG, records_key="officeActionsData")
        )

    async def get(self, office_action_record_identifier: str) -> OfficeActionResponse:
        """Get one office action by its record identifier.

        ``officeActionText`` is the first 500 characters; use :meth:`get_text`
        for the whole action.
        """
        identifier = _require(office_action_record_identifier)
        data = await self._request_json(
            "GET",
            f"/api/v1/patent/office-action/{identifier}",
            context=f"get office action {identifier}",
        )
        data.setdefault(_BAG, [])
        return OfficeActionResponse.model_validate(data)

    async def get_text(self, office_action_record_identifier: str) -> str:
        """Get the complete plain text of one office action."""
        identifier = _require(office_action_record_identifier)
        response = await self._request(
            "GET",
            f"/api/v1/patent/office-action/{identifier}/download/officeActionText",
            context=f"get office action text {identifier}",
        )
        # Documented as a JSON object; served as text/plain (live 2026-11-19).
        if "json" in response.headers.get("content-type", ""):
            return str(response.json().get("officeActionText") or "")
        return response.text


def _require(identifier: str) -> str:
    value = identifier.strip()
    if not value:
        raise ValidationError("office_action_record_identifier is required")
    return value


__all__ = ["OfficeActionSearchClient"]
