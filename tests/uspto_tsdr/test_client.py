"""Tests for USPTO TSDR client."""

import pytest

from law_tools_core.exceptions import ConfigurationError
from patent_client_agents.uspto_tsdr import TsdrClient


class TestTsdrClient:
    """Tests for TsdrClient."""

    def test_requires_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that client requires API key."""
        monkeypatch.delenv("USPTO_TSDR_API_KEY", raising=False)
        with pytest.raises(ConfigurationError, match="API key required"):
            TsdrClient(api_key=None)

    def test_format_case_id_serial(self) -> None:
        """Test serial number formatting."""
        client = TsdrClient.__new__(TsdrClient)
        assert client._format_case_id("97123456", "sn") == "sn97123456"
        assert client._format_case_id("sn97123456", "sn") == "sn97123456"
        assert client._format_case_id("97-123-456", "sn") == "sn97123456"

    def test_format_case_id_registration(self) -> None:
        """Test registration number formatting."""
        client = TsdrClient.__new__(TsdrClient)
        assert client._format_case_id("1234567", "rn") == "rn1234567"
        assert client._format_case_id("rn1234567", "rn") == "rn1234567"


@pytest.mark.live_tsdr
class TestTsdrClientLive:
    """Live tests for TsdrClient - require USPTO_TSDR_API_KEY."""

    @pytest.mark.asyncio
    async def test_get_status(self, vcr_cassette) -> None:
        """Test getting trademark status.

        Asserts on populated fields, not just serial_number — the previous
        XML parser silently returned an all-null model when USPTO switched
        TSDR to JSON, and the only assertion (`serial_number == ...`)
        passed because the serial is set by the caller.
        """
        async with TsdrClient() as client:
            status = await client.get_status("78787878")
            assert status.serial_number == "78787878"
            assert status.mark_text == "MAC MEMPHIS ATHLETIC CAMPUS"
            assert status.filing_date == "2006-01-09"
            assert status.status_date == "2007-09-25"
            assert status.abandonment_date == "2007-08-07"
            assert status.mark_type == "COLLECTIVE_MEMBERSHIP_MARK"
            assert any("MEMPHIS ATHLETIC" in (o.name or "") for o in status.owners)
            assert len(status.prosecution_history) > 0
            assert len(status.goods_services) > 0

    @pytest.mark.asyncio
    async def test_get_last_update(self, vcr_cassette) -> None:
        """Test getting last update info."""
        async with TsdrClient() as client:
            info = await client.get_last_update("78787878")
            assert info.serial_number == "78787878"

    @pytest.mark.asyncio
    async def test_get_documents(self, vcr_cassette) -> None:
        """Test getting document list."""
        async with TsdrClient() as client:
            docs = await client.get_documents("78787878")
            assert isinstance(docs, list)

    @pytest.mark.asyncio
    async def test_get_image(self, vcr_cassette) -> None:
        """Test getting mark image."""
        async with TsdrClient() as client:
            image = await client.get_image("78787878")
            assert isinstance(image, bytes)
            assert len(image) > 0
