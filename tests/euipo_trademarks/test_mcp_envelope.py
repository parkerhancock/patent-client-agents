"""Envelope-shape tests for the migrated EUIPO trademark MCP tools.

Verifies CONNECTOR_STANDARDS.md §5.9 (envelope), §5.4 (list-accepting
fetches; no batch tools), §5.5 (lean default + ``full=True`` opt-in),
and §5.6 (cross-referenced docstrings).

Mocks ``EuipoTrademarksClient`` at the boundary.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel, ConfigDict

from law_tools_core.envelope import ListEnvelope, Provenance
from law_tools_core.exceptions import ValidationError
from patent_client_agents.mcp.tools.euipo import (
    get_euipo_trademark,
    search_euipo_trademarks,
)

# ──────────────────────────────────────────────────────────────────────
# Fakes — mirror the upstream camelCase JSON shape after model_dump
# ──────────────────────────────────────────────────────────────────────


class _FakeModel(BaseModel):
    """Pydantic model that round-trips arbitrary camelCase fields via model_dump."""

    model_config = ConfigDict(extra="allow")

    def model_dump(self, **kwargs: Any) -> dict:  # type: ignore[override]
        # Force by_alias to mirror the real EUIPO models' camelCase output.
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


def _make_tm_row(
    appno: str,
    *,
    verbal: str = "ACME",
    owner: str = "Acme Corp.",
    status: str = "REGISTERED",
    nice: list[int] | None = None,
) -> dict:
    return {
        "applicationNumber": appno,
        "status": status,
        "markFeature": "WORD",
        "wordMarkSpecification": {"verbalElement": verbal},
        "applicants": [{"office": "EM", "name": owner}],
        "niceClasses": nice or [25, 28],
        "applicationDate": "2020-01-15",
        "registrationDate": "2021-03-10",
    }


def _make_search_result(rows: list[dict], *, total: int | None = None, page: int = 0) -> _FakeModel:
    total_elements = total if total is not None else len(rows)
    size = max(len(rows), 10)
    total_pages = max(1, -(-total_elements // size))
    payload = {
        "trademarks": rows,
        "totalElements": total_elements,
        "totalPages": total_pages,
        "size": size,
        "page": page,
    }
    return _FakeModel(**payload)


def _make_detail(appno: str, **kwargs: Any) -> _FakeModel:
    return _FakeModel(**_make_tm_row(appno, **kwargs))


# ──────────────────────────────────────────────────────────────────────
# search_euipo_trademarks — §5.9, §5.5
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_euipo_trademarks_returns_lean_list_envelope_by_default():
    rows = [
        _make_tm_row("000274084", verbal="RIZLA+"),
        _make_tm_row("000274085", verbal="ACME"),
    ]
    result_model = _make_search_result(rows, total=2)

    with patch("patent_client_agents.mcp.tools.euipo.EuipoTrademarksClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_euipo_trademarks(query="status==REGISTERED")

    assert isinstance(result, ListEnvelope)
    assert isinstance(result.provenance, Provenance)
    assert result.provenance.source_name == "EUIPO"
    assert "/trademark-search/trademarks" in result.provenance.source_url
    assert len(result.items) == 2
    assert set(result.items[0].keys()) == {
        "application_number",
        "verbal_element",
        "owner_name",
        "status",
        "mark_feature",
        "application_date",
        "registration_date",
        "nice_classes",
    }
    assert result.items[0]["application_number"] == "000274084"
    assert result.items[0]["verbal_element"] == "RIZLA+"
    assert "EUIPO trademarks" in result.summary
    # Only one page of 2/2 — no more available.
    assert result.more_available is False


@pytest.mark.asyncio
async def test_search_euipo_trademarks_full_true_returns_upstream_shape():
    rows = [_make_tm_row("000274084", verbal="RIZLA+")]
    result_model = _make_search_result(rows, total=1)

    with patch("patent_client_agents.mcp.tools.euipo.EuipoTrademarksClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_euipo_trademarks(query="ACME", full=True)

    # Full mode returns the upstream camelCase row.
    assert "applicationNumber" in result.items[0]
    assert result.items[0]["applicationNumber"] == "000274084"
    assert "wordMarkSpecification" in result.items[0]


@pytest.mark.asyncio
async def test_search_euipo_trademarks_more_available_when_paged():
    rows = [_make_tm_row(f"00027408{i}") for i in range(10)]
    # totalElements=100, page 0 of 10 — more pages available.
    result_model = _make_search_result(rows, total=100, page=0)

    with patch("patent_client_agents.mcp.tools.euipo.EuipoTrademarksClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.search = AsyncMock(return_value=result_model)

        result = await search_euipo_trademarks(query="status==REGISTERED", size=10)

    assert result.more_available is True
    assert "10 of 100 hits" in result.summary


# ──────────────────────────────────────────────────────────────────────
# get_euipo_trademark — §5.4 list-accepting, order preservation
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_euipo_trademark_single_returns_list_envelope():
    detail = _make_detail("000274084", verbal="RIZLA+", owner="John Player & Sons")

    with patch("patent_client_agents.mcp.tools.euipo.EuipoTrademarksClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trademark = AsyncMock(return_value=detail)

        result = await get_euipo_trademark(application_number="000274084")

    mock_client.get_trademark.assert_awaited_once_with("000274084")
    assert isinstance(result, ListEnvelope)
    assert result.provenance.source_name == "EUIPO"
    assert "/trademark-search/trademarks/000274084" in result.provenance.source_url
    assert len(result.items) == 1
    assert result.items[0]["applicationNumber"] == "000274084"
    assert "EUTM 000274084" in result.summary
    assert "RIZLA+" in result.summary


@pytest.mark.asyncio
async def test_get_euipo_trademark_list_preserves_order():
    appnos = ["000274084", "000274085", "000274086"]
    details = [_make_detail(n) for n in appnos]

    with patch("patent_client_agents.mcp.tools.euipo.EuipoTrademarksClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_trademark = AsyncMock(side_effect=details)

        result = await get_euipo_trademark(application_number=appnos)

    assert isinstance(result, ListEnvelope)
    assert [r["applicationNumber"] for r in result.items] == appnos
    # Multi-call provenance should point at the collection, not a single record.
    assert result.provenance.source_url.endswith("/trademark-search/trademarks")
    assert "Fetched 3 EUIPO trademarks" in result.summary


@pytest.mark.asyncio
async def test_get_euipo_trademark_empty_list_raises():
    with pytest.raises(ValidationError, match="at least one"):
        await get_euipo_trademark(application_number=[])
