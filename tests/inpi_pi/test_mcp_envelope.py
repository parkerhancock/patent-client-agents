"""Envelope-shape tests for the INPI France MCP tools.

Verifies the §5.9 envelope contract (Provenance ``source_name`` /
``source_url`` populated; attribution mentions INPI + licence), §5.5
lean projection (drops heavy fields; ``full=True`` opt-in), and §5.4
list-accept on the fetch tools. Mocks the underlying client + module
boundary so no real INPI traffic is generated.

Uses plain ``_FakeRow`` classes (NOT ``BaseModel(extra='allow')``)
per the chunk-4 runbook ``ty`` pitfall.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError


class _FakeRow:
    """Fake upstream row that serializes to its stored payload dict.

    Plain class (not pydantic) sidesteps the ``ty`` ``unknown-argument``
    diagnostic that pydantic ``extra='allow'`` propagation triggers.
    """

    def __init__(self, **payload: Any) -> None:
        self._payload = payload

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs  # by_alias=True is the only kw used in practice
        return dict(self._payload)


def _tm_payload(appno: str = "4216963", **overrides: Any) -> dict[str, Any]:
    base = {
        "ApplicationNumber": appno,
        "ApplicationDate": "2015-09-01",
        "RegistrationNumber": appno,
        "RegistrationDate": "2016-01-15",
        "Mark": "EXAMPLE",
        "MarkImageURI": "https://example.test/img",
        "KindMark": "Individual",
        "ClassNumber": ["9", "42"],
        "ViennaClass": ["03.07.17"],
        "ApplicantName": ["ACME SAS"],
        "HolderName": [],
        "RepresentativeName": "Cabinet Patent",
        "MarkCurrentStatusCode": "registered",
    }
    base.update(overrides)
    return base


def _design_payload(appno: str = "FR20140182", **overrides: Any) -> dict[str, Any]:
    base = {
        "DesignApplicationNumber": appno,
        "DesignReference": "001",
        "DesignApplicationDate": "2014-05-20",
        "DesignTitle": "Chaise pliante",
        "DesignRepresentationSheetURIs": [
            "https://example.test/img/1",
            "https://example.test/img/2",
        ],
        "ClassNumber": ["0601"],
        "ApplicantName": ["Mobilier France"],
        "DesignerName": ["Jean Designer"],
        "DesignCurrentStatusCode": "registered",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fixture: import the env-gated MCP module fresh under set env.
# ---------------------------------------------------------------------------


@pytest.fixture
def inpi_mcp(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Import the inpi_pi MCP module under set env so tools register.

    Reloads against a fresh FastMCP so the ``@conditional_tool``
    decorators see an empty surface and the tool functions are
    re-bound on the module each test.
    """
    monkeypatch.setenv("INPI_USERNAME", "test-user")
    monkeypatch.setenv("INPI_PASSWORD", "test-pass")

    import patent_client_agents.mcp.tools.inpi_pi as inpi

    inpi.inpi_pi_mcp = FastMCP("INPI-PI")
    importlib.reload(inpi)
    return inpi


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch, inpi_mcp: Any) -> AsyncMock:
    """Patch ``InpiPiClient`` (used by all four tools) with an async-ctx AsyncMock."""
    inner = AsyncMock()

    class _MockCtx:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    def _factory(*args: Any, **kwargs: Any) -> _MockCtx:
        return _MockCtx()

    monkeypatch.setattr(inpi_mcp, "InpiPiClient", _factory)
    return inner


# ---------------------------------------------------------------------------
# search_inpi_trademarks — lean / full / envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_trademarks_envelope_shape(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.search_trademarks = AsyncMock(
        return_value=([_FakeRow(**_tm_payload("4216963"))], 1)
    )
    result = await inpi_mcp.search_inpi_trademarks(query="EXAMPLE")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    # Attribution carries INPI + licence text per §3 standards
    assert "INPI" in result.provenance.source_name
    assert "licence INPI" in result.provenance.source_name
    assert "/marques/search" in result.provenance.source_url
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_search_trademarks_lean_drops_heavy_fields(
    inpi_mcp: Any, mock_client: AsyncMock
) -> None:
    """Lean projection: only the 8-field LEAN_TM_FIELDS set survives."""
    mock_client.search_trademarks = AsyncMock(
        return_value=([_FakeRow(**_tm_payload("4216963"))], 1)
    )
    result = await inpi_mcp.search_inpi_trademarks(query="EXAMPLE")
    item = result.items[0]
    # Lean keeps the eight chosen fields
    assert "ApplicationNumber" in item
    assert "Mark" in item
    assert "ClassNumber" in item
    # And drops everything else (Vienna codes, image URI, KindMark, etc.)
    assert "ViennaClass" not in item
    assert "MarkImageURI" not in item
    assert "KindMark" not in item


@pytest.mark.asyncio
async def test_search_trademarks_full_keeps_all_fields(
    inpi_mcp: Any, mock_client: AsyncMock
) -> None:
    mock_client.search_trademarks = AsyncMock(
        return_value=([_FakeRow(**_tm_payload("4216963"))], 1)
    )
    result = await inpi_mcp.search_inpi_trademarks(query="x", full=True)
    item = result.items[0]
    # Full mode keeps the heavy fields
    assert "ViennaClass" in item
    assert "MarkImageURI" in item


@pytest.mark.asyncio
async def test_search_trademarks_more_available(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.search_trademarks = AsyncMock(return_value=([_FakeRow(**_tm_payload("X"))], 100))
    result = await inpi_mcp.search_inpi_trademarks(query="x")
    assert result.more_available is True
    assert "100 hits" in result.summary


@pytest.mark.asyncio
async def test_search_trademarks_no_more_when_total_reached(
    inpi_mcp: Any, mock_client: AsyncMock
) -> None:
    mock_client.search_trademarks = AsyncMock(return_value=([_FakeRow(**_tm_payload("X"))], 1))
    result = await inpi_mcp.search_inpi_trademarks(query="x")
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_trademarks_summary_with_total_unknown(
    inpi_mcp: Any, mock_client: AsyncMock
) -> None:
    """When INPI doesn't report a total, summary degrades gracefully."""
    mock_client.search_trademarks = AsyncMock(return_value=([_FakeRow(**_tm_payload("X"))], None))
    result = await inpi_mcp.search_inpi_trademarks(query="x")
    assert "1 hits" in result.summary
    assert result.more_available is False


# ---------------------------------------------------------------------------
# get_inpi_trademark — list-accept + envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_trademark_single_string(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_trademark = AsyncMock(return_value=[_FakeRow(**_tm_payload("4216963"))])
    result = await inpi_mcp.get_inpi_trademark(application_number="4216963")
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    # Single-record summary mentions the appno
    assert "4216963" in result.summary
    assert "/marques/4216963" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_trademark_list_combined_envelope(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_trademark = AsyncMock(
        return_value=[
            _FakeRow(**_tm_payload("A1")),
            _FakeRow(**_tm_payload("A2")),
            _FakeRow(**_tm_payload("A3")),
        ]
    )
    result = await inpi_mcp.get_inpi_trademark(application_number=["A1", "A2", "A3"])
    assert len(result.items) == 3
    appnos = {row["ApplicationNumber"] for row in result.items}
    assert appnos == {"A1", "A2", "A3"}
    assert "3 INPI trademarks" in result.summary


@pytest.mark.asyncio
async def test_get_trademark_empty_list_raises(inpi_mcp: Any) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await inpi_mcp.get_inpi_trademark(application_number=[])


@pytest.mark.asyncio
async def test_get_trademark_full_preserves_heavy_fields(
    inpi_mcp: Any, mock_client: AsyncMock
) -> None:
    mock_client.get_trademark = AsyncMock(return_value=[_FakeRow(**_tm_payload("X"))])
    result = await inpi_mcp.get_inpi_trademark(application_number="X", full=True)
    item = result.items[0]
    assert "ViennaClass" in item
    assert "MarkImageURI" in item


# ---------------------------------------------------------------------------
# search_inpi_designs — envelope + lean
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_designs_envelope_shape(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.search_designs = AsyncMock(return_value=([_FakeRow(**_design_payload())], 1))
    result = await inpi_mcp.search_inpi_designs(query="chair")
    assert isinstance(result, ListEnvelope)
    assert "INPI" in result.provenance.source_name
    assert "licence INPI" in result.provenance.source_name
    assert "/dessins/search" in result.provenance.source_url
    item = result.items[0]
    # Lean: keep core fields, drop image URLs
    assert "DesignApplicationNumber" in item
    assert "DesignTitle" in item
    assert "DesignRepresentationSheetURIs" not in item


@pytest.mark.asyncio
async def test_search_designs_full_keeps_image_urls(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.search_designs = AsyncMock(return_value=([_FakeRow(**_design_payload())], 1))
    result = await inpi_mcp.search_inpi_designs(query="chair", full=True)
    item = result.items[0]
    assert "DesignRepresentationSheetURIs" in item
    assert len(item["DesignRepresentationSheetURIs"]) == 2


@pytest.mark.asyncio
async def test_search_designs_summary_with_no_query(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.search_designs = AsyncMock(return_value=([_FakeRow(**_design_payload())], 1))
    result = await inpi_mcp.search_inpi_designs(locarno_class=["0601"])
    # Summary labels structured-only searches "(structured)"
    assert "structured" in result.summary


# ---------------------------------------------------------------------------
# get_inpi_design — list-accept + envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_design_single_string(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_design = AsyncMock(return_value=[_FakeRow(**_design_payload("FR20140182"))])
    result = await inpi_mcp.get_inpi_design(application_number="FR20140182")
    assert len(result.items) == 1
    assert "FR20140182" in result.summary
    assert "/dessins/FR20140182" in result.provenance.source_url


@pytest.mark.asyncio
async def test_get_design_list_combined(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_design = AsyncMock(
        return_value=[
            _FakeRow(**_design_payload("FR1")),
            _FakeRow(**_design_payload("FR2")),
        ]
    )
    result = await inpi_mcp.get_inpi_design(application_number=["FR1", "FR2"])
    assert len(result.items) == 2
    assert "2 INPI designs" in result.summary


@pytest.mark.asyncio
async def test_get_design_empty_list_raises(inpi_mcp: Any) -> None:
    with pytest.raises(ValidationError, match="at least one"):
        await inpi_mcp.get_inpi_design(application_number=[])


@pytest.mark.asyncio
async def test_get_design_full_keeps_image_urls(inpi_mcp: Any, mock_client: AsyncMock) -> None:
    mock_client.get_design = AsyncMock(return_value=[_FakeRow(**_design_payload("X"))])
    result = await inpi_mcp.get_inpi_design(application_number="X", full=True)
    item = result.items[0]
    assert "DesignRepresentationSheetURIs" in item
