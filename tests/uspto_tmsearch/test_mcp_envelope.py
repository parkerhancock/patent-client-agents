"""Envelope-shape tests for the migrated Trademarks MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.3 (single auto-detecting identifier param),
and §5.5 (lean default + full opt-in).

Mocks ``TmsearchClient`` and ``TsdrClient`` at the boundary.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.trademarks import (
    _classify_tm_identifier,
    get_trademark,
    get_trademark_documents,
    get_trademark_last_update,
    get_trademark_status,
    search_trademarks,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes
# ──────────────────────────────────────────────────────────────────────


class _FakeTrademark(BaseModel):
    serialNumber: str
    registrationNumber: str | None = None
    wordmark: str = "TESTMARK"
    ownerName: str = "Test Co."
    filingDate: str = "2020-01-15"
    registrationDate: str | None = None
    statusCode: str = "700"
    statusText: str = "Registered"


class _FakeSearchResponse(BaseModel):
    results: list[_FakeTrademark] = []


class _FakeTsdrStatus(BaseModel):
    serialNumber: str
    statusCode: str = "700"
    statusText: str = "Registered"


class _FakeTsdrDocument(BaseModel):
    documentId: str
    documentType: str
    mailDate: str


class _FakeLastUpdate(BaseModel):
    serialNumber: str
    lastUpdate: str


def _make_tm(serial: str, *, wordmark: str = "TESTMARK", reg: str | None = None) -> _FakeTrademark:
    return _FakeTrademark(serialNumber=serial, wordmark=wordmark, registrationNumber=reg)


# ──────────────────────────────────────────────────────────────────────
# _classify_tm_identifier — §5.3 auto-detection
# ──────────────────────────────────────────────────────────────────────


class TestClassifyIdentifier:
    def test_8_digit_is_serial(self):
        assert _classify_tm_identifier("97123456") == "serial"

    def test_7_digit_is_registration(self):
        assert _classify_tm_identifier("1234567") == "registration"

    def test_6_digit_is_registration(self):
        assert _classify_tm_identifier("123456") == "registration"

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError, match="must be all digits"):
            _classify_tm_identifier("USPTO97123456")

    def test_unexpected_length_raises(self):
        with pytest.raises(ValidationError, match="digits"):
            _classify_tm_identifier("12345")  # 5 digits, ambiguous

    def test_strips_whitespace(self):
        assert _classify_tm_identifier(" 97123456 ") == "serial"


# ──────────────────────────────────────────────────────────────────────
# search_trademarks — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_trademarks_returns_lean_list_envelope_by_default():
    response = _FakeSearchResponse(
        results=[_make_tm("97123456", wordmark="ACME"), _make_tm("97654321", wordmark="WIDGET")]
    )
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=response)

        result = await search_trademarks(query="ACME")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "USPTO Trademark Search (TESS)"
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "serial_number",
        "registration_number",
        "wordmark",
        "owner_name",
        "filing_date",
        "registration_date",
        "status_code",
        "status_text",
    }
    assert result.items[0]["serial_number"] == "97123456"
    assert "ACME" in result.summary


@pytest.mark.asyncio
async def test_search_trademarks_full_true_returns_upstream_shape():
    response = _FakeSearchResponse(results=[_make_tm("97123456")])
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=response)

        result = await search_trademarks(query="ACME", full=True)

    assert "serialNumber" in result.items[0]
    assert result.items[0]["serialNumber"] == "97123456"


# ──────────────────────────────────────────────────────────────────────
# get_trademark — §5.3 single auto-detected param, §5.4 list-accepting
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trademark_single_serial_dispatches_to_serial_method():
    mark = _make_tm("97123456", wordmark="ACME")
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_serial = AsyncMock(return_value=mark)
        mock_client.get_by_registration = AsyncMock()

        result = await get_trademark(serial_number="97123456")

    mock_client.get_by_serial.assert_awaited_once_with("97123456")
    mock_client.get_by_registration.assert_not_awaited()
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert "97123456" in result.summary
    assert "ACME" in result.summary


@pytest.mark.asyncio
async def test_get_trademark_single_registration_dispatches_to_registration_method():
    mark = _make_tm("97123456", reg="1234567")
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_serial = AsyncMock()
        mock_client.get_by_registration = AsyncMock(return_value=mark)

        result = await get_trademark(serial_number="1234567")

    mock_client.get_by_registration.assert_awaited_once_with("1234567")
    mock_client.get_by_serial.assert_not_awaited()
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_get_trademark_list_preserves_order():
    marks = [_make_tm(s) for s in ["97000001", "97000002", "97000003"]]
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_serial = AsyncMock(side_effect=marks)

        result = await get_trademark(serial_number=["97000001", "97000002", "97000003"])

    assert [r["serialNumber"] for r in result.items] == ["97000001", "97000002", "97000003"]
    assert "3 of 3" in result.summary


@pytest.mark.asyncio
async def test_get_trademark_handles_not_found():
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_serial = AsyncMock(return_value=None)

        result = await get_trademark(serial_number="97999999")

    assert result.items == []
    assert "not found" in result.summary


@pytest.mark.asyncio
async def test_get_trademark_partial_not_found_lists_missing():
    with patch("patent_client_agents.mcp.tools.trademarks.TmsearchClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_by_serial = AsyncMock(
            side_effect=[_make_tm("97000001"), None, _make_tm("97000003")]
        )

        result = await get_trademark(serial_number=["97000001", "97999999", "97000003"])

    assert len(result.items) == 2
    assert "97999999" in result.summary
    assert "Not found" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_trademark_status — §5.4 (replaces batch_trademark_status)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trademark_status_single_returns_list_envelope():
    with patch("patent_client_agents.mcp.tools.trademarks.TsdrClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_status = AsyncMock(return_value=_FakeTsdrStatus(serialNumber="97123456"))

        result = await get_trademark_status(serial_number="97123456")

    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "USPTO TSDR"
    assert len(result.items) == 1
    assert "97123456" in result.summary


@pytest.mark.asyncio
async def test_get_trademark_status_list_fans_out():
    serials = ["97000001", "97000002", "97000003"]
    responses = [_FakeTsdrStatus(serialNumber=s) for s in serials]
    with patch("patent_client_agents.mcp.tools.trademarks.TsdrClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_status = AsyncMock(side_effect=responses)

        result = await get_trademark_status(serial_number=serials)

    assert [r["serialNumber"] for r in result.items] == serials


@pytest.mark.asyncio
async def test_batch_trademark_status_was_deleted():
    """The §5.4 violation should no longer be importable."""
    from patent_client_agents.mcp.tools import trademarks as tm_module

    assert not hasattr(tm_module, "batch_trademark_status")


# ──────────────────────────────────────────────────────────────────────
# get_trademark_documents
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trademark_documents_returns_list_envelope():
    docs = [
        _FakeTsdrDocument(documentId="D1", documentType="OFFICE_ACTION", mailDate="2021-03-01"),
        _FakeTsdrDocument(documentId="D2", documentType="RESPONSE", mailDate="2021-06-01"),
    ]
    with patch("patent_client_agents.mcp.tools.trademarks.TsdrClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_documents = AsyncMock(return_value=docs)

        result = await get_trademark_documents(serial_number="97123456")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 2
    assert "97123456" in result.summary
    assert "2 documents" in result.summary
    assert "/sn97123456/" in result.provenance.source_url


# ──────────────────────────────────────────────────────────────────────
# get_trademark_last_update — §5.4
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trademark_last_update_single():
    with patch("patent_client_agents.mcp.tools.trademarks.TsdrClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_last_update = AsyncMock(
            return_value=_FakeLastUpdate(serialNumber="97123456", lastUpdate="2024-05-01")
        )

        result = await get_trademark_last_update(serial_number="97123456")

    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["lastUpdate"] == "2024-05-01"


@pytest.mark.asyncio
async def test_get_trademark_last_update_list():
    serials = ["97000001", "97000002"]
    responses = [_FakeLastUpdate(serialNumber=s, lastUpdate="2024-01-01") for s in serials]
    with patch("patent_client_agents.mcp.tools.trademarks.TsdrClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_last_update = AsyncMock(side_effect=responses)

        result = await get_trademark_last_update(serial_number=serials)

    assert len(result.items) == 2
    assert [r["serialNumber"] for r in result.items] == serials
