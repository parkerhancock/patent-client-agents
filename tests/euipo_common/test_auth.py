"""OAuth, headers, config and error mapping shared by both EUIPO clients.

Trademark Search and Design Search use the same EUIPO dev-portal app, token
endpoints and ``X-IBM-Client-Id`` header, so each test runs against both.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import httpx2
import pytest

from mcp_data_core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    RateLimitError,
)
from patent_client_agents.euipo_designs import EuipoDesignsClient
from patent_client_agents.euipo_trademarks import EuipoTrademarksClient

from .transport import TOKEN, api_requests, euipo_transport, is_token_request

PROD_TOKEN_URL = "https://euipo.europa.eu/cas-server-webapp/oidc/accessToken"
SANDBOX_TOKEN_URL = "https://auth-sandbox.euipo.europa.eu/oidc/accessToken"

CLIENTS = [
    pytest.param(EuipoTrademarksClient, "/trademark-search", id="trademarks"),
    pytest.param(EuipoDesignsClient, "/design-search", id="designs"),
]


def _bytes_ok(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, content=b"model-bytes")


@pytest.fixture
def _no_euipo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("EUIPO_ENV", "EUIPO_CLIENT_ID", "EUIPO_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)


@pytest.mark.usefixtures("_no_euipo_env")
@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
@pytest.mark.parametrize(
    ("env_arg", "env_var", "api_host", "token_url"),
    [
        pytest.param(None, None, "api.euipo.europa.eu", PROD_TOKEN_URL, id="default-production"),
        pytest.param(
            "production", "sandbox", "api.euipo.europa.eu", PROD_TOKEN_URL, id="arg-production"
        ),
        pytest.param(
            "sandbox", None, "api-sandbox.euipo.europa.eu", SANDBOX_TOKEN_URL, id="arg-sandbox"
        ),
        pytest.param(
            None, "sandbox", "api-sandbox.euipo.europa.eu", SANDBOX_TOKEN_URL, id="env-sandbox"
        ),
    ],
)
async def test_first_request_fetches_token_and_sends_both_auth_headers(
    monkeypatch: pytest.MonkeyPatch,
    client_cls: type,
    api_prefix: str,
    env_arg: str | None,
    env_var: str | None,
    api_host: str,
    token_url: str,
) -> None:
    if env_var:
        monkeypatch.setenv("EUIPO_ENV", env_var)
    seen: list[httpx2.Request] = []

    async with client_cls(
        client_id="app-id-1",
        client_secret="app-secret-1",
        environment=env_arg,
        transport=euipo_transport(_bytes_ok, seen),
        use_cache=False,
    ) as client:
        await client.get_model("000428557")

    assert len(seen) == 2
    token_request, api_request = seen
    assert token_request.method == "POST"
    assert str(token_request.url) == token_url
    assert parse_qs(token_request.content.decode()) == {
        "grant_type": ["client_credentials"],
        "scope": ["uid"],
        "client_id": ["app-id-1"],
        "client_secret": ["app-secret-1"],
    }
    # Credentials go in the form body, not as HTTP Basic.
    assert "Authorization" not in token_request.headers

    assert api_request.url.host == api_host
    assert api_request.url.path.startswith(f"{api_prefix}/")
    assert api_request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert api_request.headers["X-IBM-Client-Id"] == "app-id-1"


@pytest.mark.usefixtures("_no_euipo_env")
@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
async def test_credentials_resolve_from_env_and_constructor_wins(
    monkeypatch: pytest.MonkeyPatch, client_cls: type, api_prefix: str
) -> None:
    monkeypatch.setenv("EUIPO_CLIENT_ID", "env-id")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "env-secret")

    seen: list[httpx2.Request] = []
    async with client_cls(transport=euipo_transport(_bytes_ok, seen), use_cache=False) as client:
        await client.get_model("x")
    body = parse_qs(seen[0].content.decode())
    assert (body["client_id"], body["client_secret"]) == (["env-id"], ["env-secret"])
    assert seen[1].headers["X-IBM-Client-Id"] == "env-id"

    seen.clear()
    async with client_cls(
        client_id="ctor-id",
        client_secret="ctor-secret",
        transport=euipo_transport(_bytes_ok, seen),
        use_cache=False,
    ) as client:
        await client.get_model("x")
    body = parse_qs(seen[0].content.decode())
    assert (body["client_id"], body["client_secret"]) == (["ctor-id"], ["ctor-secret"])
    assert seen[1].headers["X-IBM-Client-Id"] == "ctor-id"


@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
async def test_token_is_reused_across_requests(client_cls: type, api_prefix: str) -> None:
    seen: list[httpx2.Request] = []
    async with client_cls(
        client_id="id",
        client_secret="s",
        transport=euipo_transport(_bytes_ok, seen),
        use_cache=False,
    ) as client:
        await client.get_model("a")
        await client.get_model("b")

    assert sum(is_token_request(r) for r in seen) == 1
    assert [r.headers["Authorization"] for r in api_requests(seen)] == [f"Bearer {TOKEN}"] * 2


@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
async def test_rejected_token_is_refreshed_once_and_request_retried(
    client_cls: type, api_prefix: str
) -> None:
    calls = {"api": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["api"] += 1
        if calls["api"] == 1:
            return httpx2.Response(401, json={"title": "Unauthorized", "status": 401})
        return httpx2.Response(200, content=b"ok")

    seen: list[httpx2.Request] = []
    async with client_cls(
        client_id="id", client_secret="s", transport=euipo_transport(handler, seen), use_cache=False
    ) as client:
        assert await client.get_model("a") == b"ok"

    assert [is_token_request(r) for r in seen] == [True, False, True, False]


@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
async def test_custom_auth_handler_replaces_oauth_but_keeps_client_id_header(
    monkeypatch: pytest.MonkeyPatch, client_cls: type, api_prefix: str
) -> None:
    monkeypatch.delenv("EUIPO_CLIENT_SECRET", raising=False)

    class _StaticBearer(httpx2.Auth):
        def auth_flow(self, request):  # type: ignore[override]
            request.headers["Authorization"] = "Bearer caller-supplied"
            yield request

    seen: list[httpx2.Request] = []
    async with client_cls(
        client_id="id-9",
        auth=_StaticBearer(),
        transport=euipo_transport(_bytes_ok, seen),
        use_cache=False,
    ) as client:
        await client.get_model("a")

    assert len(seen) == 1
    assert not is_token_request(seen[0])
    assert seen[0].headers["Authorization"] == "Bearer caller-supplied"
    assert seen[0].headers["X-IBM-Client-Id"] == "id-9"


@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, NotFoundError),
        (429, RateLimitError),
    ],
)
async def test_api_errors_map_to_typed_exceptions(
    client_cls: type, api_prefix: str, status: int, error: type
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            status,
            headers={"Content-Type": "application/problem+json", "Retry-After": "7"},
            json={"type": "/problems/error", "title": "Error", "status": status},
        )

    async with client_cls(
        client_id="id",
        client_secret="s",
        transport=euipo_transport(handler),
        use_cache=False,
        max_retries=1,
    ) as client:
        with pytest.raises(error) as excinfo:
            await client.get_model("000000001")

    assert excinfo.value.status_code == status
    if status == 429:
        assert excinfo.value.retry_after == 7


@pytest.mark.usefixtures("_no_euipo_env")
@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
def test_missing_client_id_raises(client_cls: type, api_prefix: str) -> None:
    with pytest.raises(ConfigurationError, match="EUIPO client_id"):
        client_cls(client_secret="s")


@pytest.mark.usefixtures("_no_euipo_env")
@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
def test_missing_client_secret_raises(client_cls: type, api_prefix: str) -> None:
    with pytest.raises(ConfigurationError, match="EUIPO client_secret"):
        client_cls(client_id="id")


@pytest.mark.parametrize(("client_cls", "api_prefix"), CLIENTS)
def test_invalid_environment_raises(client_cls: type, api_prefix: str) -> None:
    with pytest.raises(ConfigurationError, match="environment must be"):
        client_cls(environment="staging", client_id="x", client_secret="y")
