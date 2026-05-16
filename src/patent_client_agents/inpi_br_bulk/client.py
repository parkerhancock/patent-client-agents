"""Async client for the INPI Brazil RPI bulk catalog on dados.gov.br.

The *Revista da Propriedade Industrial* (RPI) is INPI Brazil's weekly
official bulletin. Every administrative act (filings, office actions,
allowances, registrations, oppositions, appeals, GI grants, IC topography
registrations, technology-transfer contract registrations) publishes
here. Eight sections — patents, trade marks, designs, GIs, software
programs, IC topographies, technology-transfer contracts, and INPI
communications — are distributed as PDF + TXT-in-ZIP + XML-in-ZIP files,
indexed by dados.gov.br under Decreto 8.777/2016's open license.

This client is the **catalog + download** surface (Shape E in
CONNECTOR_STANDARDS.md §7.2). It exposes:

* ``get_dataset()`` — fetch the package metadata, including the list of
  downloadable resources.
* ``download_resource(resource_url)`` — stream one resource's bytes.

A full RPI XML ingestion pipeline (per-section parsers, INID-code +
INPI-dispatch-code decoders, schema-versioned record models) is
intentionally out of scope for v1 of this connector — it should land
separately so the catalog surface ships independently.

Note: dados.gov.br migrated its discovery UI to a SPA in 2024 and gates
the new portal's API behind ``Authorization`` for most endpoints. The
legacy CKAN-compatible action endpoint
(``/api/3/action/package_show``) is the most stable read-path; if the
portal retires that route in the future, the client below is the right
single place to swap to the new public-search shape — every consumer
goes through ``get_dataset``.
"""

from __future__ import annotations

from typing import Any

from law_tools_core import BaseAsyncClient

from .models import BulkDataset

CKAN_HOST = "https://dados.gov.br"
_PACKAGE_PATH = "/api/3/action/package_show"
INPI_BR_RPI_DATASET_ID = "revista-da-propriedade-industrial-rpi"


class InpiBrBulkClient(BaseAsyncClient):
    """Async client for the dados.gov.br catalog (INPI RPI dataset).

    No auth; the CKAN ``package_show`` action is public. Downloads
    stream directly from the resource ``url`` reported by the catalog.
    """

    CACHE_NAME: str = "inpi_br_bulk"
    DEFAULT_TIMEOUT: float = 60.0

    def __init__(self, *, base_url: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=base_url or CKAN_HOST,
            headers={
                "Accept": "application/json",
                "User-Agent": "patent-client-agents-inpi-br-bulk/0.1",
            },
            **kwargs,
        )

    async def get_dataset(self, dataset_id: str = INPI_BR_RPI_DATASET_ID) -> BulkDataset:
        """Fetch the catalog package metadata for a dados.gov.br dataset.

        Defaults to ``revista-da-propriedade-industrial-rpi`` (the RPI
        weekly feed). INPI also publishes annual bibliographic snapshots
        on dados.gov.br (e.g. ``bw-p-2020`` for Pedidos de Patentes
        2020) — pass an alternate ``dataset_id`` to enumerate those.
        """
        payload = await self._request_json(
            "GET",
            _PACKAGE_PATH,
            params={"id": dataset_id},
            context=f"inpi_br_bulk.get_dataset[{dataset_id}]",
        )
        if not payload.get("success"):
            from law_tools_core.exceptions import ApiError

            raise ApiError(
                f"dados.gov.br package_show returned success=False for {dataset_id!r}",
                status_code=200,
                response_body=str(payload)[:500],
            )
        result = payload.get("result") or {}
        return BulkDataset.model_validate(result)

    async def download_resource(self, resource_url: str) -> bytes:
        """Fetch one catalog resource's bytes.

        The URL comes from :class:`BulkResource.url` — RPI XML/TXT zips
        are typically <50 MB each, so an in-memory pull is fine; callers
        that need streaming for a wider catalog-wide sweep should use
        ``self._request("GET", resource_url, ...)`` directly.
        """
        response = await self._request(
            "GET",
            resource_url,
            context=f"inpi_br_bulk.download_resource[{resource_url}]",
        )
        return response.content


__all__ = ["CKAN_HOST", "INPI_BR_RPI_DATASET_ID", "InpiBrBulkClient"]
