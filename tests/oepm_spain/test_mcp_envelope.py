from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.oepm_spain.models import (
    OepmDesignRecord,
    OepmPatentRecord,
    OepmTrademarkRecord,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "method_name", "record", "lean_field"),
    [
        (
            "get_oepm_patent",
            "get_patent",
            OepmPatentRecord(
                identifier="P1",
                modality="P",
                title="Controller",
                filing_date=date(2024, 1, 1),
                raw={"extension": "patent"},
            ),
            "title",
        ),
        (
            "get_oepm_trademark",
            "get_trademark",
            OepmTrademarkRecord(
                identifier="M1",
                modality="M",
                denomination="NECKTIE",
                raw={"extension": "trademark"},
            ),
            "denomination",
        ),
        (
            "get_oepm_design",
            "get_design",
            OepmDesignRecord(
                identifier="D1",
                modality="D",
                filing_place="Madrid",
                raw={"extension": "design"},
            ),
            "filing_place",
        ),
    ],
)
async def test_fetch_tools_use_one_bounded_client(
    monkeypatch: pytest.MonkeyPatch,
    tool_name: str,
    method_name: str,
    record: OepmPatentRecord | OepmTrademarkRecord | OepmDesignRecord,
    lean_field: str,
) -> None:
    import patent_client_agents.mcp.tools.oepm_spain as tools

    inner = AsyncMock()
    getattr(inner, method_name).return_value = record

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(tools, "OepmSpainClient", Context)
    result = await getattr(tools, tool_name)([record.identifier, record.identifier])
    full_result = await getattr(tools, tool_name)(record.identifier, full=True)
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 2
    assert result.items[0][lean_field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert "Public-WSDL tested only" in result.summary
    assert "live account compatibility unverified" in result.provenance.source_name
    assert getattr(inner, method_name).await_count == 3


@pytest.mark.asyncio
async def test_usage_and_identifier_validation() -> None:
    import patent_client_agents.mcp.tools.oepm_spain as tools

    usage = await tools.oepm_spain_usage()
    assert "synthetic SOAP/XML fixtures" in usage
    assert "does not expose free-text search" in usage
    assert "Community help is welcome" in usage
    with pytest.raises(ValidationError):
        await tools.get_oepm_patent([])
    with pytest.raises(ValidationError):
        await tools.get_oepm_trademark([" "])
    with pytest.raises(ValidationError):
        await tools.get_oepm_design([str(index) for index in range(51)])
