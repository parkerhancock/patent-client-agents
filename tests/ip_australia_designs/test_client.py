"""Client-level tests for the IP Australia Designs client.

Constructor wiring + ``POST /search/quick`` body shaping
(classificationFilter, statusFilter, changedSinceDate) +
``GET /design/{n}`` detail path. HTTP mocked with
``httpx.MockTransport``; no live API calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.ip_australia_designs import IpAustraliaDesignsClient


@pytest.fixture
def _au_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "test-id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "test-secret")
    monkeypatch.delenv("IPAUSTRALIA_ENV", raising=False)


def _mock_http(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_missing_env_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IPAUSTRALIA_CLIENT_ID", raising=False)
    monkeypatch.delenv("IPAUSTRALIA_CLIENT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="IPAUSTRALIA_CLIENT_ID"):
        IpAustraliaDesignsClient()


def test_constructor_uses_designs_api_path(_au_env: None) -> None:
    client = IpAustraliaDesignsClient()
    assert client.environment == "production"
    assert client.base_url.endswith("/public/australian-design-search-api/v1")


def test_sandbox_environment_swaps_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "test-id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("IPAUSTRALIA_ENV", "sandbox")

    client = IpAustraliaDesignsClient()
    assert client.environment == "sandbox"
    assert client.base_url.startswith("https://test.api.ipaustralia.gov.au")


@pytest.mark.asyncio
async def test_search_posts_quick_endpoint_with_query(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "designNumber": "202210123",
                        "title": "Bottle",
                        "status": "REGISTERED",
                        "applicationDate": "2022-03-01",
                        "locarnoClasses": ["09-01"],
                    }
                ],
                "total": 1,
            },
        )

    async with IpAustraliaDesignsClient(client=_mock_http(handler)) as client:
        result = await client.search(query="bottle")

    assert len(captured) == 1
    req = captured[0]
    assert req.method == "POST"
    assert req.url.path.endswith("/search/quick")
    assert json.loads(req.content) == {"query": "bottle"}

    assert result.total == 1
    assert result.results[0].design_number == "202210123"
    assert result.results[0].locarno_classes == ["09-01"]


@pytest.mark.asyncio
async def test_search_serializes_classification_and_status_filters(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": [], "total": 0})

    async with IpAustraliaDesignsClient(client=_mock_http(handler)) as client:
        await client.search(
            query="*",
            classification=["0202c"],
            status=["REGISTERED"],
            changed_since="2026-01-01",
            sort_field="NUMBER",
            sort_direction="DESCENDING",
            extra={"customField": "x"},
        )

    body = json.loads(captured[0].content)
    assert body["filters"] == {
        "classificationFilter": ["0202c"],
        "statusFilter": ["REGISTERED"],
    }
    assert body["changedSinceDate"] == "2026-01-01"
    assert body["sort"] == {"field": "NUMBER", "direction": "DESCENDING"}
    assert body["customField"] == "x"


@pytest.mark.asyncio
async def test_search_omits_optional_blocks_when_unset(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": [], "total": 0})

    async with IpAustraliaDesignsClient(client=_mock_http(handler)) as client:
        await client.search(query="x")

    body = json.loads(captured[0].content)
    assert "filters" not in body
    assert "sort" not in body
    assert "changedSinceDate" not in body


@pytest.mark.asyncio
async def test_get_design_hits_detail_endpoint(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "designNumber": "202210123",
                "title": "Bottle",
                "status": "REGISTERED",
                "applicationDate": "2022-03-01",
                "registrationDate": "2022-06-15",
                "locarnoClasses": ["09-01"],
                "owners": [{"name": "ACME"}],
            },
        )

    async with IpAustraliaDesignsClient(client=_mock_http(handler)) as client:
        record = await client.get_design("202210123")

    assert captured[0].method == "GET"
    assert captured[0].url.path.endswith("/design/202210123")
    assert record.design_number == "202210123"
    assert record.owners == [{"name": "ACME"}]
