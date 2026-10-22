"""OAuth wiring shared by the IP Australia patents, trademarks and designs clients.

The fake transport sits below the client's own auth handler, so these tests
exercise the real token fetch rather than a pre-authorised mock client.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx2
import pytest

from mcp_data_core.exceptions import AuthenticationError, NotFoundError, RateLimitError
from patent_client_agents.ip_australia_designs import IpAustraliaDesignsClient
from patent_client_agents.ip_australia_patents import IpAustraliaPatentsClient
from patent_client_agents.ip_australia_trademarks import IpAustraliaTrademarksClient

CLIENTS = [
    pytest.param(IpAustraliaPatentsClient, "get_patent", id="patents"),
    pytest.param(IpAustraliaTrademarksClient, "get_trademark", id="trademarks"),
    pytest.param(IpAustraliaDesignsClient, "get_design", id="designs"),
]


@pytest.fixture
def requests_seen() -> list[httpx2.Request]:
    return []


@pytest.fixture
def transport(requests_seen: list[httpx2.Request]) -> httpx2.MockTransport:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests_seen.append(request)
        if request.url.path.endswith("/access_token"):
            return httpx2.Response(200, json={"access_token": "tok-1", "expires_in": 3600})
        return httpx2.Response(200, json={})

    return httpx2.MockTransport(handler)


@pytest.mark.parametrize(("client_cls", "method"), CLIENTS)
@pytest.mark.parametrize(
    ("env", "host"),
    [
        (None, "production.api.ipaustralia.gov.au"),
        ("sandbox", "test.api.ipaustralia.gov.au"),
    ],
)
async def test_first_request_fetches_a_token_and_sends_it(
    monkeypatch: pytest.MonkeyPatch,
    transport: httpx2.MockTransport,
    requests_seen: list[httpx2.Request],
    client_cls: type,
    method: str,
    env: str | None,
    host: str,
) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "id-1")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "secret-1")
    if env:
        monkeypatch.setenv("IPAUSTRALIA_ENV", env)
    else:
        monkeypatch.delenv("IPAUSTRALIA_ENV", raising=False)

    async with client_cls(transport=transport, use_cache=False) as client:
        await getattr(client, method)("123")

    token_request, api_request = requests_seen[0], requests_seen[1]
    assert token_request.method == "POST"
    assert str(token_request.url) == f"https://{host}/public/external-token-api/v1/access_token"
    assert parse_qs(token_request.content.decode()) == {
        "grant_type": ["client_credentials"],
        "client_id": ["id-1"],
        "client_secret": ["secret-1"],
    }
    assert api_request.url.host == host
    assert api_request.headers["Authorization"] == "Bearer tok-1"


@pytest.mark.parametrize(("client_cls", "method"), CLIENTS)
@pytest.mark.parametrize(
    ("status", "error"),
    [(404, NotFoundError), (403, AuthenticationError), (429, RateLimitError)],
)
async def test_api_errors_map_to_typed_exceptions(
    monkeypatch: pytest.MonkeyPatch, client_cls: type, method: str, status: int, error: type
) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "id-1")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "secret-1")
    monkeypatch.delenv("IPAUSTRALIA_ENV", raising=False)

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith("/access_token"):
            return httpx2.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx2.Response(status, text="error")

    async with client_cls(
        transport=httpx2.MockTransport(handler), use_cache=False, max_retries=1
    ) as client:
        with pytest.raises(error):
            await getattr(client, method)("123")
