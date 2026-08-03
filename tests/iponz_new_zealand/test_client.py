from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import httpx
import pytest

from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from patent_client_agents.iponz_new_zealand.client import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    IponzClient,
)


def _client_for(
    fixture_dir: Path,
    fixture_name: str,
    captured: list[httpx.Request] | None = None,
    *,
    environment: Literal["production", "sandbox"] | None = None,
    access_token: str | None = None,
) -> IponzClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        return httpx.Response(200, content=(fixture_dir / fixture_name).read_bytes())

    return IponzClient(
        "mock-subscription",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        environment=environment,
        access_token=access_token,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "number", "fixture", "field", "expected"),
    [
        ("get_patent", "765432", "patent_information.xml", "title", "Adaptive necktie controller"),
        ("get_trademark", "1234567", "trademark_information.xml", "title", "NECKTIE LABS"),
        ("get_design", "998877", "design_information.xml", "title", "Necktie clasp"),
    ],
)
async def test_detail_operations_use_exact_paths_and_parse_official_schemas(
    fixture_dir: Path,
    method: str,
    number: str,
    fixture: str,
    field: str,
    expected: str,
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, fixture, captured) as client:
        row = await getattr(client, method)(number)
    assert getattr(row, field) == expected
    assert str(captured[0].url).startswith(PRODUCTION_BASE_URL)
    assert captured[0].headers["Ocp-Apim-Subscription-Key"] == "mock-subscription"
    assert row.raw


@pytest.mark.asyncio
async def test_detail_fields_are_normalized(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "patent_information.xml") as client:
        patent = await client.get_patent("765432")
    assert patent.applicants == ["Necktie Labs NZ Limited"]
    assert patent.inventors == ["Aroha Ngata"]
    assert patent.classifications == ["G06F 1/00"]
    assert patent.grant_date == date(2025, 4, 5)

    async with _client_for(fixture_dir, "trademark_information.xml") as client:
        trademark = await client.get_trademark("1234567")
    assert trademark.word_marks == ["NECKTIE LABS"]
    assert trademark.nice_classes == ["42"]
    assert trademark.applicants == ["Necktie Labs NZ Limited"]

    async with _client_for(fixture_dir, "design_information.xml") as client:
        design = await client.get_design("998877")
    assert design.articles == ["Clasp"]
    assert design.applicants == ["Necktie Labs NZ Limited"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "fixture", "right_type", "path"),
    [
        (
            "list_patents_updated",
            "patents_updated.xml",
            "patent",
            "/patents/updated/20260801-20260803",
        ),
        (
            "list_trademarks_updated",
            "trademarks_updated.xml",
            "trademark",
            "/trademarks/updated/20260801-20260803",
        ),
        (
            "list_designs_updated",
            "designs_updated.xml",
            "design",
            "/designs/updated/20260801-20260803",
        ),
        (
            "list_designs_registered",
            "designs_registered.xml",
            "design",
            "/designs/registered/20260801-20260803",
        ),
    ],
)
async def test_date_range_operations(
    fixture_dir: Path,
    method: str,
    fixture: str,
    right_type: str,
    path: str,
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, fixture, captured) as client:
        rows = await getattr(client, method)(date(2026, 8, 1), date(2026, 8, 3))
    assert rows[0].right_type == right_type
    assert rows[0].event_date
    assert captured[0].url.path.endswith(path)


def test_configuration_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IPONZ_SUBSCRIPTION_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="portal.api.business.govt.nz"):
        IponzClient()
    with pytest.raises(ConfigurationError, match="IPONZ_ENV"):
        IponzClient("key", environment="invalid")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
    with pytest.raises(ConfigurationError, match="HTTPS"):
        IponzClient("key", base_url="http://example.test")


@pytest.mark.asyncio
async def test_register_number_validation() -> None:
    async with IponzClient(
        "key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
    ) as client:
        with pytest.raises(ConfigurationError, match="only digits"):
            await client.get_patent("NZ/123")
        with pytest.raises(ConfigurationError, match="must not be empty"):
            await client.get_design("   ")


@pytest.mark.asyncio
async def test_sandbox_and_optional_bearer_headers(fixture_dir: Path) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(
        fixture_dir,
        "patent_information.xml",
        captured,
        environment="sandbox",
        access_token="mock-bearer",
    ) as client:
        await client.get_patent("765432")
    assert str(captured[0].url).startswith(SANDBOX_BASE_URL)
    assert captured[0].headers["Authorization"] == "Bearer mock-bearer"


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (date(2009, 12, 31), date(2010, 1, 1), "before 2010"),
        (date(2026, 8, 3), date(2026, 8, 2), "on or after"),
        (date(2025, 8, 3), date(2026, 8, 3), "shorter than one year"),
    ],
)
@pytest.mark.asyncio
async def test_date_range_validation(start: date, end: date, message: str) -> None:
    async with IponzClient(
        "key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
    ) as client:
        with pytest.raises(ConfigurationError, match=message):
            await client.list_patents_updated(start, end)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, NotFoundError),
        (500, ApiError),
    ],
)
async def test_http_errors(status: int, exception: type[Exception]) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="upstream failure")

    async with IponzClient(
        "key", client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    ) as client:
        with pytest.raises(exception):
            await client.get_patent("765432")


@pytest.mark.asyncio
async def test_rate_limit_transaction_error_and_malformed_xml(fixture_dir: Path) -> None:
    async def throttled(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "7"}, text="slow")

    async with IponzClient(
        "key", client=httpx.AsyncClient(transport=httpx.MockTransport(throttled))
    ) as client:
        with pytest.raises(RateLimitError) as raised:
            await client.get_patent("765432")
    assert raised.value.retry_after == 7

    async with _client_for(fixture_dir, "transaction_error.xml") as client:
        with pytest.raises(ApiError, match="INVALID_CASE"):
            await client.get_patent("999999")

    async def malformed(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not xml")

    async with IponzClient(
        "key", client=httpx.AsyncClient(transport=httpx.MockTransport(malformed))
    ) as client:
        with pytest.raises(ApiError, match="malformed XML"):
            await client.get_patent("765432")
