"""Tests for USPTO Trademark Search models."""

from datetime import UTC, datetime

from patent_client_agents.uspto_tmsearch.models import (
    TrademarkSearchResponse,
    TrademarkSearchResult,
)


class TestTrademarkSearchResult:
    """Tests for TrademarkSearchResult model."""

    def test_basic_fields(self) -> None:
        """Test basic field parsing."""
        result = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "registrationNumber": "1234567",
                "wordmark": "EXAMPLE",
                "alive": True,
                "ownerName": ["Example Corp"],
            }
        )
        assert result.serial_number == "97123456"
        assert result.registration_number == "1234567"
        assert result.wordmark == "EXAMPLE"
        assert result.status_live is True
        assert result.owner_name == ["Example Corp"]

    def test_date_parsing(self) -> None:
        """Test date field parsing."""
        result = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "alive": True,
                "filedDate": "2023-01-15T00:00:00Z",
                "registrationDate": "2024-06-01T12:00:00Z",
            }
        )
        assert result.filed_date == datetime(2023, 1, 15, 0, 0, 0, tzinfo=UTC)
        assert result.registration_date == datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)

    def test_date_parsing_invalid(self) -> None:
        """Test invalid date handling."""
        result = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "alive": True,
                "filedDate": "invalid-date",
            }
        )
        assert result.filed_date is None

    def test_list_from_string(self) -> None:
        """Test comma-separated strings are converted to lists."""
        result = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "alive": True,
                "designCode": "010103, 010110, 050905",
                "internationalClass": "25, 35",
            }
        )
        assert result.design_code == ["010103", "010110", "050905"]
        assert result.international_class == ["25", "35"]

    def test_is_live_property(self) -> None:
        """Test is_live property."""
        result = TrademarkSearchResult.model_validate({"serialNumber": "97123456", "alive": True})
        assert result.is_live is True

        result2 = TrademarkSearchResult.model_validate({"serialNumber": "97123456", "alive": False})
        assert result2.is_live is False

    def test_is_registered_property(self) -> None:
        """Test is_registered property."""
        # Registered and not canceled
        result = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "registrationNumber": "1234567",
                "alive": True,
            }
        )
        assert result.is_registered is True

        # No registration number
        result2 = TrademarkSearchResult.model_validate({"serialNumber": "97123456", "alive": True})
        assert result2.is_registered is False

        # Canceled
        result3 = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "registrationNumber": "1234567",
                "alive": False,
                "cancelDate": "2024-01-01T00:00:00Z",
            }
        )
        assert result3.is_registered is False

    def test_primary_owner_property(self) -> None:
        """Test primary_owner property."""
        result = TrademarkSearchResult.model_validate(
            {
                "serialNumber": "97123456",
                "alive": True,
                "ownerName": ["Primary Owner", "Secondary Owner"],
            }
        )
        assert result.primary_owner == "Primary Owner"

        result2 = TrademarkSearchResult.model_validate({"serialNumber": "97123456", "alive": True})
        assert result2.primary_owner is None


class TestTrademarkSearchResponse:
    """Tests for TrademarkSearchResponse model."""

    def test_empty_response(self) -> None:
        """Test empty response."""
        response = TrademarkSearchResponse(total=0, results=[], query_time_ms=5)
        assert response.total == 0
        assert response.count == 0
        assert response.results == []

    def test_with_results(self) -> None:
        """Test response with results."""
        results = [
            TrademarkSearchResult.model_validate(
                {"serialNumber": "97123456", "alive": True, "wordmark": "MARK1"}
            ),
            TrademarkSearchResult.model_validate(
                {"serialNumber": "97123457", "alive": False, "wordmark": "MARK2"}
            ),
        ]
        response = TrademarkSearchResponse(total=100, results=results, query_time_ms=50)
        assert response.total == 100
        assert response.count == 2
        assert len(response.results) == 2
        assert response.results[0].wordmark == "MARK1"
