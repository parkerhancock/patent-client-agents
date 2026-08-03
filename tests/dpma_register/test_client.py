from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest

from mcp_data_core.exceptions import ApiError, ConfigurationError, RateLimitError
from patent_client_agents.dpma_register.client import DpmaRegisterClient


def _client_for(
    fixture_dir: Path,
    filename: str,
    captured: list[httpx.Request] | None = None,
) -> DpmaRegisterClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(200, content=(fixture_dir / filename).read_bytes())

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="https://mock.test")
    return DpmaRegisterClient(
        "explicit-user",
        "explicit-pass",
        base_url="https://mock.test",
        client=http_client,
    )


@pytest.mark.asyncio
async def test_patent_search_is_namespace_tolerant_and_preserves_unknown_xml(
    fixture_dir: Path,
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, "patent_search.xml", captured) as client:
        rows, total = await client.search_patents("AKZ=10 2023", limit=25)

    assert total == 2
    assert [row.right_type for row in rows] == ["patent", "utility_model"]
    assert rows[0].application_date is not None
    assert rows[0].application_date.isoformat() == "2023-01-05"
    assert "future-extension" in str(rows[0].raw)
    expected = "Basic " + base64.b64encode(b"explicit-user:explicit-pass").decode()
    assert captured[0].headers["Authorization"] == expected
    assert captured[0].url.raw_path.endswith(b"/search/AKZ%3D10%202023")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("search_name", "fixture_name", "field", "value"),
    [
        ("search_trademarks", "trademark_search.xml", "mark_text", "NECKTIE"),
        ("search_designs", "design_search.xml", "product_indication", "Computer enclosure"),
    ],
)
async def test_other_search_schemas(
    fixture_dir: Path, search_name: str, fixture_name: str, field: str, value: str
) -> None:
    async with _client_for(fixture_dir, fixture_name) as client:
        rows, total = await getattr(client, search_name)("mock query")
    assert total == 1
    assert getattr(rows[0], field) == value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("get_name", "fixture_name", "field", "value"),
    [
        ("get_patent", "patent_detail.xml", "title", "Adaptive charging controller"),
        ("get_trademark", "trademark_detail.xml", "nice_classification", "42"),
        ("get_design", "design_detail.xml", "locarno_classification", "14-02"),
    ],
)
async def test_detail_schemas(
    fixture_dir: Path, get_name: str, fixture_name: str, field: str, value: str
) -> None:
    async with _client_for(fixture_dir, fixture_name) as client:
        row = await getattr(client, get_name)("mock-number")
    assert getattr(row, field) == value
    assert row.raw


def test_credentials_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DPMA_CONNECTPLUS_USERNAME", raising=False)
    monkeypatch.delenv("DPMA_CONNECTPLUS_PASSWORD", raising=False)
    with pytest.raises(ConfigurationError, match="dpma.de"):
        DpmaRegisterClient()


def test_non_https_base_rejected() -> None:
    with pytest.raises(ConfigurationError, match="HTTPS"):
        DpmaRegisterClient("user", "password", base_url="http://example.test")


@pytest.mark.asyncio
async def test_xml_error_and_malformed_xml_raise_api_error(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "error.xml") as client:
        with pytest.raises(ApiError, match="Invalid expert query"):
            await client.search_patents("bad")

    async def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not xml")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(malformed))
    async with DpmaRegisterClient("user", "password", client=http_client) as client:
        with pytest.raises(ApiError, match="malformed XML"):
            await client.get_patent("bad")


@pytest.mark.asyncio
async def test_rate_limit_maps_to_domain_error() -> None:
    async def throttled(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="slow down")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(throttled))
    async with DpmaRegisterClient("user", "password", client=http_client) as client:
        with pytest.raises(RateLimitError):
            await client.get_design("1")
