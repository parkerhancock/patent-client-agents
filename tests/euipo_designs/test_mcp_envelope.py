"""Envelope-shape tests for the migrated EUIPO design MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + ``full=True`` opt-in),
and §5.6 (cross-referenced docstrings).

Mocks ``EuipoDesignsClient`` at the boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ConfigDict

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.euipo import (
    get_euipo_design,
    search_euipo_designs,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — mirror the upstream camelCase JSON shape after model_dump
# ──────────────────────────────────────────────────────────────────────


class _FakeModel(BaseModel):
    """Pydantic model that round-trips arbitrary camelCase fields via model_dump."""

    model_config = ConfigDict(extra="allow")

    def model_dump(self, **kwargs: Any) -> dict:  # type: ignore[override]
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


def _make_design_row(
    design_number: str,
    *,
    appno: str = "099037115",
    owner: str = "Acme Designers Ltd.",
    status: str = "REGISTERED_AND_FULLY_PUBLISHED",
    locarno: list[str] | None = None,
) -> dict:
    return {
        "designNumber": design_number,
        "applicationNumber": appno,
        "status": status,
        "applicants": [{"office": "EM", "name": owner}],
        "locarnoClasses": locarno or ["14.03", "14.04"],
        "applicationDate": "2022-06-01",
        "registrationDate": "2022-09-15",
    }


def _make_search_result(rows: list[dict], *, total: int | None = None, page: int = 0) -> _FakeModel:
    total_elements = total if total is not None else len(rows)
    size = max(len(rows), 10)
    total_pages = max(1, -(-total_elements // size))
    payload = {
        "designs": rows,
        "totalElements": total_elements,
        "totalPages": total_pages,
        "size": size,
        "page": page,
    }
    return _FakeModel(**payload)


def _make_detail(design_number: str, **kwargs: Any) -> _FakeModel:
    return _FakeModel(**_make_design_row(design_number, **kwargs))


# ──────────────────────────────────────────────────────────────────────
# search_euipo_designs — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_euipo_designs_returns_lean_list_envelope_by_default():
    rows = [
        _make_design_row("099037115-0001"),
        _make_design_row("099037115-0002", owner="Acme Designers Ltd."),
    ]
    result_model = _make_search_result(rows, total=2)

    with patch("patent_client_agents.mcp.tools.euipo.EuipoDesignsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_euipo_designs(query="status==REGISTERED_AND_FULLY_PUBLISHED")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "EUIPO"
    assert "/design-search/designs" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "design_number",
        "application_number",
        "owner_name",
        "status",
        "application_date",
        "registration_date",
        "locarno_classes",
    }
    assert result.items[0]["design_number"] == "099037115-0001"
    assert result.items[0]["locarno_classes"] == ["14.03", "14.04"]
    assert "EUIPO designs" in result.summary
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_euipo_designs_full_true_returns_upstream_shape():
    rows = [_make_design_row("099037115-0001")]
    result_model = _make_search_result(rows, total=1)

    with patch("patent_client_agents.mcp.tools.euipo.EuipoDesignsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_euipo_designs(full=True)

    # Full mode returns the upstream camelCase row.
    assert "designNumber" in result.items[0]
    assert "applicationNumber" in result.items[0]
    assert "locarnoClasses" in result.items[0]


@pytest.mark.asyncio
async def test_search_euipo_designs_more_available_when_paged():
    rows = [_make_design_row(f"099037115-000{i}") for i in range(10)]
    result_model = _make_search_result(rows, total=50, page=0)

    with patch("patent_client_agents.mcp.tools.euipo.EuipoDesignsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_euipo_designs(size=10)

    assert result.more_available is True
    assert "10 of 50 hits" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_euipo_design — §5.4 list-accepting, order preservation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_euipo_design_single_returns_list_envelope():
    detail = _make_detail("099037115-0001", owner="Acme Designers Ltd.")

    with patch("patent_client_agents.mcp.tools.euipo.EuipoDesignsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_design = AsyncMock(return_value=detail)

        result = await get_euipo_design(design_number="099037115-0001")

    mock_client.get_design.assert_awaited_once_with("099037115-0001")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "EUIPO"
    assert "/design-search/designs/099037115-0001" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["designNumber"] == "099037115-0001"
    assert "RCD 099037115-0001" in result.summary


@pytest.mark.asyncio
async def test_get_euipo_design_list_preserves_order():
    numbers = ["099037115-0001", "099037115-0002", "099037115-0003"]
    details = [_make_detail(n) for n in numbers]

    with patch("patent_client_agents.mcp.tools.euipo.EuipoDesignsClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_design = AsyncMock(side_effect=details)

        result = await get_euipo_design(design_number=numbers)

    assert isinstance(result, ListEnvelope)
    assert [r["designNumber"] for r in result.items] == numbers
    assert result.provenance.source_url.endswith("/design-search/designs")
    assert "Fetched 3 EUIPO designs" in result.summary


@pytest.mark.asyncio
async def test_get_euipo_design_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_euipo_design(design_number=[])
