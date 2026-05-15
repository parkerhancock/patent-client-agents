"""Envelope-shape tests for the migrated PTAB MCP tools (Row 5).

Verifies the §5.9 contract for ``search_ptab`` (type-multiplexed),
``get_ptab`` (with §5.4 list-accept), and ``list_ptab_children``. Mocks
``UsptoOdpClient`` at the boundary — we test envelope shape and the
per-type lean projections, not the upstream API.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.uspto import (
    get_ptab,
    list_ptab_children,
    search_ptab,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — minimal Pydantic models that mimic ODP PTAB response shapes
# ──────────────────────────────────────────────────────────────────────


class _FakeResponse(BaseModel):
    payload: dict = {}

    def model_dump(self, **kwargs):  # type: ignore[override]
        return self.payload


def _make_proceeding(trial_number: str, status: str = "Instituted") -> dict:
    return {
        "trialNumber": trial_number,
        "trialMetaData": {
            "trialTypeCode": "IPR",
            "trialStatusCategory": status,
            "petitionFilingDate": "2024-01-15",
            "institutionDecisionDate": "2024-07-15",
            "latestDecisionDate": "2025-07-15",
            "terminationDate": None,
        },
        "patentOwnerData": {
            "patentNumber": "11234567",
            "applicationNumberText": "16123456",
            "patentOwnerName": "Acme Corp",
        },
        "regularPetitionerData": {"realPartyInInterestName": "Beta Inc"},
    }


def _make_trial_document(trial_number: str, doc_id: str) -> dict:
    return {
        "trialNumber": trial_number,
        "documentData": {
            "documentIdentifier": doc_id,
            "documentTypeDescriptionText": "Patent Owner Response",
            "documentTitleText": "Patent Owner Preliminary Response",
            "documentFilingDate": "2024-04-15",
            "filingPartyCategory": "Patent Owner",
        },
    }


def _make_trial_decision(trial_number: str, doc_id: str) -> dict:
    return {
        "trialNumber": trial_number,
        "documentData": {
            "documentIdentifier": doc_id,
            "documentTypeDescriptionText": "Final Written Decision",
            "documentTitleText": "Final Written Decision",
            "documentFilingDate": "2025-07-15",
        },
        "decisionData": {
            "decisionTypeCategory": "FWD",
            "decisionIssueDate": "2025-07-15",
            "trialOutcomeCategory": "All claims unpatentable",
        },
    }


def _make_appeal_decision(doc_id: str, appeal_number: str = "2024-001234") -> dict:
    return {
        "appealNumber": appeal_number,
        "documentData": {"documentIdentifier": doc_id},
        "decisionData": {
            "decisionIssueDate": "2025-05-15",
            "decisionTypeCategory": "Decision",
            "appealOutcomeCategory": "Affirmed",
        },
        "appellantData": {
            "applicationNumberText": "16123456",
            "patentOwnerName": "Acme Corp",
        },
    }


def _make_interference_decision(doc_id: str, intf: str = "105,123") -> dict:
    return {
        "interferenceNumber": intf,
        "decisionDocumentData": {
            "documentIdentifier": doc_id,
            "decisionIssueDate": "2014-03-15",
            "decisionTypeCategory": "Final Decision",
            "interferenceOutcomeCategory": "Judgment for senior party",
        },
        "seniorPartyData": {"realPartyInInterestName": "First Inventor LLC"},
        "juniorPartyData": {"realPartyInInterestName": "Second Inventor LLC"},
    }


# ──────────────────────────────────────────────────────────────────────
# search_ptab — type-multiplexed
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ptab_proceeding_returns_lean_envelope():
    payload = {
        "count": 12,
        "patentTrialProceedingDataBag": [
            _make_proceeding("IPR2024-00001"),
            _make_proceeding("IPR2024-00002", status="Terminated"),
        ],
    }
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_trial_proceedings = AsyncMock(return_value=fake)
        result = await search_ptab(type="proceeding", query="Acme", limit=2)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Open Data Portal"
    assert "/api/v1/ptab/proceedings/search" in result.provenance.source_url
    assert len(result.items) == 2
    assert result.more_available is True
    assert "PTAB proceeding" in result.summary
    assert "2 of 12" in result.summary
    # Lean projection: every hit has the trial_number, status, etc., not
    # the upstream trialMetaData blob.
    first = result.items[0]
    assert first["type"] == "proceeding"
    assert first["trial_number"] == "IPR2024-00001"
    assert first["status"] == "Instituted"
    assert first["patent_owner"] == "Acme Corp"
    assert "trialMetaData" not in first


@pytest.mark.asyncio
async def test_search_ptab_trial_decision_full_passes_through():
    payload = {
        "count": 1,
        "patentTrialDocumentDataBag": [_make_trial_decision("IPR2024-00001", "FWD123")],
    }
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_trial_decisions = AsyncMock(return_value=fake)
        result = await search_ptab(type="trial_decision", query="*", limit=25, full=True)

    assert isinstance(result, ListEnvelope)
    # When full=True, hits keep the upstream documentData structure.
    assert "documentData" in result.items[0]
    assert result.more_available is False  # 1 of 1


@pytest.mark.asyncio
async def test_search_ptab_unknown_type_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await search_ptab(type="bogus", query="x")


# ──────────────────────────────────────────────────────────────────────
# get_ptab — §5.4 list-accept
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ptab_proceeding_single_string_returns_list_envelope():
    payload = {"patentTrialProceedingDataBag": [_make_proceeding("IPR2024-00001")]}
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trial_proceeding = AsyncMock(return_value=fake)
        result = await get_ptab(type="proceeding", identifier="IPR2024-00001")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert "PTAB trial IPR2024-00001" in result.summary
    assert "Acme Corp" in result.summary
    assert "/api/v1/ptab/proceedings/IPR2024-00001" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_ptab_list_preserves_order():
    """Multi-identifier fan-out must return items in the input order."""
    trial_ids = ["IPR2024-00001", "IPR2024-00002", "IPR2024-00003"]
    responses = [
        _FakeResponse(payload={"patentTrialProceedingDataBag": [_make_proceeding(t)]})
        for t in trial_ids
    ]

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trial_proceeding = AsyncMock(side_effect=responses)
        result = await get_ptab(type="proceeding", identifier=trial_ids)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    returned = [item["patentTrialProceedingDataBag"][0]["trialNumber"] for item in result.items]
    assert returned == trial_ids
    # Multi-id provenance points at the collection URL.
    assert result.provenance.source_url.endswith("/api/v1/ptab/proceedings")
    assert "Fetched 3 PTAB proceeding records" in result.summary


@pytest.mark.asyncio
async def test_get_ptab_appeal_decision_single():
    payload = {"patentAppealDataBag": [_make_appeal_decision("DEC456")]}
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_appeal_decision = AsyncMock(return_value=fake)
        result = await get_ptab(type="appeal_decision", identifier="DEC456")

    assert isinstance(result, ListEnvelope)
    assert "PTAB appeal decision DEC456" in result.summary
    assert "Affirmed" in result.summary
    assert "/api/v1/ptab/appeal-decisions/DEC456" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_ptab_interference_decision_single():
    payload = {"patentInterferenceDataBag": [_make_interference_decision("INT789")]}
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_interference_decision = AsyncMock(return_value=fake)
        result = await get_ptab(type="interference_decision", identifier="INT789")

    assert isinstance(result, ListEnvelope)
    assert "PTAB interference decision INT789" in result.summary
    assert "Judgment for senior party" in result.summary


@pytest.mark.asyncio
async def test_get_ptab_unknown_type_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await get_ptab(type="bogus", identifier="x")


# ──────────────────────────────────────────────────────────────────────
# list_ptab_children
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_ptab_children_trial_decisions_returns_list_envelope():
    decisions_payload = {
        "patentTrialDocumentDataBag": [
            _make_trial_decision("IPR2024-00001", f"DEC{i}") for i in range(3)
        ]
    }
    fake = _FakeResponse(payload=decisions_payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trial_decisions_by_trial = AsyncMock(return_value=fake)
        result = await list_ptab_children(parent_type="trial", parent_identifier="IPR2024-00001")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    assert "IPR2024-00001" in result.summary
    assert all(it["type"] == "trial_decision" for it in result.items)
    assert "/api/v1/ptab/trials/IPR2024-00001/decisions" in result.provenance.source_url


@pytest.mark.asyncio
async def test_list_ptab_children_trial_both_combines_decisions_and_documents():
    decisions_payload = {
        "patentTrialDocumentDataBag": [_make_trial_decision("IPR2024-00001", "DEC1")]
    }
    documents_payload = {
        "patentTrialDocumentDataBag": [
            _make_trial_document("IPR2024-00001", f"DOC{i}") for i in range(2)
        ]
    }
    fake_dec = _FakeResponse(payload=decisions_payload)
    fake_doc = _FakeResponse(payload=documents_payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trial_decisions_by_trial = AsyncMock(return_value=fake_dec)
        mock_client.get_trial_documents_by_trial = AsyncMock(return_value=fake_doc)
        result = await list_ptab_children(
            parent_type="trial", parent_identifier="IPR2024-00001", include="both"
        )

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    types = [it["type"] for it in result.items]
    assert types.count("trial_decision") == 1
    assert types.count("trial_document") == 2


@pytest.mark.asyncio
async def test_list_ptab_children_application_returns_appeal_decisions():
    payload = {"patentAppealDataBag": [_make_appeal_decision(f"DEC{i}") for i in range(2)]}
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_appeal_decisions_by_number = AsyncMock(return_value=fake)
        result = await list_ptab_children(parent_type="application", parent_identifier="16123456")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 2
    assert all(it["type"] == "appeal_decision" for it in result.items)
    assert "/api/v1/ptab/appeals/by-application/16123456" in result.provenance.source_url


@pytest.mark.asyncio
async def test_list_ptab_children_invalid_parent_type_raises():
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await list_ptab_children(parent_type="bogus", parent_identifier="x")


# ──────────────────────────────────────────────────────────────────────
# §5.13 — docstring expands "PTAB" on first use
# ──────────────────────────────────────────────────────────────────────


def test_docstrings_expand_ptab_acronym():
    """The first sentence of every PTAB tool must expand the acronym."""
    for tool in (search_ptab, get_ptab, list_ptab_children):
        doc = tool.__doc__ or ""
        first_sentence = doc.split(".")[0]
        assert "Patent Trial and Appeal Board" in first_sentence, (
            f"{tool.__name__} first sentence does not expand 'PTAB': {first_sentence!r}"
        )


# ──────────────────────────────────────────────────────────────────────
# §5.6 — Related tools cross-references
# ──────────────────────────────────────────────────────────────────────


def test_docstrings_carry_related_tools_lines():
    """§5.6: every PTAB tool docstring ends with a Related tools: line."""
    for tool in (search_ptab, get_ptab, list_ptab_children):
        doc = tool.__doc__ or ""
        assert "Related tools:" in doc, f"{tool.__name__} missing Related tools: line"
