"""Tests for USPTO Trademark Assignment models."""

from patent_client_agents.uspto_trademark_assignments import (
    Assignor,
    TrademarkAssignmentRecord,
    TrademarkAssignmentSearchResponse,
    TrademarkProperty,
)


class TestTrademarkProperty:
    """Tests for TrademarkProperty model."""

    def test_basic_parsing(self) -> None:
        """Test basic property parsing."""
        data = {
            "sequenceNumber": 1,
            "serialNumber": 88874668,
            "currentOwner": "RAC7 GAMES INC.",
            "mark": "SNEAKY SASQUATCH",
            "applicationFilingDate": "04/16/2020",
            "internationalRegistrationNumber": None,
            "registrationDate": "11/24/2020",
            "registrationNumber": 6204399,
            "registrantName": None,
        }
        prop = TrademarkProperty.model_validate(data)
        assert prop.serial_number == 88874668
        assert prop.mark == "SNEAKY SASQUATCH"
        assert prop.registration_number == 6204399
        assert prop.current_owner == "RAC7 GAMES INC."


class TestAssignor:
    """Tests for Assignor model."""

    def test_basic_parsing(self) -> None:
        """Test assignor parsing."""
        data = {
            "assignorName": "RAC7 GAMES ULC",
            "executionDate": "07/22/2025",
        }
        assignor = Assignor.model_validate(data)
        assert assignor.assignor_name == "RAC7 GAMES ULC"
        assert assignor.execution_date == "07/22/2025"


class TestTrademarkAssignmentRecord:
    """Tests for TrademarkAssignmentRecord model."""

    def test_basic_parsing(self) -> None:
        """Test basic record parsing."""
        data = {
            "reelNumber": 9006,
            "frameNumber": "0093",
            "assignorExecutionDate": "07/22/2025",
            "correspondentName": "PHILLIP A. ROSENBERG ",
            "domesticRepresentative": "",
            "assignors": [{"assignorName": "RAC7 GAMES ULC", "executionDate": "07/22/2025"}],
            "assignees": ["APPLE INC."],
            "noOfProperties": 1,
            "properties": [
                {
                    "sequenceNumber": 1,
                    "serialNumber": 88874668,
                    "currentOwner": "RAC7 GAMES INC.",
                    "mark": "SNEAKY SASQUATCH",
                    "applicationFilingDate": "04/16/2020",
                    "registrationDate": "11/24/2020",
                    "registrationNumber": 6204399,
                }
            ],
        }
        record = TrademarkAssignmentRecord.model_validate(data)
        assert record.reel_number == 9006
        assert record.frame_number == "0093"
        assert record.reel_frame == "9006/0093"
        assert record.assignees == ["APPLE INC."]
        assert len(record.assignors) == 1
        assert record.assignors[0].assignor_name == "RAC7 GAMES ULC"
        assert len(record.properties) == 1
        assert record.properties[0].mark == "SNEAKY SASQUATCH"


class TestTrademarkAssignmentSearchResponse:
    """Tests for TrademarkAssignmentSearchResponse model."""

    def test_basic_parsing(self) -> None:
        """Test response parsing."""
        data = {
            "searchCriteria": [{"property": "Apple", "searchBy": "assigneeName"}],
            "data": [
                {
                    "reelNumber": 9006,
                    "frameNumber": "0093",
                    "assignors": [],
                    "assignees": ["APPLE INC."],
                    "noOfProperties": 0,
                    "properties": [],
                }
            ],
        }
        response = TrademarkAssignmentSearchResponse.model_validate(data)
        assert response.count == 1
        assert len(response.search_criteria) == 1
        assert response.search_criteria[0].property == "Apple"

    def test_empty_response(self) -> None:
        """Test empty response parsing."""
        data = {"searchCriteria": [], "data": []}
        response = TrademarkAssignmentSearchResponse.model_validate(data)
        assert response.count == 0
