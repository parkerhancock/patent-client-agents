"""Envelope-shape tests for the migrated trademark-assignment MCP tool (Row 8).

Verifies the §5.9 contract for ``search_trademark_assignments`` — lean
projection (§5.5), cross-references to register tools (§5.6), and
provenance pointing at the Trademark Assignment Center.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.trademarks import search_trademark_assignments
from patent_client_agents.uspto_trademark_assignments.models import (
    Assignor,
    TrademarkAssignmentRecord,
    TrademarkProperty,
)


def _make_record(reel: int = 9006, frame: str = "0093") -> TrademarkAssignmentRecord:
    return TrademarkAssignmentRecord.model_validate(
        {
            "reelNumber": reel,
            "frameNumber": frame,
            "assignorExecutionDate": "2024-03-15",
            "noOfProperties": 1,
            "assignors": [
                Assignor.model_validate(
                    {"assignorName": "Alice Inventor", "executionDate": "2024-03-15"}
                )
            ],
            "assignees": ["Acme Corp"],
            "properties": [
                TrademarkProperty.model_validate(
                    {
                        "serialNumber": 97123456,
                        "registrationNumber": 1234567,
                        "mark": "ACME",
                    }
                )
            ],
        }
    )


@pytest.mark.asyncio
async def test_search_trademark_assignments_returns_lean_envelope():
    records = [_make_record(reel=9006 + i, frame=f"{93 + i:04d}") for i in range(2)]

    with patch("patent_client_agents.mcp.tools.trademarks.TrademarkAssignmentClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_by_assignee = AsyncMock(return_value=records)
        result = await search_trademark_assignments(query="Acme Corp", by="assignee")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Trademark Assignment Center"
    assert "assignment-api.uspto.gov" in result.provenance.source_url
    assert len(result.items) == 2
    first = result.items[0]
    assert first["reel_frame"] == "9006/0093"
    assert first["assignor"] == "Alice Inventor"
    assert first["assignee"] == "Acme Corp"
    assert first["serial_number"] == 97123456
    assert first["mark"] == "ACME"
    assert "properties" not in first


@pytest.mark.asyncio
async def test_search_trademark_assignments_full_passes_through():
    records = [_make_record()]
    with patch("patent_client_agents.mcp.tools.trademarks.TrademarkAssignmentClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_by_serial = AsyncMock(return_value=records)
        result = await search_trademark_assignments(query="97123456", by="serial_number", full=True)

    assert "properties" in result.items[0]
    assert result.items[0]["assignees"] == ["Acme Corp"]


@pytest.mark.asyncio
async def test_search_trademark_assignments_unknown_axis_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await search_trademark_assignments(query="x", by="bogus")


def test_docstring_carries_related_tools_line():
    """§5.6: search_trademark_assignments must cross-reference register tools."""
    doc = search_trademark_assignments.__doc__ or ""
    assert "Related tools:" in doc
    assert "get_trademark" in doc
    assert "get_trademark_status" in doc
