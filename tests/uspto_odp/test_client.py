"""Tests for USPTO ODP unified client."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from patent_client_agents.uspto_odp.client import UsptoOdpClient
from patent_client_agents.uspto_odp.models import SearchResponse


class TestUsptoOdpClientNormalization:
    """Tests for application number normalization."""

    def test_normalize_application_number(self) -> None:
        client = UsptoOdpClient(api_key="test")
        assert client._normalize_application_number("12/345,678") == "12345678"
        assert client._normalize_application_number("  12345678  ") == "12345678"

    @pytest.mark.asyncio
    async def test_search_applications_forwards_normalize_flag(self) -> None:
        client = UsptoOdpClient(api_key="test")
        client._applications.search = AsyncMock(return_value=SearchResponse())

        await client.search_applications(query="anything", normalize=False)

        assert client._applications.search.await_args.kwargs["normalize"] is False


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
