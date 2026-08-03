from __future__ import annotations

from datetime import date
from typing import Literal
from unittest.mock import AsyncMock

import pytest

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.iponz_new_zealand.models import (
    IponzDesignRecord,
    IponzPatentRecord,
    IponzRegisterSummary,
    IponzTrademarkRecord,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "method_name", "record", "lean_field"),
    [
        (
            "get_iponz_patent",
            "get_patent",
            IponzPatentRecord(
                identifier="P1", patent_number="P1", title="Controller", raw={"x": 1}
            ),
            "title",
        ),
        (
            "get_iponz_trademark",
            "get_trademark",
            IponzTrademarkRecord(
                identifier="T1", application_number="T1", title="NECKTIE", raw={"x": 1}
            ),
            "title",
        ),
        (
            "get_iponz_design",
            "get_design",
            IponzDesignRecord(
                identifier="D1", registration_number="D1", title="Clasp", raw={"x": 1}
            ),
            "title",
        ),
    ],
)
async def test_fetch_tools_use_one_bounded_client(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    method_name: str,
    record: IponzPatentRecord | IponzTrademarkRecord | IponzDesignRecord,
    lean_field: str,
) -> None:
    import patent_client_agents.mcp.tools.iponz_new_zealand as tools

    inner = AsyncMock()
    getattr(inner, method_name).return_value = record

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(tools, "IponzClient", Context)
    result = await getattr(tools, tool_name)([record.identifier, record.identifier])
    full_result = await getattr(tools, tool_name)(record.identifier, full=True)
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 2
    assert result.items[0][lean_field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert getattr(inner, method_name).await_count == 3
    assert "live subscription unverified" in result.provenance.source_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "api_name", "right_type"),
    [
        ("list_iponz_patents_updated", "list_iponz_patents_updated", "patent"),
        ("list_iponz_trademarks_updated", "list_iponz_trademarks_updated", "trademark"),
        ("list_iponz_designs_updated", "list_iponz_designs_updated", "design"),
        ("list_iponz_designs_registered", "list_iponz_designs_registered", "design"),
    ],
)
async def test_list_tools_return_lean_full_and_truncation(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    api_name: str,
    right_type: Literal["patent", "trademark", "design"],
) -> None:
    import patent_client_agents.mcp.tools.iponz_new_zealand as tools

    rows = [
        IponzRegisterSummary(
            identifier="1",
            right_type=right_type,
            status="Registered",
            event_date=date(2026, 1, 1),
            raw={"extension": "kept"},
        ),
        IponzRegisterSummary(identifier="2", right_type=right_type, status="Pending", raw={"x": 2}),
    ]
    monkeypatch.setattr(tools.api, api_name, AsyncMock(return_value=rows))
    start, end = date(2026, 1, 1), date(2026, 1, 2)
    result = await getattr(tools, tool_name)(start, end, limit=1)
    full_result = await getattr(tools, tool_name)(start, end, full=True)
    assert result.items[0]["right_type"] == right_type
    assert "raw" not in result.items[0]
    assert result.more_available is True
    assert result.next_cursor is None
    assert "Split the date range" in result.summary
    assert full_result.items[0]["raw"]


@pytest.mark.asyncio
async def test_usage_and_validation() -> None:
    import patent_client_agents.mcp.tools.iponz_new_zealand as tools

    usage = await tools.iponz_new_zealand_usage()
    assert "synthetic XML fixtures" in usage
    assert "Community help is welcome" in usage
    assert "renewals" in usage
    with pytest.raises(ValidationError):
        await tools.get_iponz_patent([])
    with pytest.raises(ValidationError):
        await tools.get_iponz_design([str(index) for index in range(51)])
    with pytest.raises(ValidationError):
        await tools.list_iponz_patents_updated(date(2026, 1, 1), date(2026, 1, 2), limit=0)
    with pytest.raises(ValidationError):
        await tools.list_iponz_designs_registered(date(2026, 1, 1), date(2026, 1, 2), limit=2001)
