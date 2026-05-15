"""Envelope-shape tests for the migrated USPTO patent-assignment MCP tool (Row 8).

Verifies the §5.9 contract for ``search_patent_assignments`` — lean
projection (§5.5), cross-references to register tools (§5.6), and
provenance pointing at the Assignment Center API base.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.patent_assignments import search_patent_assignments
from patent_client_agents.uspto_assignments.models import (
    AssignmentRecord,
    Assignor,
    Property,
    SearchResults,
)


def _make_record(
    reel: int = 12345, frame: int = 67, *, conveyance: str = "ASSIGNMENT"
) -> AssignmentRecord:
    return AssignmentRecord.model_validate(
        {
            "reelNumber": reel,
            "frameNumber": frame,
            "conveyance": conveyance,
            "assignorExecutionDate": "2024-03-15",
            "noOfProperties": 1,
            "assignors": [
                Assignor.model_validate(
                    {"assignorName": "Alice Inventor", "executionDate": "2024-03-15"}
                )
            ],
            "assignees": ["Acme Corp"],
            "properties": [
                Property.model_validate(
                    {
                        "applicationNumber": "16123456",
                        "patentNumber": "11234567",
                        "publicationNumber": "US20230012345A1",
                        "inventionTitle": "Method for foo",
                    }
                )
            ],
        }
    )


@pytest.mark.asyncio
async def test_search_patent_assignments_returns_lean_envelope():
    records = [_make_record(reel=100 + i, frame=10 + i) for i in range(3)]
    results = SearchResults(records=records, total=42, truncated=False)

    with patch(
        "patent_client_agents.mcp.tools.patent_assignments.AssignmentCenterClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=results)
        result = await search_patent_assignments(query="Acme Corp", by="assignee")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Patent Assignment Center"
    assert "assignment-api.uspto.gov" in result.provenance.source_url
    assert "/PatentAssignmentSearch/" in result.provenance.source_url
    assert len(result.items) == 3
    assert "3 of 42 hits" in result.summary
    # Lean projection: practitioner-facing fields only.
    first = result.items[0]
    assert first["reel_frame"] == "100/10"
    assert first["conveyance"] == "ASSIGNMENT"
    assert first["assignor"] == "Alice Inventor"
    assert first["assignee"] == "Acme Corp"
    assert first["application_number"] == "16123456"
    assert first["patent_number"] == "11234567"
    # And the full upstream `properties` list is NOT in the stub.
    assert "properties" not in first


@pytest.mark.asyncio
async def test_search_patent_assignments_full_passes_through():
    records = [_make_record()]
    results = SearchResults(records=records, total=1, truncated=False)

    with patch(
        "patent_client_agents.mcp.tools.patent_assignments.AssignmentCenterClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=results)
        result = await search_patent_assignments(query="Acme", by="assignee", full=True)

    # full=True keeps the upstream model_dump structure.
    assert "properties" in result.items[0]
    assert result.items[0]["assignees"] == ["Acme Corp"]


@pytest.mark.asyncio
async def test_search_patent_assignments_truncated_summary_warns():
    records = [_make_record() for _ in range(2)]
    results = SearchResults(records=records, total=10000, truncated=True)

    with patch(
        "patent_client_agents.mcp.tools.patent_assignments.AssignmentCenterClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=results)
        result = await search_patent_assignments(query="*", by="assignee")

    assert result.more_available is True
    assert "USPTO capped" in result.summary


@pytest.mark.asyncio
async def test_search_patent_assignments_unknown_axis_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await search_patent_assignments(query="x", by="bogus")


def test_docstring_carries_related_tools_line():
    """§5.6: search_patent_assignments must cross-reference register tools."""
    doc = search_patent_assignments.__doc__ or ""
    assert "Related tools:" in doc
    assert "get_application" in doc
    assert "get_patent" in doc
