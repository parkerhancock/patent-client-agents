"""Async client for the ILPO Israel trade mark feed on data.gov.il.

The Israeli Ministry of Justice (ILPO) publishes the national trade
mark register through the ``data.gov.il`` open-data portal. The portal
speaks the standard CKAN action API, so the catalog lookup and download
resolution paths mirror IP Australia's ``ip_australia_bulk`` client.

This is the **catalog + download** surface (Shape E in
CONNECTOR_STANDARDS.md §7.2). It exposes:

* :meth:`IlpoTmClient.get_dataset` — fetch CKAN package metadata,
  including the list of downloadable resources.
* :meth:`IlpoTmClient.download_resource` — stream one resource's bytes.

Default dataset id is ``"trade-marks"`` — the canonical ILPO TM
register. Pass a different id to enumerate a non-default dataset.

Verified 2026-05-16: data.gov.il is hosted at https://data.gov.il/ and
the CKAN action API is rooted at ``/api/3/action/``.
"""

from __future__ import annotations

from typing import Any

from mcp_data_core import BaseAsyncClient

from .models import IlpoTmDataset

CKAN_HOST = "https://data.gov.il"
_PACKAGE_PATH = "/api/3/action/package_show"
_DEFAULT_DATASET_ID = "trade-marks"


class IlpoTmClient(BaseAsyncClient):
    """Async client for the data.gov.il CKAN catalog (ILPO TM dataset).

    No auth required for ``package_show`` reads. Downloads stream
    directly from the resource ``url`` reported by CKAN.
    """

    CACHE_NAME: str = "ilpo_tm"
    DEFAULT_TIMEOUT: float = 60.0

    def __init__(self, *, base_url: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=base_url or CKAN_HOST,
            headers={
                "Accept": "application/json",
                "User-Agent": "patent-client-agents-ilpo-tm/0.1",
            },
            **kwargs,
        )

    async def get_dataset(self, dataset_id: str = _DEFAULT_DATASET_ID) -> IlpoTmDataset:
        """Fetch the CKAN package metadata for a data.gov.il dataset.

        Defaults to ``trade-marks`` (the canonical ILPO TM register).
        Other ILPO datasets (e.g. patents or designs, if published) can
        be enumerated by passing a different ``dataset_id``.
        """
        payload = await self._request_json(
            "GET",
            _PACKAGE_PATH,
            params={"id": dataset_id},
            context=f"ilpo_tm.get_dataset[{dataset_id}]",
        )
        if not payload.get("success"):
            from mcp_data_core.exceptions import ApiError

            raise ApiError(
                f"CKAN package_show returned success=False for {dataset_id!r}",
                status_code=200,
                response_body=str(payload)[:500],
            )
        result = payload.get("result") or {}
        return IlpoTmDataset.model_validate(result)

    async def download_resource(self, resource_url: str) -> bytes:
        """Fetch one CKAN resource's bytes.

        For a CSV/ZIP that exceeds memory, callers should switch to
        streaming via ``self._request("GET", resource_url, ...)``
        directly.
        """
        response = await self._request(
            "GET",
            resource_url,
            context=f"ilpo_tm.download_resource[{resource_url}]",
        )
        return response.content


__all__ = ["CKAN_HOST", "IlpoTmClient"]
