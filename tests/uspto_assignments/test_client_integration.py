"""VCR-recorded integration tests for UsptoAssignmentsClient."""

import pytest

from ip_tools.uspto_assignments import AssignmentRecord, UsptoAssignmentsClient


class TestAssignmentsIntegration:
    """Integration tests for USPTO Assignment Search API."""

    @pytest.mark.vcr
    async def test_assignments_for_patent(self):
        async with UsptoAssignmentsClient() as client:
            records = await client.assignments_for_patent("7654321")

        assert isinstance(records, list)
        assert len(records) > 0
        record = records[0]
        assert isinstance(record, AssignmentRecord)
        assert record.conveyance_text is not None
        assert record.reel_number is not None
        assert record.frame_number is not None
        # Should have at least one patent number in the record
        assert len(record.patent_numbers) > 0

    @pytest.mark.vcr
    async def test_assignments_for_assignee(self):
        async with UsptoAssignmentsClient() as client:
            records = await client.assignments_for_assignee("Google")

        assert isinstance(records, list)
        assert len(records) > 0
        record = records[0]
        assert isinstance(record, AssignmentRecord)
        assert record.conveyance_text is not None
        # Assignee records should have assignees
        assert len(record.assignees) > 0
        assignee = record.assignees[0]
        assert assignee.name is not None

    @pytest.mark.vcr
    async def test_assignments_for_application(self):
        async with UsptoAssignmentsClient() as client:
            records = await client.assignments_for_application("16123456")

        assert isinstance(records, list)
        # This application may or may not have assignments;
        # just verify we get a valid list of AssignmentRecord
        for record in records:
            assert isinstance(record, AssignmentRecord)

    @pytest.mark.vcr
    async def test_assignments_for_patent_has_assignors_and_assignees(self):
        async with UsptoAssignmentsClient() as client:
            records = await client.assignments_for_patent("7654321")

        # At least one record should have both assignors and assignees
        has_both = any(r.assignors and r.assignees for r in records)
        assert has_both, "Expected at least one record with both assignors and assignees"

        # Verify party fields
        for record in records:
            for party in record.assignors + record.assignees:
                assert party.name is not None
