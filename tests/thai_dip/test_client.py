from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from patent_client_agents.thai_dip.client import PatentKind, ThaiDipClient
from patent_client_agents.thai_dip.models import parse_dip_date


def _client_for(
    fixture_dir: Path,
    captured: list[httpx.Request] | None = None,
) -> ThaiDipClient:
    fixture_by_endpoint = {
        "PATENT_NOIP": "patent.json",
        "PRODUCTPATENT": "patent.json",
        "PETTYPATENT": "patent.json",
        "TM": "trademark.json",
        "CPR": "copyright.json",
        "CPRSONG": "song.json",
        "GI": "gi.json",
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        filename = fixture_by_endpoint[request.url.path.rsplit("/", 1)[-1]]
        return httpx.Response(200, content=(fixture_dir / filename).read_bytes())

    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://mock.test"
    )
    return ThaiDipClient("explicit-token", base_url="https://mock.test", client=http_client)


@pytest.mark.asyncio
async def test_patent_search_uses_documented_body_and_bearer_token(fixture_dir: Path) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, captured) as client:
        rows, total = await client.search_patents("sensor", limit=1)

    assert total == 2
    assert len(rows) == 1
    assert rows[0].application_number == "2501000001"
    assert rows[0].filing_date is not None
    assert rows[0].filing_date.isoformat() == "2025-01-15"
    assert rows[0].raw["FUTURE_FIELD"] == "preserved"
    assert captured[0].headers["Authorization"] == "Bearer explicit-token"
    assert json.loads(captured[0].content) == {"patent_name": "%sensor%"}


@pytest.mark.asyncio
@pytest.mark.parametrize("right_type", ["invention", "design", "petty_patent"])
async def test_all_patent_datasets(right_type: PatentKind, fixture_dir: Path) -> None:
    async with _client_for(fixture_dir) as client:
        rows, _ = await client.search_patents(
            "2501000001", right_type=right_type, field="application_number"
        )
    assert rows[0].right_type == right_type


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "field", "expected"),
    [
        ("search_trademarks", "mark_name", "SYNTHETIC MARK"),
        ("search_copyrights", "work_name", "Synthetic handbook"),
        ("search_songs", "song_name", "Synthetic melody"),
        ("search_geographical_indications", "name", "Synthetic Highland Rice"),
    ],
)
async def test_other_catalogue_schemas(
    method: str, field: str, expected: str, fixture_dir: Path
) -> None:
    async with _client_for(fixture_dir) as client:
        rows, total = await getattr(client, method)("Synthetic")
    assert total == 1
    assert getattr(rows[0], field) == expected
    assert rows[0].raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "argument", "field", "expected"),
    [
        ("get_patent", "2501000001", "application_number", "2501000001"),
        ("get_trademark", "250000001", "application_number", "250000001"),
        ("get_copyright", "CR-250001", "request_number", "CR-250001"),
        ("get_geographical_indication", "90001", "identifier", "90001"),
    ],
)
async def test_fetch_uses_exact_identifier_search(
    method: str, argument: str, field: str, expected: str, fixture_dir: Path
) -> None:
    async with _client_for(fixture_dir) as client:
        row = await getattr(client, method)(argument)
    assert getattr(row, field) == expected


def test_credentials_and_https_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIP_DATA_EXCHANGE_TOKEN", raising=False)
    with pytest.raises(ConfigurationError, match="DIP_DATA_EXCHANGE_TOKEN"):
        ThaiDipClient()
    with pytest.raises(ConfigurationError, match="HTTPS"):
        ThaiDipClient("token", base_url="http://example.test")


@pytest.mark.parametrize("query", ["", "x" * 501])
@pytest.mark.asyncio
async def test_query_validation(query: str, fixture_dir: Path) -> None:
    async with _client_for(fixture_dir) as client:
        with pytest.raises(ConfigurationError, match="1 to 500"):
            await client.search_trademarks(query)


@pytest.mark.asyncio
async def test_limit_validation(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir) as client:
        with pytest.raises(ConfigurationError, match="between 1 and 100"):
            await client.search_copyrights("work", limit=101)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (500, ApiError),
    ],
)
async def test_http_errors_map_to_domain_errors(status: int, error_type: type[Exception]) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="upstream error")

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with ThaiDipClient("token", client=http_client) as client:
        with pytest.raises(error_type):
            await client.search_songs("melody")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "match"),
    [(b"not-json", "malformed JSON"), (b'{"message":"Invalid Api."}', "Invalid Api")],
)
async def test_invalid_response_shapes_raise_api_error(content: bytes, match: str) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with ThaiDipClient("token", client=http_client) as client:
        with pytest.raises(ApiError, match=match):
            await client.search_geographical_indications("rice")


@pytest.mark.asyncio
async def test_missing_record_and_identifier_raise_domain_errors() -> None:
    responses = iter([b"[]", b'[{"PATENT_NAME":"missing number"}]'])

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(responses))

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with ThaiDipClient("token", client=http_client) as client:
        with pytest.raises(NotFoundError):
            await client.get_trademark("missing")
        with pytest.raises(ApiError, match="lacks an identifier"):
            await client.search_patents("missing")


def test_date_parser_rejects_unknown_values() -> None:
    assert parse_dip_date("not-a-date") is None
    assert parse_dip_date(1234) is None
