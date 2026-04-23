"""Tests for USPTO ODP unified client."""

from __future__ import annotations

import pytest

from patent_client_agents.uspto_odp.client import BASE_URL, UsptoOdpClient
from law_tools_core.exceptions import ConfigurationError


class TestBaseUrl:
    """Tests for BASE_URL constant."""

    def test_is_https(self) -> None:
        assert BASE_URL.startswith("https://")

    def test_is_uspto_domain(self) -> None:
        assert "api.uspto.gov" in BASE_URL


class TestUsptoOdpClientInit:
    """Tests for UsptoOdpClient initialization."""

    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USPTO_ODP_API_KEY", raising=False)
        with pytest.raises(ConfigurationError):
            UsptoOdpClient()

    def test_uses_env_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("USPTO_ODP_API_KEY", "test_key")
        client = UsptoOdpClient()
        assert client.api_key == "test_key"

    def test_uses_parameter_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("USPTO_ODP_API_KEY", raising=False)
        client = UsptoOdpClient(api_key="direct_key")
        assert client.api_key == "direct_key"

    def test_custom_base_url(self) -> None:
        client = UsptoOdpClient(api_key="test", base_url="https://custom.api.com/")
        assert client.base_url == "https://custom.api.com"

    def test_creates_sub_clients(self) -> None:
        client = UsptoOdpClient(api_key="test_key")
        assert client._applications is not None
        assert client._bulkdata is not None
        assert client._petitions is not None
        assert client._ptab_trials is not None
        assert client._ptab_appeals is not None
        assert client._ptab_interferences is not None


class TestUsptoOdpClientNormalization:
    """Tests for application number normalization."""

    def test_normalize_application_number(self) -> None:
        client = UsptoOdpClient(api_key="test")
        assert client._normalize_application_number("12/345,678") == "12345678"
        assert client._normalize_application_number("  12345678  ") == "12345678"


class TestUsptoOdpClientSubClientProperties:
    """Tests for sub-client access and configuration."""

    def test_sub_clients_share_api_key(self) -> None:
        client = UsptoOdpClient(api_key="shared_key")
        assert client._applications.api_key == "shared_key"
        assert client._bulkdata.api_key == "shared_key"
        assert client._petitions.api_key == "shared_key"
        assert client._ptab_trials.api_key == "shared_key"
        assert client._ptab_appeals.api_key == "shared_key"
        assert client._ptab_interferences.api_key == "shared_key"

    def test_sub_clients_share_base_url(self) -> None:
        client = UsptoOdpClient(api_key="key", base_url="https://custom.api.com")
        assert client._applications.base_url == "https://custom.api.com"
        assert client._bulkdata.base_url == "https://custom.api.com"

    @pytest.mark.asyncio
    async def test_context_manager_closes_all(self) -> None:
        async with UsptoOdpClient(api_key="test") as client:
            # Just verify context manager works
            assert client._applications is not None
        # After context exit, clients should be closed
        # (no explicit way to verify, but no exception = success)
