"""Client-level tests for the data.gov.il ILPO trade-mark CKAN client.

Constructor smoke + CKAN ``package_show`` shape + ``ApiError`` raise +
the ``download_resource`` fetch. HTTP mocked with ``httpx.MockTransport``;
no live calls.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from law_tools_core.exceptions import ApiError
from patent_client_agents.ilpo_tm import CKAN_HOST, IlpoTmClient


def _mock_http(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_default_base_url_is_data_gov_il() -> None:
    client = IlpoTmClient()
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
                    "name": "trade-marks",
                    "title": "Israeli Trade Marks Register",
                    "license_id": "cc-by-4.0",
                    "license_title": "Creative Commons Attribution 4.0",
                    "metadata_modified": "2026-05-15T12:00:00",
                    "resources": [
                        {
                            "id": "r-1",
                            "name": "trade-marks-current.csv",
                            "format": "CSV",
                            "mimetype": "text/csv",
                            "size": 12_345_678,
                            "url": "https://data.gov.il/dataset/x/resource/r-1/download/tm.csv",
                            "last_modified": "2026-05-12T02:00:00",
                        }
                    ],
                },
            },
        )

    async with IlpoTmClient(client=_mock_http(handler)) as client:
        dataset = await client.get_dataset()

    assert captured[0].method == "GET"
    assert captured[0].url.path.endswith("/api/3/action/package_show")
    assert captured[0].url.params.get("id") == "trade-marks"
    assert dataset.name == "trade-marks"
    assert dataset.license_title == "Creative Commons Attribution 4.0"
    assert len(dataset.resources) == 1
    assert dataset.resources[0].size == 12_345_678


@pytest.mark.asyncio
async def test_get_dataset_passes_custom_id() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "success": True,
                "result": {"id": "x", "name": "trademark-history", "resources": []},
            },
        )

    async with IlpoTmClient(client=_mock_http(handler)) as client:
        dataset = await client.get_dataset("trademark-history")

    assert captured[0].url.params.get("id") == "trademark-history"
    assert dataset.name == "trademark-history"


@pytest.mark.asyncio
async def test_get_dataset_raises_on_success_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"success": False, "error": {"message": "Not Found"}})

    async with IlpoTmClient(client=_mock_http(handler)) as client:
        with pytest.raises(ApiError, match="success=False"):
            await client.get_dataset("missing")


@pytest.mark.asyncio
async def test_download_resource_streams_bytes() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"id,owner\n123,Acme")

    async with IlpoTmClient(client=_mock_http(handler)) as client:
        data = await client.download_resource(
            "https://data.gov.il/dataset/x/resource/r-1/download/tm.csv"
        )

    assert data == b"id,owner\n123,Acme"
    assert captured[0].method == "GET"
    assert str(captured[0].url).endswith("/tm.csv")
