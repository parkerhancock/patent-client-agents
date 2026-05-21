"""Envelope-shape tests for the IP Australia trade marks MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9, §5.4, §5.5, §5.6. Mocks
``IpAustraliaTrademarksClient`` at the boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.ip_australia_trademarks import (
    get_ipa_trademark,
    search_ipa_trademarks,
)


class _FakeModel:
    """Fake upstream response: round-trips arbitrary camelCase fields via model_dump."""

    def __init__(self, **kwargs: Any) -> None:
        self._payload = kwargs

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _make_tm_row(
    serial: str,
    *,
    word_mark: str = "VEGEMITE",
    status: str = "REGISTERED",
) -> dict:
    return {
        "serialNumber": serial,
        "wordMark": word_mark,
        "status": status,
        "markType": "WORD",
        "applicationDate": "2018-03-14",
        "registrationDate": "2019-06-20",
        "niceClasses": [29, 30],
    }


def _make_search_result(rows: list[dict], *, total: int | None = None) -> _FakeModel:
    return _FakeModel(results=rows, total=total if total is not None else len(rows))


def _make_detail(serial: str, **kwargs: Any) -> _FakeModel:
    return _FakeModel(**_make_tm_row(serial, **kwargs))


# ──────────────────────────────────────────────────────────────────────
# search_ipa_trademarks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ipa_trademarks_returns_lean_envelope_by_default():
    rows = [
        _make_tm_row("1234567", word_mark="VEGEMITE"),
        _make_tm_row("2345678", word_mark="UGG"),
    ]
    result_model = _make_search_result(rows, total=42)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_trademarks.IpAustraliaTrademarksClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_trademarks(query="VEGEMITE")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IP Australia"
    assert (
        "/public/australian-trade-mark-search-api/v1/search/quick" in result.provenance.source_url
    )
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "serial_number",
        "word_mark",
        "status",
        "mark_type",
        "application_date",
        "registration_date",
        "nice_classes",
    }
    assert result.items[0]["word_mark"] == "VEGEMITE"
    assert "VEGEMITE" in result.summary
    assert "2 of 42 hits" in result.summary
    assert result.more_available is True


@pytest.mark.asyncio
async def test_search_ipa_trademarks_full_true_returns_upstream_shape():
    rows = [_make_tm_row("1234567")]
    result_model = _make_search_result(rows, total=1)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_trademarks.IpAustraliaTrademarksClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_trademarks(query="x", full=True)

    assert "serialNumber" in result.items[0]
    assert "niceClasses" in result.items[0]


# ──────────────────────────────────────────────────────────────────────
# get_ipa_trademark — §5.4 list-accept, order preservation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ipa_trademark_single_string_returns_list_envelope():
    detail = _make_detail("1234567", word_mark="VEGEMITE")

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_trademarks.IpAustraliaTrademarksClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trademark = AsyncMock(return_value=detail)

        result = await get_ipa_trademark(serial_number="1234567")

    mock_client.get_trademark.assert_awaited_once_with("1234567")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "IP Australia"
    assert "/trade-mark/1234567" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["serialNumber"] == "1234567"
    assert "AU trade mark 1234567" in result.summary
    assert "VEGEMITE" in result.summary


@pytest.mark.asyncio
async def test_get_ipa_trademark_list_preserves_order():
    numbers = ["1234567", "2345678", "3456789"]
    details = [_make_detail(n, word_mark=f"MARK{n}") for n in numbers]

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_trademarks.IpAustraliaTrademarksClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trademark = AsyncMock(side_effect=details)

        result = await get_ipa_trademark(serial_number=numbers)

    assert isinstance(result, ListEnvelope)
    assert [r["serialNumber"] for r in result.items] == numbers
    assert result.provenance.source_url.endswith(
        "/public/australian-trade-mark-search-api/v1/trade-mark"
    )
    assert "Fetched 3 Australian trade marks" in result.summary


@pytest.mark.asyncio
async def test_get_ipa_trademark_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipa_trademark(serial_number=[])
