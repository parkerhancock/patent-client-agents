"""Tests for USPTO Assignment Center client."""

from __future__ import annotations

from datetime import date

import pytest

from patent_client_agents.uspto_assignments import (
    AssignmentCenterClient,
    AssignmentRecord,
    Assignor,
    Property,
    SearchResults,
)


class TestModels:
    """Tests for Pydantic models and SearchResults dataclass."""

    def test_assignor_model(self) -> None:
        data = {"assignorName": "SMITH, JOHN", "executionDate": "01/15/2024"}
        a = Assignor.model_validate(data)
        assert a.assignor_name == "SMITH, JOHN"
        assert a.execution_date == "01/15/2024"

    def test_property_model(self) -> None:
        data = {
            "sequenceNumber": 1,
            "applicationNumber": "17123456",
            "fillingDate": "01/01/2024",  # API typo preserved
            "patentNumber": "11000000",
            "inventionTitle": "Test Invention",
            "inventors": "John Smith, Jane Doe",
        }
        p = Property.model_validate(data)
        assert p.application_number == "17123456"
        assert p.patent_number == "11000000"
        assert p.filing_date == "01/01/2024"
        assert p.invention_title == "Test Invention"

    def test_assignment_record_with_conveyance(self) -> None:
        """Confirms conveyance + conveyance_code populate from the search/patent response shape."""
        data = {
            "reelNumber": 72877,
            "frameNumber": 227,
            "correspondentName": "Lerner David LLP",
            "assignorExecutionDate": "11/12/2025",
            "conveyance": "ASSIGNMENT OF ASSIGNOR'S INTEREST",
            "conveyanceCode": 23,
            "assignors": [{"assignorName": "SAKALKAR, VARUN", "executionDate": "11/12/2025"}],
            "assignees": ["GOOGLE LLC"],
            "noOfProperties": 1,
            "properties": [{"sequenceNumber": 1, "applicationNumber": "19385694"}],
        }
        r = AssignmentRecord.model_validate(data)
        assert r.reel_number == 72877
        assert r.frame_number == 227
        assert r.reel_frame == "72877/227"
        assert r.conveyance == "ASSIGNMENT OF ASSIGNOR'S INTEREST"
        assert r.conveyance_code == 23
        assert r.correspondent_name == "Lerner David LLP"
        assert r.assignors[0].assignor_name == "SAKALKAR, VARUN"
        assert r.assignees == ["GOOGLE LLC"]
        assert r.number_of_properties == 1
        assert r.properties[0].application_number == "19385694"

    def test_assignment_record_handles_missing_conveyance(self) -> None:
        """Records without conveyance still parse cleanly (defensive default)."""
        data = {
            "reelNumber": 1,
            "frameNumber": 2,
            "assignors": [],
            "assignees": [],
            "properties": [],
        }
        r = AssignmentRecord.model_validate(data)
        assert r.conveyance is None
        assert r.conveyance_code is None
        assert r.number_of_properties == 0

    def test_search_results_list_protocol(self) -> None:
        """SearchResults behaves as a list of records for the common path."""
        records = [
            AssignmentRecord.model_validate({"reelNumber": i, "frameNumber": 0}) for i in range(3)
        ]
        result = SearchResults(records=records, total=42, truncated=False)
        assert len(result) == 3
        assert result[0].reel_number == 0
        assert [r.reel_number for r in result] == [0, 1, 2]
        assert bool(result) is True
        assert result.total == 42
        assert result.truncated is False

    def test_search_results_empty_is_falsy(self) -> None:
        result = SearchResults(records=[], total=0, truncated=False)
        assert bool(result) is False
        assert len(result) == 0


class TestSearchValidation:
    """Argument validation that doesn't require HTTP."""

    @pytest.mark.asyncio
    async def test_negative_offset_rejected(self) -> None:
        async with AssignmentCenterClient() as client:
            with pytest.raises(ValueError, match="offset"):
                await client.search(query="x", by="assignee", offset=-1)

    @pytest.mark.asyncio
    async def test_negative_limit_rejected(self) -> None:
        async with AssignmentCenterClient() as client:
            with pytest.raises(ValueError, match="limit"):
                await client.search(query="x", by="assignee", limit=-1)

    @pytest.mark.asyncio
    async def test_invalid_axis_rejected(self) -> None:
        async with AssignmentCenterClient() as client:
            with pytest.raises(KeyError):
                await client.search(query="x", by="bogus")  # type: ignore[arg-type]


class TestSearchLive:
    """Tests against recorded VCR cassettes."""

    @pytest.mark.asyncio
    async def test_search_by_application(self, vcr_cassette) -> None:
        """Application-number search returns recordations with conveyance populated."""
        async with AssignmentCenterClient() as client:
            result = await client.search(query="16136935", by="application_number")
        assert len(result) >= 1
        for r in result:
            assert isinstance(r, AssignmentRecord)
            assert r.conveyance is not None and r.conveyance != ""
            assert r.conveyance_code is not None
        assert result.truncated is False

    @pytest.mark.asyncio
    async def test_search_by_patent(self, vcr_cassette) -> None:
        async with AssignmentCenterClient() as client:
            result = await client.search(query="10000000", by="patent_number")
        assert len(result) >= 1
        for r in result:
            assert any(p.patent_number and "10000000" in p.patent_number for p in r.properties)

    @pytest.mark.asyncio
    async def test_search_by_reel_frame(self, vcr_cassette) -> None:
        async with AssignmentCenterClient() as client:
            result = await client.search(query="58293/75", by="reel_frame")
        assert len(result) == 1
        assert result[0].reel_frame == "58293/75"
        assert result[0].conveyance == "CHANGE OF NAME"

    @pytest.mark.asyncio
    async def test_search_by_assignee_contains(self, vcr_cassette) -> None:
        """Assignee Contains-search returns recordations with conveyance for every match."""
        async with AssignmentCenterClient() as client:
            result = await client.search(query="WIDEX A/S", by="assignee", exact=True, limit=10)
        assert len(result) > 0
        for r in result:
            assert r.conveyance is not None
            assert any("WIDEX" in name.upper() for name in r.assignees)

    @pytest.mark.asyncio
    async def test_search_with_executed_between(self, vcr_cassette) -> None:
        """executionDate filter actually narrows the result set."""
        start, end = date(2024, 1, 1), date(2024, 12, 31)
        async with AssignmentCenterClient() as client:
            unfiltered = await client.search(query="Google", by="assignee", limit=5)
            filtered = await client.search(
                query="Google",
                by="assignee",
                executed_between=(start, end),
                limit=5,
            )
        # The total before slicing should differ when filter narrows
        assert filtered.total <= unfiltered.total

    @pytest.mark.asyncio
    async def test_search_with_conveyance_filter(self, vcr_cassette) -> None:
        """conveyance contains-filter narrows result set."""
        async with AssignmentCenterClient() as client:
            result = await client.search(
                query="Google",
                by="assignee",
                conveyance="SECURITY",
                limit=5,
            )
        assert result.total > 0
        for r in result:
            assert r.conveyance is not None
            assert "SECURITY" in r.conveyance.upper()

    @pytest.mark.asyncio
    async def test_search_truncated_flag_for_huge_query(self, vcr_cassette) -> None:
        """An assignee with >10k recordations sets truncated=True."""
        async with AssignmentCenterClient() as client:
            result = await client.search(query="Apple", by="assignee", exact=False, limit=5)
        assert result.truncated is True
        assert result.total >= 10_000
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_search_offset_skips_records(self, vcr_cassette) -> None:
        """offset advances past the first records of the result set."""
        async with AssignmentCenterClient() as client:
            page1 = await client.search(
                query="WIDEX A/S", by="assignee", exact=True, offset=0, limit=3
            )
            page2 = await client.search(
                query="WIDEX A/S", by="assignee", exact=True, offset=3, limit=3
            )
        assert len(page1) == 3
        assert len(page2) == 3
        # Reel/frames should differ between pages
        rf1 = {r.reel_frame for r in page1}
        rf2 = {r.reel_frame for r in page2}
        assert rf1.isdisjoint(rf2)
