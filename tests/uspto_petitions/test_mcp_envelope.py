"""Envelope-shape tests for the migrated USPTO Petitions MCP tools (Row 7).

Verifies the §5.9 contract for ``search_petitions`` and ``get_petition``
(with §5.4 list-accept + §5.8 parameter rename from ``petition_id`` to
``petition_number``). Mocks ``UsptoOdpClient`` at the boundary.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from law_tools_core.envelope import ListEnvelope, Provenance
from patent_client_agents.mcp.tools.uspto import get_petition, search_petitions


class _FakeResponse(BaseModel):
    payload: dict = {}

    def model_dump(self, **kwargs):  # type: ignore[override]
        return self.payload


def _make_petition(pid: str, *, application: str = "16123456") -> dict:
    return {
        "petitionDecisionRecordIdentifier": pid,
        "applicationNumberText": application,
        "patentNumber": "11234567",
        "decisionDate": "2024-06-15",
        "decisionTypeCode": "GRANTED",
        "decisionPetitionTypeCodeDescriptionText": "Petition to revive (unintentional)",
        "finalDecidingOfficeName": "Office of Petitions",
        "firstApplicantName": "Acme Corp",
        "inventionTitle": "Method and system for foo",
        "petitionMailDate": "2024-05-01",
        "statuteBag": ["35 USC 41"],
        "ruleBag": ["37 CFR 1.137"],
    }


# ──────────────────────────────────────────────────────────────────────
# search_petitions
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_petitions_returns_lean_envelope():
    payload = {
        "count": 7,
        "petitionDecisionDataBag": [_make_petition(f"P{i}") for i in range(3)],
    }
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_petitions = AsyncMock(return_value=fake)
        result = await search_petitions(query="revive", limit=3)

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Open Data Portal"
    assert "/api/v1/patent/petitions/search" in result.provenance.source_url
    assert len(result.items) == 3
    assert result.more_available is True  # 7 total, 3 shown, offset=0
    assert "3 of 7" in result.summary
    # Lean projection drops the upstream statute/rule bags.
    first = result.items[0]
    assert "statuteBag" not in first
    assert first["petition_decision_record_identifier"] == "P0"
    assert first["application_number"] == "16123456"
    assert first["petition_type"] == "Petition to revive (unintentional)"


@pytest.mark.asyncio
async def test_search_petitions_full_passes_through():
    payload = {
        "count": 1,
        "petitionDecisionDataBag": [_make_petition("P1")],
    }
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search_petitions = AsyncMock(return_value=fake)
        result = await search_petitions(query="x", full=True)

    assert "statuteBag" in result.items[0]
    assert result.more_available is False


# ──────────────────────────────────────────────────────────────────────
# get_petition — §5.4 list-accept + §5.8 parameter rename
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_petition_single_string_returns_list_envelope():
    payload = {"petitionDecisionDataBag": [_make_petition("P1")]}
    fake = _FakeResponse(payload=payload)

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_petition = AsyncMock(return_value=fake)
        result = await get_petition(petition_number="P1")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert "USPTO petition P1" in result.summary
    assert "Petition to revive" in result.summary
    assert "/api/v1/patent/petitions/P1" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_petition_list_preserves_order():
    ids = ["P1", "P2", "P3"]
    responses = [
        _FakeResponse(payload={"petitionDecisionDataBag": [_make_petition(p)]}) for p in ids
    ]

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_petition = AsyncMock(side_effect=responses)
        result = await get_petition(petition_number=ids)

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 3
    returned = [
        item["petitionDecisionDataBag"][0]["petitionDecisionRecordIdentifier"]
        for item in result.items
    ]
    assert returned == ids
    assert result.provenance.source_url.endswith("/api/v1/patent/petitions")
    assert "Fetched 3 USPTO petition decisions" in result.summary


def test_get_petition_parameter_renamed():
    """§5.8: petition_id → petition_number; the old name must not survive."""
    sig = inspect.signature(get_petition)
    assert "petition_number" in sig.parameters
    assert "petition_id" not in sig.parameters


# ──────────────────────────────────────────────────────────────────────
# §5.6 — Related tools cross-references
# ──────────────────────────────────────────────────────────────────────


def test_docstrings_carry_related_tools_lines():
    for tool in (search_petitions, get_petition):
        doc = tool.__doc__ or ""
        assert "Related tools:" in doc
        # Both tools must cross-reference search_applications (petitions
        # attach to applications, per the playbook).
        assert "search_applications" in doc, f"{tool.__name__} missing search_applications xref"
