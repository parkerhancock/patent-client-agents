"""Client-level tests for the IP RAPID bulk catalog client.

Constructor smoke + the CKAN ``package_show`` request shape + the
``ApiError`` raise when CKAN returns ``success=False`` + the
``download_resource`` fetch. HTTP mocked with ``httpx.MockTransport``;
no live calls.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from mcp_data_core.exceptions import ApiError
from patent_client_agents.ip_australia_bulk import CKAN_HOST, IpAustraliaBulkClient


def _mock_http(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_default_base_url_is_data_gov_au() -> None:
    client = IpAustraliaBulkClient()
    assert client.base_url == CKAN_HOST
    assert client._client.auth is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_get_dataset_calls_ckan_package_show() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {
                    "id": "abc-123",
                    "name": "iprapid",
                    "title": "IP RAPID",
                    "license_id": "cc-by-4.0",
                    "license_title": "Creative Commons Attribution 4.0 International",
                    "resources": [
                        {
                            "id": "r-1",
                            "name": "IPRAPID.zip",
                            "format": "ZIP",
                            "mimetype": "application/zip",
                            "size": 1_318_890_174,
                            "url": "https://data.gov.au/data/dataset/x/resource/r-1/download/iprapid.zip",
                            "last_modified": "2026-05-12T02:49:34.617084",
                        }
                    ],
                },
            },
        )

    async with IpAustraliaBulkClient(client=_mock_http(handler)) as client:
        dataset = await client.get_dataset()

    assert captured[0].method == "GET"
    assert captured[0].url.path.endswith("/data/api/3/action/package_show")
    assert captured[0].url.params.get("id") == "iprapid"
    assert dataset.name == "iprapid"
    assert len(dataset.resources) == 1
    assert dataset.resources[0].size == 1_318_890_174


@pytest.mark.asyncio
async def test_get_dataset_passes_custom_dataset_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"success": True, "result": {"id": "x", "name": "ipgod", "resources": []}},
        )

    async with IpAustraliaBulkClient(client=_mock_http(handler)) as client:
        dataset = await client.get_dataset("ipgod")

    assert captured[0].url.params.get("id") == "ipgod"
    assert dataset.name == "ipgod"


@pytest.mark.asyncio
async def test_get_dataset_raises_when_ckan_reports_success_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"success": False, "error": {"message": "Not Found"}})

    async with IpAustraliaBulkClient(client=_mock_http(handler)) as client:
        with pytest.raises(ApiError, match="success=False"):
            await client.get_dataset("missing")


@pytest.mark.asyncio
async def test_download_resource_streams_bytes() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"binary-payload")

    async with IpAustraliaBulkClient(client=_mock_http(handler)) as client:
        data = await client.download_resource(
            "https://data.gov.au/data/dataset/x/resource/r-1/download/iprapid.zip"
        )

    assert data == b"binary-payload"
    assert captured[0].method == "GET"
    assert str(captured[0].url).endswith("/iprapid.zip")
