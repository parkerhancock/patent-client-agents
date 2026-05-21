"""Client construction tests for euipo_trademarks.

Network-touching tests are intentionally not here yet — they need
recorded cassettes. These tests cover config plumbing.
"""

from __future__ import annotations

import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.euipo_trademarks import EuipoTrademarksClient


def test_default_environment_is_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EUIPO_ENV", raising=False)
    monkeypatch.setenv("EUIPO_CLIENT_ID", "test_id")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "test_secret")
    client = EuipoTrademarksClient()
    assert client.environment == "production"
    assert client.base_url == "https://api.euipo.europa.eu/trademark-search"


def test_sandbox_environment_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EUIPO_ENV", "sandbox")
    monkeypatch.setenv("EUIPO_CLIENT_ID", "test_id")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "test_secret")
    client = EuipoTrademarksClient()
    assert client.environment == "sandbox"
    assert client.base_url == "https://api-sandbox.euipo.europa.eu/trademark-search"


def test_sandbox_environment_via_arg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EUIPO_ENV", "production")  # arg should win
    client = EuipoTrademarksClient(environment="sandbox", client_id="x", client_secret="y")
    assert client.environment == "sandbox"
    assert "sandbox" in client.base_url


def test_constructor_args_take_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EUIPO_CLIENT_ID", "env_id")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "env_secret")
    client = EuipoTrademarksClient(
        environment="production", client_id="ctor_id", client_secret="ctor_secret"
    )
    assert client._client_id == "ctor_id"


def test_invalid_environment_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ConfigurationError, match="environment must be"):
        EuipoTrademarksClient(
            environment="staging",  # type: ignore[arg-type]
            client_id="x",
            client_secret="y",
        )


def test_missing_client_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EUIPO_CLIENT_ID", raising=False)
    monkeypatch.delenv("EUIPO_CLIENT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="EUIPO client_id"):
        EuipoTrademarksClient()


def test_missing_client_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EUIPO_CLIENT_ID", "x")
    monkeypatch.delenv("EUIPO_CLIENT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="EUIPO client_secret"):
        EuipoTrademarksClient()


def test_custom_auth_handler_skips_secret_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """If caller supplies their own auth handler, no need for env client_secret."""
    import httpx

    monkeypatch.setenv("EUIPO_CLIENT_ID", "x")
    monkeypatch.delenv("EUIPO_CLIENT_SECRET", raising=False)

    class _NoOpAuth(httpx.Auth):
        def auth_flow(self, request):  # type: ignore[override]
            yield request

    client = EuipoTrademarksClient(auth=_NoOpAuth())
    assert client.base_url.endswith("/trademark-search")


def test_x_ibm_client_id_header_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every request must carry the IBM apiKey header."""
    monkeypatch.setenv("EUIPO_CLIENT_ID", "abc123")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "secret")
    client = EuipoTrademarksClient()
    assert client._client.headers.get("X-IBM-Client-Id") == "abc123"


def test_search_validates_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setenv("EUIPO_CLIENT_ID", "x")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "y")
    client = EuipoTrademarksClient()
    with pytest.raises(ValueError, match="size must be"):
        asyncio.run(client.search(size=5))
    with pytest.raises(ValueError, match="size must be"):
        asyncio.run(client.search(size=200))
    with pytest.raises(ValueError, match="page must be"):
        asyncio.run(client.search(page=-1))
    asyncio.run(client.close())
