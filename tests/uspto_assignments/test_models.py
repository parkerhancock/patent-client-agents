"""Tests for USPTO Assignments Pydantic models."""

from datetime import datetime

from ip_tools.uspto_assignments.models import AssignmentParty, AssignmentRecord


class TestAssignmentParty:
    """Tests for AssignmentParty model."""

    def test_basic_party(self):
        """Test creating a basic party."""
        party = AssignmentParty(
            name="ACME Corporation",
            city="San Francisco",
            state="CA",
            country="US",
        )
        assert party.name == "ACME Corporation"
        assert party.city == "San Francisco"
        assert party.state == "CA"
        assert party.country == "US"

    def test_full_address(self):
        """Test party with full address."""
        party = AssignmentParty(
            name="Tech Corp",
            address1="123 Main St",
            address2="Suite 100",
            city="Seattle",
            state="WA",
            country="US",
            postcode="98101",
        )
        assert party.address1 == "123 Main St"
        assert party.address2 == "Suite 100"
        assert party.postcode == "98101"

    def test_minimal_party(self):
        """Test party with only required field."""
        party = AssignmentParty(name="Inventor Name")
        assert party.name == "Inventor Name"
        assert party.address1 is None
        assert party.city is None


class TestAssignmentRecord:
    """Tests for AssignmentRecord model."""

    def test_basic_record(self):
        """Test creating a basic assignment record."""
        record = AssignmentRecord(
            reel_number="12345",
            frame_number="0001",
            conveyance_text="ASSIGNMENT OF ASSIGNORS INTEREST",
        )
        assert record.reel_number == "12345"
        assert record.frame_number == "0001"
        assert record.conveyance_text == "ASSIGNMENT OF ASSIGNORS INTEREST"

    def test_record_with_dates(self):
        """Test record with execution and recorded dates."""
        record = AssignmentRecord(
            reel_number="12345",
            frame_number="0001",
            recorded_date=datetime(2023, 6, 15),
            execution_date=datetime(2023, 6, 1),
        )
        assert record.recorded_date == datetime(2023, 6, 15)
        assert record.execution_date == datetime(2023, 6, 1)

    def test_record_with_parties(self):
        """Test record with assignors and assignees."""
        assignor = AssignmentParty(name="Original Owner", country="US")
        assignee = AssignmentParty(name="New Owner Corp", country="US")

        record = AssignmentRecord(
            reel_number="12345",
            frame_number="0001",
            assignors=[assignor],
            assignees=[assignee],
        )
        assert len(record.assignors) == 1
        assert len(record.assignees) == 1
        assert record.assignors[0].name == "Original Owner"
        assert record.assignees[0].name == "New Owner Corp"

    def test_record_with_patent_numbers(self):
        """Test record with patent and application numbers."""
        record = AssignmentRecord(
            reel_number="12345",
            frame_number="0001",
            patent_numbers=["8830957", "9123456"],
            application_numbers=["16123456", "16789012"],
        )
        assert len(record.patent_numbers) == 2
        assert len(record.application_numbers) == 2
        assert "8830957" in record.patent_numbers

    def test_default_lists(self):
        """Test that list fields default to empty."""
        record = AssignmentRecord()
        assert record.assignors == []
        assert record.assignees == []
        assert record.patent_numbers == []
        assert record.application_numbers == []
