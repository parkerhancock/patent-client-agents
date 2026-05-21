"""Async client for the IP RAPID bulk catalog on data.gov.au.

IP RAPID ("IP Refreshed Automated Product for Information and Data") is
IP Australia's weekly snapshot of the registered IP register (patents,
trade marks, designs, plant breeder's rights) published as a ~1.3 GB
CSV zip on data.gov.au under a Creative Commons licence. The dataset is
metadata-discoverable through the CKAN API and downloadable without
auth.

This client is the **catalog + download** surface (Shape E in
CONNECTOR_STANDARDS.md §7.2). It exposes:

* ``get_dataset()`` — fetch the CKAN package metadata, including the
  list of downloadable resources.
* ``download_resource(resource_url)`` — stream one resource's bytes.

A full CSV ingestion pipeline (~40 tables, columns standardised on
ISO dates and boolean indicators per the 2019 IPGOD schema revision)
is intentionally out of scope for v1 of this connector — it should
land separately so the OAuth-API rights surface ships independently.

Verified 2026-05-16: dataset ``iprapid`` is licensed CC-BY 4.0
International with two resources (data dictionary PDF + the IPRAPID
zip, ~1.3 GB).
"""

from __future__ import annotations

from typing import Any

from mcp_data_core import BaseAsyncClient

from .models import BulkDataset

CKAN_HOST = "https://data.gov.au"
_PACKAGE_PATH = "/data/api/3/action/package_show"
_DEFAULT_DATASET_ID = "iprapid"


class IpAustraliaBulkClient(BaseAsyncClient):
    """Async client for the data.gov.au CKAN catalog (IP RAPID dataset).

    No auth; the CKAN ``package_show`` action is public. Downloads
    stream directly from the resource ``url`` reported by CKAN.
    """

    CACHE_NAME: str = "ip_australia_bulk"
    DEFAULT_TIMEOUT: float = 60.0

    def __init__(self, *, base_url: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=base_url or CKAN_HOST,
            headers={
                "Accept": "application/json",
                "User-Agent": "patent-client-agents-ip-australia-bulk/0.1",
            },
            **kwargs,
        )

    async def get_dataset(self, dataset_id: str = _DEFAULT_DATASET_ID) -> BulkDataset:
        """Fetch the CKAN package metadata for a data.gov.au dataset.

        Defaults to ``iprapid`` (the canonical IP RAPID dataset). The
        legacy annual ``ipgod`` snapshots remain accessible via the
        same call by passing a different ``dataset_id``.
        """
        payload = await self._request_json(
            "GET",
            _PACKAGE_PATH,
            params={"id": dataset_id},
            context=f"ip_australia_bulk.get_dataset[{dataset_id}]",
        )
        if not payload.get("success"):
            from mcp_data_core.exceptions import ApiError

            raise ApiError(
                f"CKAN package_show returned success=False for {dataset_id!r}",
                status_code=200,
                response_body=str(payload)[:500],
            )
        result = payload.get("result") or {}
        return BulkDataset.model_validate(result)

    async def download_resource(self, resource_url: str) -> bytes:
        """Fetch one CKAN resource's bytes. The URL comes from
        :class:`BulkResource.url` — for the big ``IPRAPID.zip`` resource
        this pulls ~1.3 GB into memory; callers that need streaming
        should use ``self._request("GET", resource_url, ...)`` directly.
        """
        response = await self._request(
            "GET",
            resource_url,
            context=f"ip_australia_bulk.download_resource[{resource_url}]",
        )
        return response.content


__all__ = ["CKAN_HOST", "IpAustraliaBulkClient"]
