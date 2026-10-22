"""Client-level tests for the IP Australia Trade Marks client.

Constructor wiring + ``POST /search/quick`` body shaping + the
``GET /trade-mark/{n}`` detail path. HTTP mocked with
``httpx2.MockTransport``; no live API calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx2
import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.ip_australia_trademarks import IpAustraliaTrademarksClient


@pytest.fixture
def _au_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "test-id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "test-secret")
    monkeypatch.delenv("IPAUSTRALIA_ENV", raising=False)


def _mock_transport(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> httpx2.MockTransport:
    """Serve the OAuth token endpoint, and hand API requests to ``handler``."""

    def route(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/access_token"):
            return httpx2.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return handler(request)

    return httpx2.MockTransport(route)


def test_missing_env_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IPAUSTRALIA_CLIENT_ID", raising=False)
    monkeypatch.delenv("IPAUSTRALIA_CLIENT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="IPAUSTRALIA_CLIENT_ID"):
        IpAustraliaTrademarksClient()


def test_constructor_uses_trademarks_api_path(_au_env: None) -> None:
    client = IpAustraliaTrademarksClient()
    assert client.environment == "production"
    assert client.base_url.endswith("/public/australian-trade-mark-search-api/v1")


def test_sandbox_environment_swaps_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "test-id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("IPAUSTRALIA_ENV", "sandbox")

    client = IpAustraliaTrademarksClient()
    assert client.environment == "sandbox"
    assert client.base_url.startswith("https://test.api.ipaustralia.gov.au")


@pytest.mark.asyncio
async def test_search_posts_quick_endpoint_with_query(_au_env: None) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(
            200,
            json={
                "results": [
                    {
                        "serialNumber": "1234567",
                        "wordMark": "VEGEMITE",
                        "status": "REGISTERED",
                        "markType": "WORD",
                        "applicationDate": "2020-01-15",
                    }
                ],
                "total": 1,
            },
        )

    async with IpAustraliaTrademarksClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        result = await client.search(query="VEGEMITE")

    assert len(captured) == 1
    req = captured[0]
    assert req.method == "POST"
    assert req.url.path.endswith("/search/quick")
    assert json.loads(req.content) == {"query": "VEGEMITE"}

    assert result.total == 1
    assert result.results[0].serial_number == "1234567"
    assert result.results[0].word_mark == "VEGEMITE"


@pytest.mark.asyncio
async def test_search_serializes_quick_search_type_filter(_au_env: None) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(200, json={"results": [], "total": 0})

    async with IpAustraliaTrademarksClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        await client.search(
            query="*",
            quick_search_type=["WORD", "IMAGE"],
            status=["REGISTERED"],
            changed_since="2025-12-01",
            sort_field="NUMBER",
            sort_direction="DESCENDING",
            extra={"customField": "x"},
        )

    body = json.loads(captured[0].content)
    assert body["filters"] == {
        "quickSearchType": ["WORD", "IMAGE"],
        "status": ["REGISTERED"],
    }
    assert body["changedSinceDate"] == "2025-12-01"
    assert body["sort"] == {"field": "NUMBER", "direction": "DESCENDING"}
    assert body["customField"] == "x"


@pytest.mark.asyncio
async def test_search_omits_optional_blocks_when_unset(_au_env: None) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(200, json={"results": [], "total": 0})

    async with IpAustraliaTrademarksClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        await client.search(query="x")

    body = json.loads(captured[0].content)
    assert "filters" not in body
    assert "sort" not in body
    assert "changedSinceDate" not in body


@pytest.mark.asyncio
async def test_get_trademark_hits_detail_endpoint(_au_env: None) -> None:
    captured: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured.append(request)
        return httpx2.Response(
            200,
            json={
                "serialNumber": "1234567",
                "wordMark": "VEGEMITE",
                "status": "REGISTERED",
                "markType": "WORD",
                "applicationDate": "2020-01-15",
                "registrationDate": "2020-08-22",
                "niceClasses": [29, 30],
                "owners": [{"name": "Bega Cheese Ltd"}],
            },
        )

    async with IpAustraliaTrademarksClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        record = await client.get_trademark("1234567")

    assert captured[0].method == "GET"
    assert captured[0].url.path.endswith("/trade-mark/1234567")
    assert record.serial_number == "1234567"
    assert record.nice_classes == [29, 30]
    assert record.owners == [{"name": "Bega Cheese Ltd"}]
