"""Client-level tests for the IP Australia Patents client.

Three layers:
- Constructor wiring: env-var resolution, host swap, OAuth handler attachment.
- Request shape: search() builds the right ``POST /search/quick`` body
  (filters, sort, changedSinceDate) and get_patent() hits the right path.
- Response parsing: upstream JSON deserializes into the Pydantic models.

HTTP is mocked with ``httpx.MockTransport``; no live API calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.ip_australia_patents import IpAustraliaPatentsClient


@pytest.fixture
def _au_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "test-id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "test-secret")
    monkeypatch.delenv("IPAUSTRALIA_ENV", raising=False)


def _mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    """Serve the OAuth token endpoint, and hand API requests to ``handler``."""

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_token"):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return handler(request)

    return httpx.MockTransport(route)


def test_missing_env_raises_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IPAUSTRALIA_CLIENT_ID", raising=False)
    monkeypatch.delenv("IPAUSTRALIA_CLIENT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="IPAUSTRALIA_CLIENT_ID"):
        IpAustraliaPatentsClient()


def test_sandbox_environment_swaps_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "test-id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("IPAUSTRALIA_ENV", "sandbox")

    client = IpAustraliaPatentsClient()
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
                        "applicationNumber": "2019204205",
                        "patentNumber": "2019204205",
                        "title": "Sample patent",
                        "status": "GRANTED",
                        "applicationDate": "2019-06-25",
                        "grantDate": "2022-03-17",
                    }
                ],
                "total": 1,
            },
        )

    async with IpAustraliaPatentsClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        result = await client.search(query="blockchain")

    assert len(captured) == 1
    req = captured[0]
    assert req.method == "POST"
    assert req.url.path.endswith("/search/quick")
    assert json.loads(req.content) == {"query": "blockchain"}

    assert result.total == 1
    assert result.results[0].application_number == "2019204205"
    assert result.results[0].status == "GRANTED"


@pytest.mark.asyncio
async def test_search_serializes_filters_sort_and_changed_since(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": [], "total": 0})

    async with IpAustraliaPatentsClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        await client.search(
            query="*",
            status=["GRANTED", "ACCEPTED"],
            changed_since="2026-01-01",
            sort_field="NUMBER",
            sort_direction="DESCENDING",
            extra={"customField": "x"},
        )

    body = json.loads(captured[0].content)
    assert body["query"] == "*"
    assert body["filters"] == {"status": ["GRANTED", "ACCEPTED"]}
    assert body["changedSinceDate"] == "2026-01-01"
    assert body["sort"] == {"field": "NUMBER", "direction": "DESCENDING"}
    assert body["customField"] == "x"


@pytest.mark.asyncio
async def test_search_omits_optional_blocks_when_unset(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"results": [], "total": 0})

    async with IpAustraliaPatentsClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        await client.search(query="x")

    body = json.loads(captured[0].content)
    assert "filters" not in body
    assert "sort" not in body
    assert "changedSinceDate" not in body


@pytest.mark.asyncio
async def test_get_patent_hits_detail_endpoint(_au_env: None) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "applicationNumber": "2019204205",
                "patentNumber": "2019204205",
                "title": "Sample",
                "status": "GRANTED",
                "applicationDate": "2019-06-25",
                "grantDate": "2022-03-17",
                "applicants": [{"name": "ACME"}],
            },
        )

    async with IpAustraliaPatentsClient(
        transport=_mock_transport(handler), use_cache=False
    ) as client:
        record = await client.get_patent("2019204205")

    assert captured[0].method == "GET"
    assert captured[0].url.path.endswith("/patent/2019204205")
    assert record.application_number == "2019204205"
    assert record.applicants == [{"name": "ACME"}]
