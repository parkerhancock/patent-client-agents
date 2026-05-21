"""Envelope-shape tests for the IP Australia patents MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + ``full=True`` opt-in),
and §5.6 (cross-referenced docstrings).

Mocks ``IpAustraliaPatentsClient`` at the boundary — we test envelope
shape, not the upstream API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.ip_australia_patents import (
    get_ipa_patent,
    search_ipa_patents,
)


class _FakeModel:
    """Fake upstream response: round-trips arbitrary camelCase fields via model_dump."""

    def __init__(self, **kwargs: Any) -> None:
        self._payload = kwargs

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _make_patent_row(
    appno: str,
    *,
    title: str = "Test invention",
    status: str = "GRANTED",
    patent_number: str | None = "2019204205",
) -> dict:
    return {
        "applicationNumber": appno,
        "patentNumber": patent_number,
        "title": title,
        "status": status,
        "applicationDate": "2019-06-12",
        "grantDate": "2022-08-30",
        "ipcClassifications": ["G06F 21/30"],
    }


def _make_search_result(rows: list[dict], *, total: int | None = None) -> _FakeModel:
    return _FakeModel(results=rows, total=total if total is not None else len(rows))


def _make_detail(appno: str, **kwargs: Any) -> _FakeModel:
    return _FakeModel(**_make_patent_row(appno, **kwargs))


# ──────────────────────────────────────────────────────────────────────
# search_ipa_patents
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ipa_patents_returns_lean_envelope_by_default():
    rows = [
        _make_patent_row("2019204205", title="Blockchain auth"),
        _make_patent_row("2020111111", title="Quantum key dist"),
    ]
    result_model = _make_search_result(rows, total=12)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_patents.IpAustraliaPatentsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_patents(query="blockchain")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IP Australia"
    assert "/public/australian-patent-search-api/v1/search/quick" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "application_number",
        "patent_number",
        "title",
        "status",
        "application_date",
        "grant_date",
        "ipc_classifications",
    }
    assert result.items[0]["application_number"] == "2019204205"
    assert "blockchain" in result.summary
    assert "2 of 12 hits" in result.summary
    assert result.more_available is True


@pytest.mark.asyncio
async def test_search_ipa_patents_full_true_returns_upstream_shape():
    rows = [_make_patent_row("2019204205")]
    result_model = _make_search_result(rows, total=1)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_patents.IpAustraliaPatentsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_patents(query="x", full=True)

    # Full mode returns the upstream camelCase row.
    assert "applicationNumber" in result.items[0]
    assert "ipcClassifications" in result.items[0]


@pytest.mark.asyncio
async def test_search_ipa_patents_more_available_false_when_exhausted():
    rows = [_make_patent_row("2019204205")]
    result_model = _make_search_result(rows, total=1)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_patents.IpAustraliaPatentsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_patents(query="x")

    assert result.more_available is False


# ──────────────────────────────────────────────────────────────────────
# get_ipa_patent — §5.4 list-accept, order preservation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ipa_patent_single_string_returns_list_envelope():
    detail = _make_detail("2019204205", title="Blockchain auth")

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_patents.IpAustraliaPatentsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_patent = AsyncMock(return_value=detail)

        result = await get_ipa_patent(application_number="2019204205")

    mock_client.get_patent.assert_awaited_once_with("2019204205")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "IP Australia"
    assert "/patent/2019204205" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["applicationNumber"] == "2019204205"
    assert "AU patent application 2019204205" in result.summary
    assert "Blockchain auth" in result.summary


@pytest.mark.asyncio
async def test_get_ipa_patent_list_preserves_order():
    numbers = ["2019204205", "2020111111", "2021333333"]
    details = [_make_detail(n, title=f"Title {n}") for n in numbers]

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_patents.IpAustraliaPatentsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_patent = AsyncMock(side_effect=details)

        result = await get_ipa_patent(application_number=numbers)

    assert isinstance(result, ListEnvelope)
    assert [r["applicationNumber"] for r in result.items] == numbers
    # Multi-fetch points provenance at the collection URL.
    assert result.provenance.source_url.endswith("/public/australian-patent-search-api/v1/patent")
    assert "Fetched 3 Australian patents" in result.summary


@pytest.mark.asyncio
async def test_get_ipa_patent_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipa_patent(application_number=[])
