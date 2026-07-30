"""Focused tests for the EPO family-intelligence aggregate."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_data_core.envelope import ResponseEnvelope
from mcp_data_core.exceptions import (
    AuthenticationError,
    ConfigurationError,
    NotFoundError,
    ParseError,
    RateLimitError,
    ServerError,
)
from patent_client_agents.epo_ops.models import (
    CitationResponse,
    DocumentId,
    EquivalentsResponse,
    FamilyIntelligenceResponse,
    FamilyMember,
    FamilyResponse,
    LegalEvent,
    LegalEventsResponse,
    RegisterBiblioResponse,
    RegisterEvent,
    RegisterEventsResponse,
    RegisterProceduralStep,
    RegisterProceduralStepsResponse,
)
from patent_client_agents.mcp.tools.epo_ops import get_epo_family_intelligence


def _patch_client(mock_client: MagicMock) -> AbstractContextManager[Any]:
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=mock_client)
    context.__aexit__ = AsyncMock(return_value=None)
    return patch(
        "patent_client_agents.mcp.tools.epo_ops.client_from_env",
        return_value=context,
    )


def _successful_client(number: str = "EP1000000A1") -> MagicMock:
    client = MagicMock()
    client.fetch_family = AsyncMock(
        return_value=FamilyResponse(
            publication_number=number,
            num_records=2,
            members=[
                FamilyMember(publication_number=number),
                FamilyMember(publication_number="US6000000A"),
            ],
        )
    )
    client.fetch_equivalents = AsyncMock(
        return_value=EquivalentsResponse(
            input_document=DocumentId(country="EP", number="1000000", kind="A1"),
            equivalents=[DocumentId(country="US", number="6000000", kind="A")],
        )
    )
    client.fetch_citations = AsyncMock(
        return_value=CitationResponse(
            publication_number=number,
            citations=[],
        )
    )
    client.fetch_legal_events = AsyncMock(
        return_value=LegalEventsResponse(
            events=[LegalEvent(event_code="EP.PG25", event_date="20240101")]
        )
    )
    client.fetch_register_biblio = AsyncMock(
        return_value=RegisterBiblioResponse(
            epo_number=number,
            bibliographic_status="Application pending",
        )
    )
    client.fetch_register_events = AsyncMock(
        return_value=RegisterEventsResponse(
            epo_number=number,
            events=[RegisterEvent(event_code="0009012")],
        )
    )
    client.fetch_register_procedural_steps = AsyncMock(
        return_value=RegisterProceduralStepsResponse(
            epo_number=number,
            procedural_steps=[RegisterProceduralStep(step_code="RFEE")],
        )
    )
    return client


@pytest.mark.asyncio
async def test_family_intelligence_returns_typed_per_source_evidence() -> None:
    client = _successful_client()

    with _patch_client(client):
        result = await get_epo_family_intelligence(" ep 1000000 a1 ")

    assert isinstance(result, ResponseEnvelope)
    assert isinstance(result.details, FamilyIntelligenceResponse)
    assert result.details.publication_number == "EP1000000A1"
    assert result.details.inpadoc_family.outcome == "ok"
    assert result.details.simple_family_equivalents.outcome == "ok"
    assert result.details.backward_citations.outcome == "empty"
    assert result.details.worldwide_legal_events.outcome == "ok"
    assert result.details.register_biblio.outcome == "ok"
    assert result.details.register_events.outcome == "ok"
    assert result.details.register_procedural_steps.outcome == "ok"
    assert result.provenance.source_name == (
        "European Patent Office services aggregate (EPO OPS and European Patent Register)"
    )
    assert result.provenance.source_url == "https://ops.epo.org/3.2"
    assert "Register evidence: biblio returned" in result.summary
    assert "1 dossier event(s)" in result.summary
    assert "1 procedural step(s)" in result.summary

    assert result.details.inpadoc_family.provenance is not None
    assert result.details.inpadoc_family.provenance.source_url.endswith(
        "/family/publication/docdb/EP1000000A1"
    )
    assert result.details.simple_family_equivalents.provenance is not None
    assert result.details.simple_family_equivalents.provenance.source_url.endswith(
        "/published-data/publication/docdb/EP1000000A1/equivalents"
    )
    assert result.details.backward_citations.provenance is not None
    assert result.details.backward_citations.provenance.source_url.endswith(
        "/published-data/publication/docdb/EP1000000A1/biblio"
    )
    assert result.details.worldwide_legal_events.provenance is not None
    assert result.details.worldwide_legal_events.provenance.source_url.endswith(
        "/legal/publication/docdb/EP1000000A1"
    )
    assert result.details.register_biblio.provenance is not None
    assert result.details.register_biblio.provenance.source_url.endswith(
        "/register/publication/epodoc/EP1000000A1/biblio"
    )
    assert result.details.register_events.provenance is not None
    assert result.details.register_events.provenance.source_url.endswith(
        "/register/publication/epodoc/EP1000000A1/events"
    )
    assert result.details.register_procedural_steps.provenance is not None
    assert result.details.register_procedural_steps.provenance.source_url.endswith(
        "/register/publication/epodoc/EP1000000A1/procedural-steps"
    )

    for method_name in (
        "fetch_family",
        "fetch_equivalents",
        "fetch_citations",
        "fetch_legal_events",
        "fetch_register_biblio",
        "fetch_register_events",
        "fetch_register_procedural_steps",
    ):
        getattr(client, method_name).assert_awaited_once_with(number="EP1000000A1")

    dumped = result.details.model_dump()
    assert set(dumped) == {
        "publication_number",
        "inpadoc_family",
        "simple_family_equivalents",
        "backward_citations",
        "worldwide_legal_events",
        "register_biblio",
        "register_events",
        "register_procedural_steps",
        "limitations",
    }
    assert "active" not in result.summary.lower()
    assert "enforceab" not in result.summary.lower()
    assert any("national register" in item.lower() for item in result.details.limitations)
    assert any("upc" in item.lower() for item in result.details.limitations)


@pytest.mark.asyncio
async def test_family_intelligence_non_ep_skips_register_sources() -> None:
    client = _successful_client("US6000000A")

    with _patch_client(client):
        result = await get_epo_family_intelligence(" us 6000000 a ")

    assert result.details.publication_number == "US6000000A"
    assert result.details.register_biblio.outcome == "not_applicable"
    assert result.details.register_events.outcome == "not_applicable"
    assert result.details.register_procedural_steps.outcome == "not_applicable"
    assert result.provenance.source_name == (
        "European Patent Office Open Patent Services (EPO OPS)"
    )
    assert result.provenance.source_url == "https://ops.epo.org/3.2/rest-services"
    assert "Register evidence" not in result.summary
    client.fetch_register_biblio.assert_not_awaited()
    client.fetch_register_events.assert_not_awaited()
    client.fetch_register_procedural_steps.assert_not_awaited()


@pytest.mark.asyncio
async def test_family_intelligence_distinguishes_empty_from_source_failure() -> None:
    client = _successful_client()
    client.fetch_family = AsyncMock(return_value=FamilyResponse())
    client.fetch_equivalents = AsyncMock(side_effect=NotFoundError("no equivalents", 404))
    client.fetch_citations = AsyncMock(side_effect=RateLimitError("quota", 429))
    client.fetch_legal_events = AsyncMock(return_value=LegalEventsResponse())
    client.fetch_register_biblio = AsyncMock(return_value=RegisterBiblioResponse(epo_number="EP1"))
    client.fetch_register_events = AsyncMock(return_value=RegisterEventsResponse(epo_number="EP1"))
    client.fetch_register_procedural_steps = AsyncMock(
        return_value=RegisterProceduralStepsResponse(epo_number="EP1")
    )

    with _patch_client(client):
        result = await get_epo_family_intelligence("EP1")

    assert result.details.inpadoc_family.outcome == "empty"
    assert result.details.worldwide_legal_events.outcome == "empty"
    assert result.details.register_biblio.outcome == "empty"
    assert result.details.register_events.outcome == "empty"
    assert result.details.register_procedural_steps.outcome == "empty"

    equivalents = result.details.simple_family_equivalents
    assert equivalents.outcome == "not_found"
    assert equivalents.provenance is None
    assert equivalents.failure is not None
    assert equivalents.failure.retryable is False
    assert equivalents.failure.source_name == (
        "European Patent Office Open Patent Services (EPO OPS)"
    )
    assert equivalents.failure.source_url.endswith(
        "/published-data/publication/docdb/EP1/equivalents"
    )

    citations = result.details.backward_citations
    assert citations.outcome == "error"
    assert citations.provenance is None
    assert citations.failure is not None
    assert citations.failure.retryable is True
    assert citations.failure.source_url.endswith("/published-data/publication/docdb/EP1/biblio")


@pytest.mark.asyncio
async def test_family_intelligence_captures_parse_and_transport_failures() -> None:
    client = _successful_client()
    client.fetch_register_biblio = AsyncMock(
        side_effect=ParseError("bad register XML", source="register")
    )
    client.fetch_register_events = AsyncMock(side_effect=httpx.ReadTimeout("register timed out"))

    with _patch_client(client):
        result = await get_epo_family_intelligence("EP1000000A1")

    biblio = result.details.register_biblio
    assert biblio.outcome == "error"
    assert biblio.failure is not None
    assert biblio.failure.code == "parse_error"
    assert biblio.failure.retryable is False
    assert biblio.failure.source_url.endswith("/register/publication/epodoc/EP1000000A1/biblio")

    events = result.details.register_events
    assert events.outcome == "error"
    assert events.failure is not None
    assert events.failure.code == "transport_error"
    assert events.failure.retryable is True
    assert events.failure.source_url.endswith("/register/publication/epodoc/EP1000000A1/events")


@pytest.mark.asyncio
async def test_family_intelligence_all_attempted_failures_reraises_typed_original() -> None:
    client = MagicMock()
    failures = [
        ServerError("family failed", 503),
        ServerError("equivalents failed", 503),
        ServerError("citations failed", 503),
        ServerError("events failed", 503),
    ]
    client.fetch_family = AsyncMock(side_effect=failures[0])
    client.fetch_equivalents = AsyncMock(side_effect=failures[1])
    client.fetch_citations = AsyncMock(side_effect=failures[2])
    client.fetch_legal_events = AsyncMock(side_effect=failures[3])

    with _patch_client(client), pytest.raises(ServerError) as exc_info:
        await get_epo_family_intelligence("US6000000A")

    assert exc_info.value is failures[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        AuthenticationError("bad credentials", 401),
        ConfigurationError("missing configuration"),
        RuntimeError("programming error"),
    ],
)
async def test_family_intelligence_propagates_non_partial_failures(failure: Exception) -> None:
    client = _successful_client()
    client.fetch_family = AsyncMock(side_effect=failure)

    with _patch_client(client), pytest.raises(type(failure)) as exc_info:
        await get_epo_family_intelligence("EP1000000A1")

    assert exc_info.value is failure


@pytest.mark.asyncio
async def test_family_intelligence_rejects_blank_publication() -> None:
    with pytest.raises(ValueError, match="requires a publication number"):
        await get_epo_family_intelligence("   ")


@pytest.mark.asyncio
async def test_family_intelligence_rejects_list_input() -> None:
    with pytest.raises(ValueError, match="requires a single publication number"):
        await get_epo_family_intelligence(
            ["EP1"]  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]
        )
