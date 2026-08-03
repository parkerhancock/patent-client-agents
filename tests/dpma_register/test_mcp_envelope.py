from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.dpma_register.models import (
    DesignRecord,
    PatentUtilityRecord,
    TrademarkRecord,
)


@pytest.mark.asyncio
async def test_patent_search_marks_mock_only_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import patent_client_agents.mcp.tools.dpma_register as tools

    row = PatentUtilityRecord(
        identifier="10 2023 123 456.7",
        application_number="10 2023 123 456.7",
        title="Adaptive charging controller",
        right_type="patent",
        raw={"future-extension": "preserved"},
    )
    monkeypatch.setattr(
        tools.api,
        "search_dpma_patents",
        AsyncMock(return_value=([row], 1)),
    )

    result = await tools.search_dpma_patents("AKZ=10 2023")

    assert isinstance(result, ListEnvelope)
    assert "Mock-only tested" in result.summary
    assert "Mock-only tested" in result.provenance.source_name
    assert "raw" not in result.items[0]
    assert result.next_cursor is None


@pytest.mark.asyncio
async def test_full_search_preserves_raw_xml(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import patent_client_agents.mcp.tools.dpma_register as tools

    row = PatentUtilityRecord(
        identifier="DE1",
        right_type="patent",
        raw={"future-extension": "preserved"},
    )
    monkeypatch.setattr(
        tools.api,
        "search_dpma_patents",
        AsyncMock(return_value=([row], 1)),
    )

    result = await tools.search_dpma_patents("AKZ=DE1", full=True)

    assert result.items[0]["raw"]["future-extension"] == "preserved"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "api_name", "row", "lean_field"),
    [
        (
            "search_dpma_trademarks",
            "search_dpma_trademarks",
            TrademarkRecord(
                identifier="TM1",
                mark_text="NECKTIE",
                registration_date=date(2024, 8, 1),
                raw={"extension": "trademark"},
            ),
            "mark_text",
        ),
        (
            "search_dpma_designs",
            "search_dpma_designs",
            DesignRecord(
                identifier="D1",
                product_indication="Computer enclosure",
                registration_date=date(2024, 8, 1),
                raw={"extension": "design"},
            ),
            "product_indication",
        ),
    ],
)
async def test_other_search_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    api_name: str,
    row: TrademarkRecord | DesignRecord,
    lean_field: str,
) -> None:
    import patent_client_agents.mcp.tools.dpma_register as tools

    monkeypatch.setattr(tools.api, api_name, AsyncMock(return_value=([row], 1000)))

    result = await getattr(tools, tool_name)("query", full=False)
    full_result = await getattr(tools, tool_name)("query", full=True)

    assert result.items[0][lean_field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert result.more_available is True
    assert "account cap reached" in result.summary


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "record", "method_name", "lean_field"),
    [
        (
            "get_dpma_patent",
            PatentUtilityRecord(
                identifier="P1",
                title="Patent title",
                right_type="patent",
                raw={"extension": "patent"},
            ),
            "get_patent",
            "title",
        ),
        (
            "get_dpma_trademark",
            TrademarkRecord(
                identifier="T1",
                mark_text="NECKTIE",
                raw={"extension": "trademark"},
            ),
            "get_trademark",
            "mark_text",
        ),
        (
            "get_dpma_design",
            DesignRecord(
                identifier="D1",
                product_indication="Computer enclosure",
                raw={"extension": "design"},
            ),
            "get_design",
            "product_indication",
        ),
    ],
)
async def test_fetch_tools_use_bounded_client_fanout(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    record: PatentUtilityRecord | TrademarkRecord | DesignRecord,
    method_name: str,
    lean_field: str,
) -> None:
    import patent_client_agents.mcp.tools.dpma_register as tools

    inner = AsyncMock()
    getattr(inner, method_name).return_value = record

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(tools, "DpmaRegisterClient", Context)

    result = await getattr(tools, tool_name)([record.identifier, record.identifier])
    full_result = await getattr(tools, tool_name)(record.identifier, full=True)

    assert len(result.items) == 2
    assert result.items[0][lean_field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert getattr(inner, method_name).await_count == 3


@pytest.mark.asyncio
async def test_usage_resource_invites_community_validation() -> None:
    import patent_client_agents.mcp.tools.dpma_register as tools

    usage = await tools.dpma_register_usage()

    assert "synthetic XML fixtures" in usage
    assert "community help is welcome" in usage


@pytest.mark.asyncio
async def test_tool_validation_rejects_bad_limits_and_lists() -> None:
    import patent_client_agents.mcp.tools.dpma_register as tools

    with pytest.raises(ValidationError):
        await tools.search_dpma_patents("query", limit=0)
    with pytest.raises(ValidationError):
        await tools.search_dpma_trademarks("query", limit=1001)
    with pytest.raises(ValidationError):
        await tools.search_dpma_designs("query", limit=0)
    with pytest.raises(ValidationError):
        await tools.get_dpma_patent([])
    with pytest.raises(ValidationError):
        await tools.get_dpma_design([str(index) for index in range(51)])
