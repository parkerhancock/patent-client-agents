"""Client construction tests for euipo_designs."""

from __future__ import annotations

import pytest

from mcp_data_core.exceptions import ConfigurationError
from patent_client_agents.euipo_designs import EuipoDesignsClient


def test_default_environment_is_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EUIPO_ENV", raising=False)
    monkeypatch.setenv("EUIPO_CLIENT_ID", "x")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "y")
    client = EuipoDesignsClient()
    assert client.environment == "production"
    assert client.base_url == "https://api.euipo.europa.eu/design-search"


def test_sandbox_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    client = EuipoDesignsClient(environment="sandbox", client_id="x", client_secret="y")
    assert client.environment == "sandbox"
    assert client.base_url == "https://api-sandbox.euipo.europa.eu/design-search"


def test_missing_client_id_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EUIPO_CLIENT_ID", raising=False)
    monkeypatch.delenv("EUIPO_CLIENT_SECRET", raising=False)
    with pytest.raises(ConfigurationError, match="EUIPO client_id"):
        EuipoDesignsClient()


def test_search_validates_page_size(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setenv("EUIPO_CLIENT_ID", "x")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "y")
    client = EuipoDesignsClient()
    with pytest.raises(ValueError, match="size must be"):
        asyncio.run(client.search(size=5))
    asyncio.run(client.close())


def test_x_ibm_client_id_header_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EUIPO_CLIENT_ID", "abc123")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "secret")
    client = EuipoDesignsClient()
    assert client._client.headers.get("X-IBM-Client-Id") == "abc123"
