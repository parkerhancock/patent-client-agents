"""Tests for the USPTO forward-citation monitoring workflow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from patent_client_agents.mcp.tools import office_actions as mod
from patent_client_agents.uspto_office_actions.models import (
    EnrichedCitation,
    EnrichedCitationSearchResponse,
    OfficeActionRejection,
    RejectionSearchResponse,
)


def _make_client(citation_response, rejection_response):
    client = MagicMock()
    client.search_enriched_citations = AsyncMock(return_value=citation_response)
    client.search_rejections = AsyncMock(return_value=rejection_response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.asyncio
async def test_filters_to_examiner_citations_and_cross_checks_section_102(monkeypatch):
    citation_response = EnrichedCitationSearchResponse(
        num_found=2,
        results=[
            EnrichedCitation.model_validate(
                {
                    "citedDocumentIdentifier": "US 10123456 B2",
                    "patentApplicationNumber": "17000001",
                    "officeActionDate": "2026-05-01",
                    "examinerCitedReferenceIndicator": True,
                }
            ),
            EnrichedCitation.model_validate(
                {
                    "citedDocumentIdentifier": "US 10123456 B2",
                    "patentApplicationNumber": "17000002",
                    "officeActionDate": "2026-05-02",
                    "examinerCitedReferenceIndicator": False,
                }
            ),
        ],
    )
    rejection_response = RejectionSearchResponse(
        num_found=1,
        results=[
            OfficeActionRejection.model_validate(
                {"patentApplicationNumber": "17000001", "hasRej102": 1}
            )
        ],
    )
    client = _make_client(citation_response, rejection_response)
    monkeypatch.setattr(mod, "OfficeActionClient", MagicMock(return_value=client))

    result = await mod.check_citation_hits(
        patent_numbers=["US 10123456 B2"], since="2026-01-01"
    )

    assert len(result.items) == 1
    assert result.items[0] == {
        "cited_patent": "US 10123456 B2",
        "citing_application": "17000001",
        "office_action_date": "2026-05-01",
        "citing_app_has_section_102": True,
    }


@pytest.mark.asyncio
async def test_phrase_quotes_each_watched_identifier(monkeypatch):
    client = _make_client(
        EnrichedCitationSearchResponse(num_found=0, results=[]),
        RejectionSearchResponse(num_found=0, results=[]),
    )
    monkeypatch.setattr(mod, "OfficeActionClient", MagicMock(return_value=client))

    watched = ["US 10946800 B2", "WO-2017115695-A1"]
    await mod.check_citation_hits(patent_numbers=watched, since="2026-01-01")

    criteria = client.search_enriched_citations.await_args.args[0]
    for identifier in watched:
        assert f'"{identifier}"' in criteria
    assert "citedDocumentIdentifier:(US 10946800 B2" not in criteria


@pytest.mark.asyncio
async def test_no_hits_returns_clear_summary(monkeypatch):
    client = _make_client(
        EnrichedCitationSearchResponse(num_found=0, results=[]),
        RejectionSearchResponse(num_found=0, results=[]),
    )
    monkeypatch.setattr(mod, "OfficeActionClient", MagicMock(return_value=client))

    result = await mod.check_citation_hits(
        patent_numbers=["US 10123456 B2", "US 10234567 B2"], since="2026-01-01"
    )

    assert result.items == []
    assert result.summary == "No new citation hits for 2 watched patent(s)."
    client.search_rejections.assert_not_awaited()
