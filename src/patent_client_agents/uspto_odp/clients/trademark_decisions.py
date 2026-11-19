"""USPTO ODP Trademark Decisions and Proceedings client (ODP release 5.1)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcp_data_core.exceptions import ValidationError

from ..models import OdpFilter, OdpRangeFilter, OdpSort, TrademarkDecisionResponse
from .base import UsptoOdpBaseClient, _build_search_payload

_BAG = "trademarkDecisionsDataBag"
_SEARCH = "/api/v1/trademark/decision-proceeding/search"


class TrademarkDecisionsClient(UsptoOdpBaseClient):
    """Client for the ODP Trademark Decisions and Proceedings API.

    Covers three categories, selected with a ``decisionProceedingCategory``
    filter: ``ExpungReexam`` (expungement and reexamination proceedings),
    ``PetitionsToDirector``, and ``Administrative`` (sanctions and show-cause
    orders).
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
    ) -> TrademarkDecisionResponse:
        """Search trademark decisions and proceedings.

        Args:
            q: Search query; free text is matched against the document text.
            filters: Filter objects or dicts, e.g.
                ``[{"name": "decisionProceedingCategory", "value": ["ExpungReexam"]}]``.
            range_filters: Range filter objects or dicts, e.g. on
                ``decisionActionDate``.
            sort: Sort objects or dicts. The default is newest
                ``decisionActionDate`` first.
            fields: Fields to return.
            facets: Fields to aggregate.
            limit: Maximum results to return.
            offset: Number of results to skip.
        """
        return await self._post_search(
            _SEARCH,
            "search trademark decisions",
            _build_search_payload(
                q=q,
                filters=filters,
                range_filters=range_filters,
                sort=sort,
                fields=fields,
                facets=facets,
                limit=limit,
                offset=offset,
            ),
        )

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
    ) -> TrademarkDecisionResponse:
        """Download trademark decision search results as JSON."""
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
        return await self._post_search(
            f"{_SEARCH}/download", "download trademark decisions", payload
        )

    async def get(self, document_identifier: str) -> TrademarkDecisionResponse:
        """Get one trademark decision document by its document identifier."""
        identifier = document_identifier.strip()
        if not identifier:
            raise ValidationError("document_identifier is required")
        data = await self._request_json(
            "GET",
            f"{_SEARCH}/{identifier}",
            context=f"get trademark decision {identifier}",
        )
        return TrademarkDecisionResponse.model_validate(_normalize_bag(data))

    async def download_document_pdf(
        self,
        file_download_uri: str,
        *,
        output_path: str | Path | None = None,
    ) -> bytes:
        """Download a decision PDF.

        Args:
            file_download_uri: The record's ``fileDownloadURI``. Only
                ``Administrative`` records carry one (live 2026-11-19); the
                other categories link to TSDR through ``documentURI``.
            output_path: Optional path to save the PDF. Parent directories
                are created if needed.
        """
        uri = file_download_uri.strip()
        if not uri:
            raise ValidationError("file_download_uri is required")
        response = await self._request(
            "GET",
            uri,
            context="download trademark decision document",
            timeout=120.0,
        )
        content = response.content
        if output_path is not None:
            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(content)
        return content

    async def _post_search(
        self, endpoint: str, context: str, payload: dict[str, Any]
    ) -> TrademarkDecisionResponse:
        data = await self._search_with_payload(
            endpoint, payload, empty_bag_key=_BAG, context=context
        )
        return TrademarkDecisionResponse.model_validate(_normalize_bag(data))


def _normalize_bag(data: dict[str, Any]) -> dict[str, Any]:
    """Make the bag a list: the get-by-identifier endpoint returns one object."""
    bag = data.get(_BAG)
    if isinstance(bag, dict):
        data[_BAG] = [bag]
    elif bag is None:
        data[_BAG] = []
    return data


__all__ = ["TrademarkDecisionsClient"]
