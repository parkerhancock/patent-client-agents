from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.ipi_swissreg.models import (
    IpiPatentRecord,
    IpiPublicationRecord,
    IpiSearchMeta,
    IpiSpcRecord,
    IpiTrademarkRecord,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "api_name", "row", "lean_field", "label"),
    [
        (
            "search_ipi_patents",
            "search_ipi_patents",
            IpiPatentRecord(identifier="CH1", title="Controller", raw={"extension": "patent"}),
            "title",
            "patent",
        ),
        (
            "search_ipi_trademarks",
            "search_ipi_trademarks",
            IpiTrademarkRecord(
                identifier="TM1", word_element="NECKTIE", raw={"extension": "trademark"}
            ),
            "word_element",
            "trademark",
        ),
        (
            "search_ipi_spcs",
            "search_ipi_spcs",
            IpiSpcRecord(identifier="S1", product="Medicine", raw={"extension": "spc"}),
            "product",
            "SPC",
        ),
        (
            "search_ipi_patent_publications",
            "search_ipi_patent_publications",
            IpiPublicationRecord(
                identifier="P1",
                right_type="patent",
                publication_title="Grant",
                raw={"extension": "patent-publication"},
            ),
            "publication_title",
            "patent publication",
        ),
        (
            "search_ipi_spc_publications",
            "search_ipi_spc_publications",
            IpiPublicationRecord(
                identifier="S1",
                right_type="spc",
                publication_title="SPC grant",
                raw={"extension": "spc-publication"},
            ),
            "publication_title",
            "SPC publication",
        ),
    ],
)
async def test_search_envelopes_expose_cursor_and_schema_status(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    api_name: str,
    row: IpiPatentRecord | IpiTrademarkRecord | IpiSpcRecord | IpiPublicationRecord,
    lean_field: str,
    label: str,
) -> None:
    import patent_client_agents.mcp.tools.ipi_swissreg as tools

    meta = IpiSearchMeta(total_item_count=20, item_count=1, next_cursor="next-page")
    monkeypatch.setattr(tools.api, api_name, AsyncMock(return_value=([row], meta)))
    result = await getattr(tools, tool_name)("query")
    full_result = await getattr(tools, tool_name)("query", full=True)

    assert isinstance(result, ListEnvelope)
    assert result.items[0][lean_field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert result.next_cursor == "next-page"
    assert result.more_available is True
    assert label in result.summary
    assert "Schema-tested only" in result.summary
    assert "live account compatibility unverified" in result.provenance.source_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "method_name", "record", "lean_field"),
    [
        (
            "get_ipi_patent",
            "get_patent",
            IpiPatentRecord(
                identifier="CH1",
                title="Controller",
                publication_date=date(2024, 1, 1),
                raw={"extension": "patent"},
            ),
            "title",
        ),
        (
            "get_ipi_trademark",
            "get_trademark",
            IpiTrademarkRecord(
                identifier="TM1", word_element="NECKTIE", raw={"extension": "trademark"}
            ),
            "word_element",
        ),
        (
            "get_ipi_spc",
            "get_spc",
            IpiSpcRecord(identifier="S1", product="Medicine", raw={"extension": "spc"}),
            "product",
        ),
    ],
)
async def test_fetch_tools_use_one_bounded_client(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    method_name: str,
    record: IpiPatentRecord | IpiTrademarkRecord | IpiSpcRecord,
    lean_field: str,
) -> None:
    import patent_client_agents.mcp.tools.ipi_swissreg as tools

    inner = AsyncMock()
    getattr(inner, method_name).return_value = record

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(tools, "IpiSwissregClient", Context)
    result = await getattr(tools, tool_name)([record.identifier, record.identifier])
    full_result = await getattr(tools, tool_name)(record.identifier, full=True)
    assert len(result.items) == 2
    assert result.items[0][lean_field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert getattr(inner, method_name).await_count == 3


@pytest.mark.asyncio
async def test_usage_and_validation() -> None:
    import patent_client_agents.mcp.tools.ipi_swissreg as tools

    usage = await tools.ipi_swissreg_usage()
    assert "synthetic XML fixtures" in usage
    assert "Community help is welcome" in usage
    with pytest.raises(ValidationError):
        await tools.search_ipi_patents("q", limit=0)
    with pytest.raises(ValidationError):
        await tools.search_ipi_trademarks("q", limit=65)
    with pytest.raises(ValidationError):
        await tools.search_ipi_spcs("q", limit=0)
    with pytest.raises(ValidationError):
        await tools.search_ipi_patent_publications("q", limit=65)
    with pytest.raises(ValidationError):
        await tools.search_ipi_spc_publications("q", limit=0)
    with pytest.raises(ValidationError):
        await tools.get_ipi_patent([])
    with pytest.raises(ValidationError):
        await tools.get_ipi_spc([str(index) for index in range(51)])
