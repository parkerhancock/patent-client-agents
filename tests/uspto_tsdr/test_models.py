"""Tests for USPTO TSDR models."""

from patent_client_agents.uspto_tsdr import (
    TrademarkStatus,
)


class TestTrademarkStatus:
    """Tests for TrademarkStatus model."""

    def test_basic_parsing(self) -> None:
        """Test basic model parsing."""
        data = {
            "serialNumber": "97123456",
            "registrationNumber": "1234567",
            "markText": "TEST MARK",
            "statusCode": "800",
            "statusDescription": "Registered",
            "filingDate": "2022-01-15",
            "registrationDate": "2023-06-20",
        }
        status = TrademarkStatus.model_validate(data)
        assert status.serial_number == "97123456"
        assert status.registration_number == "1234567"
        assert status.mark_text == "TEST MARK"
        assert status.is_registered is True
        assert status.is_live is True

    def test_abandoned_status(self) -> None:
        """Test abandoned trademark status."""
        data = {
            "serialNumber": "97123456",
            "abandonmentDate": "2023-01-01",
        }
        status = TrademarkStatus.model_validate(data)
        assert status.is_live is False
        assert status.is_registered is False

    def test_cancelled_status(self) -> None:
        """Test cancelled trademark status."""
        data = {
            "serialNumber": "97123456",
            "registrationNumber": "1234567",
            "cancellationDate": "2023-06-01",
        }
        status = TrademarkStatus.model_validate(data)
        assert status.is_live is False
        assert status.is_registered is False
