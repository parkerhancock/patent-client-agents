"""Tests for USPTO TSDR models."""

from patent_client_agents.uspto_tsdr import (
    GoodsServices,
    Owner,
    TrademarkStatus,
    TsdrDocument,
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


class TestTsdrDocument:
    """Tests for TsdrDocument model."""

    def test_basic_parsing(self) -> None:
        """Test basic document parsing."""
        data = {
            "docId": "DOC123",
            "docType": "OA",
            "docDate": "2023-01-15",
            "description": "Office Action",
            "pageCount": 5,
        }
        doc = TsdrDocument.model_validate(data)
        assert doc.doc_id == "DOC123"
        assert doc.doc_type == "OA"
        assert doc.page_count == 5


class TestOwner:
    """Tests for Owner model."""

    def test_basic_parsing(self) -> None:
        """Test owner parsing."""
        data = {
            "name": "Test Company Inc.",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
        }
        owner = Owner.model_validate(data)
        assert owner.name == "Test Company Inc."
        assert owner.city == "San Francisco"


class TestGoodsServices:
    """Tests for GoodsServices model."""

    def test_basic_parsing(self) -> None:
        """Test goods/services parsing."""
        data = {
            "classNumber": 9,
            "classDescription": "Computer software",
        }
        gs = GoodsServices.model_validate(data)
        assert gs.class_number == 9
        assert gs.class_description == "Computer software"
