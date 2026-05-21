"""Envelope-shape tests for the IP Australia designs MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9, §5.4, §5.5, §5.6. Mocks
``IpAustraliaDesignsClient`` at the boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from mcp_data_core.envelope import ListEnvelope, Provenance
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.ip_australia_designs import (
    get_ipa_design,
    search_ipa_designs,
)


class _FakeModel:
    """Fake upstream response: round-trips arbitrary camelCase fields via model_dump."""

    def __init__(self, **kwargs: Any) -> None:
        self._payload = kwargs

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        del kwargs
        return dict(self._payload)


def _make_design_row(
    dno: str,
    *,
    title: str = "Lounge chair",
    status: str = "REGISTERED",
    locarno: list[str] | None = None,
) -> dict:
    return {
        "designNumber": dno,
        "applicationNumber": dno,
        "title": title,
        "status": status,
        "applicationDate": "2024-02-15",
        "registrationDate": "2024-05-30",
        "locarnoClasses": locarno or ["06.01"],
    }


def _make_search_result(rows: list[dict], *, total: int | None = None) -> _FakeModel:
    return _FakeModel(results=rows, total=total if total is not None else len(rows))


def _make_detail(dno: str, **kwargs: Any) -> _FakeModel:
    return _FakeModel(**_make_design_row(dno, **kwargs))


# ──────────────────────────────────────────────────────────────────────
# search_ipa_designs
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_ipa_designs_returns_lean_envelope_by_default():
    rows = [
        _make_design_row("202410123", title="Lounge chair"),
        _make_design_row("202410456", title="Bottle"),
    ]
    result_model = _make_search_result(rows, total=15)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_designs.IpAustraliaDesignsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_designs(query="chair")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "IP Australia"
    assert "/public/australian-design-search-api/v1/search/quick" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "design_number",
        "application_number",
        "title",
        "status",
        "application_date",
        "registration_date",
        "locarno_classes",
    }
    assert result.items[0]["design_number"] == "202410123"
    assert "chair" in result.summary
    assert "2 of 15 hits" in result.summary
    assert result.more_available is True


@pytest.mark.asyncio
async def test_search_ipa_designs_full_true_returns_upstream_shape():
    rows = [_make_design_row("202410123")]
    result_model = _make_search_result(rows, total=1)

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_designs.IpAustraliaDesignsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_ipa_designs(query="x", full=True)

    assert "designNumber" in result.items[0]
    assert "locarnoClasses" in result.items[0]


# ──────────────────────────────────────────────────────────────────────
# get_ipa_design — §5.4 list-accept, order preservation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ipa_design_single_string_returns_list_envelope():
    detail = _make_detail("202410123", title="Lounge chair")

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_designs.IpAustraliaDesignsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_design = AsyncMock(return_value=detail)

        result = await get_ipa_design(application_number="202410123")

    mock_client.get_design.assert_awaited_once_with("202410123")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "IP Australia"
    assert "/design/202410123" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["designNumber"] == "202410123"
    assert "AU design 202410123" in result.summary
    assert "Lounge chair" in result.summary


@pytest.mark.asyncio
async def test_get_ipa_design_list_preserves_order():
    numbers = ["202410123", "202410456", "202410789"]
    details = [_make_detail(n, title=f"Design {n}") for n in numbers]

    with patch(
        "patent_client_agents.mcp.tools.ip_australia_designs.IpAustraliaDesignsClient"
    ) as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_design = AsyncMock(side_effect=details)

        result = await get_ipa_design(application_number=numbers)

    assert isinstance(result, ListEnvelope)
    assert [r["designNumber"] for r in result.items] == numbers
    assert result.provenance.source_url.endswith("/public/australian-design-search-api/v1/design")
    assert "Fetched 3 Australian designs" in result.summary


@pytest.mark.asyncio
async def test_get_ipa_design_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_ipa_design(application_number=[])
