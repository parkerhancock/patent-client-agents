from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from mcp_data_core.exceptions import (
    ApiError,
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from patent_client_agents.ipi_swissreg.client import (
    BASE_URL,
    COMMON_NS,
    CORE_NS,
    TOKEN_URL,
    IpiSwissregClient,
)


def _client_for(
    fixture_dir: Path,
    fixture_name: str,
    captured: list[httpx.Request] | None = None,
    *,
    totp_token: str | None = None,
) -> IpiSwissregClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        if str(request.url) == TOKEN_URL:
            return httpx.Response(
                200,
                json={
                    "access_token": "mock-access",
                    "refresh_token": "mock-refresh",
                    "expires_in": 600,
                },
            )
        return httpx.Response(200, content=(fixture_dir / fixture_name).read_bytes())

    return IpiSwissregClient(
        "explicit-user",
        "explicit-password",
        totp_token=totp_token,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_patent_search_authenticates_builds_contract_and_parses_metadata(
    fixture_dir: Path,
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(
        fixture_dir, "patent_search.xml", captured, totp_token="123456"
    ) as client:
        rows, meta = await client.search_patents("adaptive controller", limit=12)
        await client.search_patents("second call", limit=3)

    assert len([request for request in captured if str(request.url) == TOKEN_URL]) == 1
    token_form = parse_qs(captured[0].content.decode())
    assert token_form == {
        "client_id": ["datadelivery-api-client"],
        "grant_type": ["password"],
        "username": ["explicit-user"],
        "password": ["explicit-password"],
        "totp": ["123456"],
    }
    request = captured[1]
    assert str(request.url) == BASE_URL
    assert request.headers["Authorization"] == "Bearer mock-access"
    root = ET.fromstring(request.content)
    action = root.find(f"{{{CORE_NS}}}Action")
    assert action is not None and action.attrib["type"] == "PatentSearch"
    assert (
        action.find(".//{urn:ige:schema:xsd:datadeliverypatent-1.0.0}PatentSearchRequest")
        is not None
    )
    page = action.find(f".//{{{COMMON_NS}}}Page")
    any_query = action.find(f".//{{{COMMON_NS}}}Any")
    assert page is not None and page.attrib["size"] == "12"
    assert any_query is not None and any_query.text == "adaptive controller"
    assert rows[0].identifier == "CH718001"
    assert rows[0].publication_date and rows[0].publication_date.isoformat() == "2024-07-15"
    assert rows[0].ipc == ["H02J7/00"]
    assert "FutureExtension" in str(rows[0].raw)
    assert meta.total_item_count == 2
    assert meta.item_count == 1
    assert meta.next_cursor == "opaque-patent-page-2"


@pytest.mark.asyncio
async def test_continuation_request_contains_only_cursor(fixture_dir: Path) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, "patent_search.xml", captured) as client:
        await client.search_patents("ignored", cursor="opaque-cursor")

    root = ET.fromstring(captured[1].content)
    continuation = root.find(f"{{{CORE_NS}}}Continuation")
    assert continuation is not None
    assert continuation.attrib == {"name": "NextPage"}
    assert continuation.text == "opaque-cursor"
    assert root.find(f"{{{CORE_NS}}}Action") is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "fixture", "field", "value"),
    [
        ("search_trademarks", "trademark_search.xml", "word_element", "NECKTIE"),
        ("search_spcs", "spc_search.xml", "basic_patent_number", "CH700001"),
        (
            "search_patent_publications",
            "patent_publication_search.xml",
            "publication_title",
            "Patent grant",
        ),
        (
            "search_spc_publications",
            "spc_publication_search.xml",
            "publication_title",
            "SPC grant",
        ),
    ],
)
async def test_other_action_schemas(
    fixture_dir: Path, method: str, fixture: str, field: str, value: str
) -> None:
    async with _client_for(fixture_dir, fixture) as client:
        rows, meta = await getattr(client, method)("example")
    assert getattr(rows[0], field) == value
    assert meta.total_item_count == 1
    assert rows[0].raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "fixture", "request_tag", "request_field"),
    [
        ("get_patent", "patent_search.xml", "PatentSearchRequest", "PatentNumber"),
        ("get_trademark", "trademark_search.xml", "TrademarkSearchRequest", "TradeMarkNumber"),
        ("get_spc", "spc_search.xml", "SPCSearchRequest", "SPCNumber"),
    ],
)
async def test_get_uses_identifier_query(
    fixture_dir: Path, method: str, fixture: str, request_tag: str, request_field: str
) -> None:
    captured: list[httpx.Request] = []
    async with _client_for(fixture_dir, fixture, captured) as client:
        row = await getattr(client, method)("CH-MOCK")
    root = ET.fromstring(captured[1].content)
    nodes = [node for node in root.iter() if node.tag.endswith(request_tag)]
    fields = [node for node in nodes[0].iter() if node.tag.endswith(request_field)]
    assert fields[0].text == "CH-MOCK"
    assert row.identifier


def test_credentials_and_https_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IPI_DATA_USERNAME", raising=False)
    monkeypatch.delenv("IPI_DATA_PASSWORD", raising=False)
    with pytest.raises(ConfigurationError, match="ige.ch"):
        IpiSwissregClient()
    with pytest.raises(ConfigurationError, match="HTTPS"):
        IpiSwissregClient("user", "password", base_url="http://example.test")
    with pytest.raises(ConfigurationError, match="HTTPS"):
        IpiSwissregClient("user", "password", token_url="http://example.test")


@pytest.mark.asyncio
async def test_error_malformed_empty_and_not_found(fixture_dir: Path) -> None:
    async with _client_for(fixture_dir, "error.xml") as client:
        with pytest.raises(ApiError, match="Invalid Swiss IPI query"):
            await client.search_patents("bad")

    async def malformed(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "token", "expires_in": 600})
        return httpx.Response(200, content=b"not xml")

    async with IpiSwissregClient(
        "user", "password", client=httpx.AsyncClient(transport=httpx.MockTransport(malformed))
    ) as client:
        with pytest.raises(ApiError, match="malformed XML"):
            await client.search_patents("bad")
        with pytest.raises(ConfigurationError, match="must not be empty"):
            await client.search_patents("   ")

    empty = b'<core:ApiResponse xmlns:core="urn:ige:schema:xsd:datadeliverycore-1.0.0"><core:Result success="true"/></core:ApiResponse>'

    async def no_rows(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(200, json={"access_token": "token", "expires_in": 600})
        return httpx.Response(200, content=empty)

    async with IpiSwissregClient(
        "user", "password", client=httpx.AsyncClient(transport=httpx.MockTransport(no_rows))
    ) as client:
        with pytest.raises(NotFoundError):
            await client.get_patent("missing")


@pytest.mark.asyncio
async def test_auth_rate_limit_refresh_and_one_401_retry(fixture_dir: Path) -> None:
    calls = 0

    async def unauthorized(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if str(request.url) == TOKEN_URL:
            calls += 1
            return httpx.Response(200, json={"access_token": f"token-{calls}", "expires_in": 600})
        if request.headers["Authorization"] == "Bearer token-1":
            return httpx.Response(401)
        return httpx.Response(200, content=(fixture_dir / "patent_search.xml").read_bytes())

    async with IpiSwissregClient(
        "user", "password", client=httpx.AsyncClient(transport=httpx.MockTransport(unauthorized))
    ) as client:
        rows, _ = await client.search_patents("q")
    assert rows and calls == 2

    async def throttled(request: httpx.Request) -> httpx.Response:
        if str(request.url) == TOKEN_URL:
            return httpx.Response(429, headers={"Retry-After": "9"}, text="slow")
        raise AssertionError("unexpected API call")

    async with IpiSwissregClient(
        "user", "password", client=httpx.AsyncClient(transport=httpx.MockTransport(throttled))
    ) as client:
        with pytest.raises(RateLimitError) as raised:
            await client.search_patents("q")
    assert raised.value.retry_after == 9

    async def denied(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="credentials rejected")

    async with IpiSwissregClient(
        "user", "secret", client=httpx.AsyncClient(transport=httpx.MockTransport(denied))
    ) as client:
        with pytest.raises(AuthenticationError) as raised_auth:
            await client.search_patents("q")
    assert raised_auth.value.response_body is None
    assert "secret" not in str(raised_auth.value)
