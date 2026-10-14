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
from patent_client_agents.thai_dip.client import BASE_URL, PatentKind, ThaiDipClient
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

    return ThaiDipClient("explicit-token", transport=httpx.MockTransport(handler))


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
    assert captured[0].method == "POST"
    assert str(captured[0].url) == f"{BASE_URL}/PATENT_NOIP"
    assert captured[0].headers["Authorization"] == "Bearer explicit-token"
    assert json.loads(captured[0].content) == {"patent_name": "%sensor%"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("right_type", "endpoint"),
    [("invention", "PATENT_NOIP"), ("design", "PRODUCTPATENT"), ("petty_patent", "PETTYPATENT")],
)
async def test_all_patent_datasets(
    right_type: PatentKind, endpoint: str, fixture_dir: Path
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, captured) as client:
        rows, _ = await client.search_patents(
            "2501000001", right_type=right_type, field="application_number"
        )
    assert rows[0].right_type == right_type
    assert str(captured[0].url) == f"{BASE_URL}/{endpoint}"
    assert json.loads(captured[0].content) == {"app_no": "2501000001"}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "endpoint", "field", "expected"),
    [
        ("search_trademarks", "TM", "mark_name", "SYNTHETIC MARK"),
        ("search_copyrights", "CPR", "work_name", "Synthetic handbook"),
        ("search_songs", "CPRSONG", "song_name", "Synthetic melody"),
        ("search_geographical_indications", "GI", "name", "Synthetic Highland Rice"),
    ],
)
async def test_other_catalogue_schemas(
    method: str, endpoint: str, field: str, expected: str, fixture_dir: Path
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, captured) as client:
        rows, total = await getattr(client, method)("Synthetic")
    assert str(captured[0].url) == f"{BASE_URL}/{endpoint}"
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


@pytest.mark.asyncio
async def test_get_trademark_returns_the_exact_application_not_a_longer_match() -> None:
    # The DIP application-number filter is a substring match, so a lookup can
    # return longer numbers that merely contain the one requested.
    rows = [
        {"REQ_NO": "2500000019", "TR_NAME": "WRONG MARK"},
        {"REQ_NO": "25000001", "TR_NAME": "RIGHT MARK"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=rows)

    async with ThaiDipClient("explicit-token", transport=httpx.MockTransport(handler)) as client:
        record = await client.get_trademark("25000001")
        assert record.mark_name == "RIGHT MARK"
        with pytest.raises(NotFoundError):
            await client.get_trademark("2500000")


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

    async with ThaiDipClient("token", transport=httpx.MockTransport(handler)) as client:
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

    async with ThaiDipClient("token", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ApiError, match=match):
            await client.search_geographical_indications("rice")


@pytest.mark.asyncio
async def test_missing_record_and_identifier_raise_domain_errors() -> None:
    responses = iter([b"[]", b'[{"PATENT_NAME":"missing number"}]'])

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=next(responses))

    async with ThaiDipClient("token", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(NotFoundError):
            await client.get_trademark("missing")
        with pytest.raises(ApiError, match="lacks an identifier"):
            await client.search_patents("missing")


def test_date_parser_rejects_unknown_values() -> None:
    assert parse_dip_date("not-a-date") is None
    assert parse_dip_date(1234) is None
