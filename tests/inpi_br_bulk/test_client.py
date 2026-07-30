"""Client-level tests for the INPI Brazil RPI bulk catalog client.

Constructor smoke + the CKAN ``package_show`` request shape + the
``ApiError`` raise when the catalog returns ``success=False`` + the
``download_resource`` fetch. HTTP mocked with ``httpx.MockTransport``;
no live calls.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from mcp_data_core.exceptions import ApiError
from patent_client_agents.inpi_br_bulk import (
    CKAN_HOST,
    INPI_BR_RPI_DATASET_ID,
    InpiBrBulkClient,
)


def _mock_http(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_default_base_url_is_dados_gov_br() -> None:
    client = InpiBrBulkClient()
    assert client.base_url == CKAN_HOST
    assert client._client.auth is None  # type: ignore[attr-defined]


def test_default_dataset_id_is_rpi() -> None:
    assert INPI_BR_RPI_DATASET_ID == "revista-da-propriedade-industrial-rpi"


@pytest.mark.asyncio
async def test_get_dataset_calls_package_show() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "abc-123",
                    "name": INPI_BR_RPI_DATASET_ID,
                    "title": "Revista da Propriedade Industrial",
                    "license_id": "odc-odbl",
                    "license_title": "Open Database License (Decreto 8.777/2016)",
                    "resources": [
                        {
                            "id": "r-1",
                            "name": "RPI 2879 — Patentes.zip",
                            "format": "ZIP",
                            "mimetype": "application/zip",
                            "size": 25_000_000,
                            "url": "https://revistas.inpi.gov.br/xml/RPI2879_Patentes.zip",
                            "last_modified": "2026-03-10T03:00:00",
                        }
                    ],
                },
            },
        )

    async with InpiBrBulkClient(client=_mock_http(handler)) as client:
        dataset = await client.get_dataset()

    assert captured[0].method == "GET"
    assert captured[0].url.path.endswith("/api/3/action/package_show")
    assert captured[0].url.params.get("id") == INPI_BR_RPI_DATASET_ID
    assert dataset.name == INPI_BR_RPI_DATASET_ID
    assert len(dataset.resources) == 1
    assert dataset.resources[0].size == 25_000_000


@pytest.mark.asyncio
async def test_get_dataset_passes_custom_dataset_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"success": True, "result": {"id": "x", "name": "bw-p-2020", "resources": []}},
        )

    async with InpiBrBulkClient(client=_mock_http(handler)) as client:
        dataset = await client.get_dataset("bw-p-2020")

    assert captured[0].url.params.get("id") == "bw-p-2020"
    assert dataset.name == "bw-p-2020"


@pytest.mark.asyncio
async def test_get_dataset_raises_when_catalog_reports_success_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"success": False, "error": {"message": "Not Found"}})

    async with InpiBrBulkClient(client=_mock_http(handler)) as client:
        with pytest.raises(ApiError, match="success=False"):
            await client.get_dataset("missing")


@pytest.mark.asyncio
async def test_download_resource_streams_bytes() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"binary-payload")

    async with InpiBrBulkClient(client=_mock_http(handler)) as client:
        data = await client.download_resource(
            "https://revistas.inpi.gov.br/xml/RPI2879_Patentes.zip"
        )

    assert data == b"binary-payload"
    assert captured[0].method == "GET"
    assert str(captured[0].url).endswith("/RPI2879_Patentes.zip")
