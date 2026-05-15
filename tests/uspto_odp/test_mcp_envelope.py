"""Envelope-shape tests for the migrated USPTO Applications MCP tools.

Verifies the §5.9 contract for ``search_applications``, ``get_application``,
and ``list_file_history``. These are the template referenced by
CONNECTOR_STANDARDS.md; the rest of the surface follows the same pattern.

Mocks ``UsptoOdpClient`` at the boundary — we're testing envelope shape,
not the upstream API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.uspto import (
    get_application,
    get_patent_assignment,
    list_file_history,
    search_applications,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal Pydantic models that mimic UsptoOdpClient return types
# ──────────────────────────────────────────────────────────────────────


class _FakeSearchResponse(BaseModel):
    count: int = 2
    patentBag: list[dict] = []

    def model_dump(self, **kwargs):  # type: ignore[override]
        return {"count": self.count, "patentBag": self.patentBag}


class _FakeApplicationResponse(BaseModel):
    patentBag: list[dict] = []

    def model_dump(self, **kwargs):  # type: ignore[override]
        return {"patentBag": self.patentBag}


class _FakeDocumentsResponse(BaseModel):
    documents: list[dict] = []

    def model_dump(self, **kwargs):  # type: ignore[override]
        return {"documents": self.documents}


def _make_application(appl: str, *, title: str = "Test", status: str = "Patented") -> dict:
    return {
        "applicationNumberText": appl,
        "applicationMetaData": {
            "inventionTitle": title,
            "applicationStatusDescriptionText": status,
            "filingDate": "2020-01-15",
            "patentNumber": "11234567",
            "grantDate": "2023-04-11",
        },
    }


# ──────────────────────────────────────────────────────────────────────
# search_applications
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_applications_returns_list_envelope():
    fake_results = [
        _make_application("16123456", title="First"),
        _make_application("17654321", title="Second"),
    ]
    fake_response = _FakeSearchResponse(count=42, patentBag=fake_results)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_applications = AsyncMock(return_value=fake_response)

        result = await search_applications(query="title:test", limit=2)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Open Data Portal"
    assert "/api/v1/patent/applications/search" in result.provenance.source_url
    assert len(result.items) == 2
    assert result.more_available is True  # 42 total, 2 shown, offset=0
    assert "USPTO Applications" in result.summary
    assert "2 of 42" in result.summary


@pytest.mark.asyncio
async def test_search_applications_more_available_false_when_exhausted():
    fake_response = _FakeSearchResponse(
        count=2, patentBag=[_make_application("1"), _make_application("2")]
    )
    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.search_applications = AsyncMock(return_value=fake_response)
        result = await search_applications(query="*", limit=25)
    assert result.more_available is False


# ──────────────────────────────────────────────────────────────────────
# get_application — §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_application_single_string_returns_list_envelope():
    record = _make_application("16123456", title="Blockchain authentication")
    fake_response = _FakeApplicationResponse(patentBag=[record])

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_application = AsyncMock(return_value=fake_response)

        result = await get_application(application_number="16123456")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.provenance.source_name == "USPTO Open Data Portal"
    assert "/16123456" in result.provenance.source_url
    assert "16123456" in result.summary
    assert "Blockchain authentication" in result.summary


@pytest.mark.asyncio
async def test_get_application_list_returns_list_envelope():
    responses = [
        _FakeApplicationResponse(patentBag=[_make_application(n)])
        for n in ["16123456", "17654321", "18900000"]
    ]

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_application = AsyncMock(side_effect=responses)

        result = await get_application(application_number=["16123456", "17654321", "18900000"])

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    assert "3 USPTO applications" in result.summary
    # Multi-fetch points provenance at the collection URL, not a single record.
    assert result.provenance.source_url.endswith("/api/v1/patent/applications")


@pytest.mark.asyncio
async def test_get_application_fanout_preserves_order():
    """Numbers in the request order should match numbers in the response order."""
    appls = ["A1", "B2", "C3"]
    responses = [_FakeApplicationResponse(patentBag=[_make_application(a)]) for a in appls]

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_application = AsyncMock(side_effect=responses)

        result = await get_application(application_number=appls)

    returned = [item["patentBag"][0]["applicationNumberText"] for item in result.items]
    assert returned == appls


# ──────────────────────────────────────────────────────────────────────
# list_file_history
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_file_history_returns_list_envelope():
    fake_response = _FakeDocumentsResponse(
        documents=[
            {
                "documentIdentifier": "ABC123",
                "documentCode": "CTNF",
                "documentCodeDescriptionText": "Non-Final Rejection",
                "officialDate": "2022-08-15",
                "directionCategory": "outgoing",
                "pageCount": 12,
                "downloadOptionBag": [
                    {"mimeTypeIdentifier": "PDF"},
                    {"mimeTypeIdentifier": "MS_WORD"},
                ],
            },
            {
                "documentIdentifier": "DEF456",
                "documentCode": "REM",
                "documentCodeDescriptionText": "Applicant Remarks",
                "officialDate": "2022-11-10",
                "directionCategory": "incoming",
                "pageCount": 8,
                "downloadOptionBag": [{"mimeTypeIdentifier": "PDF"}],
            },
        ],
    )

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__aenter__.return_value
        mock_client.get_documents = AsyncMock(return_value=fake_response)

        result = await list_file_history(application_number="16123456")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 2
    assert "16123456" in result.summary
    assert "2 file-history documents" in result.summary
    # Lean shape per §5.5: only the projected fields, not the raw ODP record.
    assert set(result.items[0].keys()) == {
        "document_identifier",
        "code",
        "description",
        "date",
        "direction",
        "page_count",
        "formats",
    }
    assert result.items[0]["formats"] == ["PDF", "MS_WORD"]
    assert "/api/v1/patent/applications/16123456/documents" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# get_patent_assignment — §5.4 list-accept (Row 8)
# ──────────────────────────────────────────────────────────────────────


class _FakeAssignmentResponse(BaseModel):
    payload: dict = {}

    def model_dump(self, **kwargs):  # type: ignore[override]
        return self.payload


def _make_assignment_response(appl: str, *, count: int = 1) -> dict:
    return {
        "applicationNumberText": appl,
        "assignmentBag": [
            {
                "reelNumber": 50000 + i,
                "frameNumber": 100 + i,
                "reelAndFrameNumber": f"{50000 + i}/{100 + i}",
                "conveyanceText": "ASSIGNMENT OF ASSIGNORS INTEREST",
                "assignorBag": [{"assignorNameText": "Alice Inventor"}],
                "assigneeBag": [{"assigneeNameText": "Acme Corp"}],
                "assignmentRecordedDate": "2024-03-20",
            }
            for i in range(count)
        ],
    }


@pytest.mark.asyncio
async def test_get_patent_assignment_single_string_returns_list_envelope():
    payload = _make_assignment_response("16123456", count=2)
    fake = _FakeAssignmentResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_assignment = AsyncMock(return_value=fake)
        result = await get_patent_assignment(application_number="16123456")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.provenance.source_name == "USPTO Open Data Portal"
    assert "/api/v1/patent/applications/16123456/assignment" in result.provenance.source_url
    assert "16123456" in result.summary
    assert "2 assignments on record" in result.summary


@pytest.mark.asyncio
async def test_get_patent_assignment_list_preserves_order():
    appls = ["16123456", "17654321", "18900000"]
    responses = [_FakeAssignmentResponse(payload=_make_assignment_response(a)) for a in appls]

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_assignment = AsyncMock(side_effect=responses)
        result = await get_patent_assignment(application_number=appls)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    returned = [item["applicationNumberText"] for item in result.items]
    assert returned == appls
    assert result.provenance.source_url.endswith("/api/v1/patent/applications/assignment")
    assert "Fetched assignments for 3 applications" in result.summary
