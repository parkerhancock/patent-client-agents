from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from mcp_data_core.envelope import ListEnvelope
from mcp_data_core.exceptions import ValidationError
from patent_client_agents.thai_dip.models import (
    ThaiDipCopyrightRecord,
    ThaiDipGiRecord,
    ThaiDipPatentRecord,
    ThaiDipSongRecord,
    ThaiDipTrademarkRecord,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "api_method", "record", "field", "kwargs"),
    [
        (
            "search_thai_dip_patents",
            "search_thai_dip_patents",
            ThaiDipPatentRecord(
                identifier="P1", right_type="design", title="Sensor", raw={"extra": 1}
            ),
            "title",
            {"right_type": "design"},
        ),
        (
            "search_thai_dip_trademarks",
            "search_thai_dip_trademarks",
            ThaiDipTrademarkRecord(identifier="T1", mark_name="MARK", raw={"extra": 1}),
            "mark_name",
            {},
        ),
        (
            "search_thai_dip_copyrights",
            "search_thai_dip_copyrights",
            ThaiDipCopyrightRecord(identifier="C1", work_name="Work", raw={"extra": 1}),
            "work_name",
            {},
        ),
        (
            "search_thai_dip_songs",
            "search_thai_dip_songs",
            ThaiDipSongRecord(identifier="S1", song_name="Song", raw={"extra": 1}),
            "song_name",
            {},
        ),
        (
            "search_thai_dip_geographical_indications",
            "search_thai_dip_geographical_indications",
            ThaiDipGiRecord(identifier="G1", name="Rice", raw={"extra": 1}),
            "name",
            {},
        ),
    ],
)
async def test_search_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    api_method: str,
    record: object,
    field: str,
    kwargs: dict[str, str],
) -> None:
    import patent_client_agents.mcp.tools.thai_dip as tools

    monkeypatch.setattr(tools.api, api_method, AsyncMock(return_value=([record], 2)))
    result = await getattr(tools, tool)("query", **kwargs)
    full_result = await getattr(tools, tool)("query", full=True, **kwargs)

    assert isinstance(result, ListEnvelope)
    assert result.items[0][field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert result.more_available is True
    assert result.next_cursor is None
    assert "live compatibility unverified" in result.provenance.source_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "method", "record", "field", "kwargs"),
    [
        (
            "get_thai_dip_patent",
            "get_patent",
            ThaiDipPatentRecord(
                identifier="P1", right_type="petty_patent", title="Sensor", raw={"extra": 1}
            ),
            "title",
            {"right_type": "petty_patent"},
        ),
        (
            "get_thai_dip_trademark",
            "get_trademark",
            ThaiDipTrademarkRecord(identifier="T1", mark_name="MARK", raw={"extra": 1}),
            "mark_name",
            {},
        ),
        (
            "get_thai_dip_copyright",
            "get_copyright",
            ThaiDipCopyrightRecord(identifier="C1", work_name="Work", raw={"extra": 1}),
            "work_name",
            {},
        ),
        (
            "get_thai_dip_geographical_indication",
            "get_geographical_indication",
            ThaiDipGiRecord(identifier="G1", name="Rice", raw={"extra": 1}),
            "name",
            {},
        ),
    ],
)
async def test_fetch_envelopes_use_one_client(
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    method: str,
    record: object,
    field: str,
    kwargs: dict[str, str],
) -> None:
    import patent_client_agents.mcp.tools.thai_dip as tools

    inner = AsyncMock()
    getattr(inner, method).return_value = record

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(tools, "ThaiDipClient", Context)
    result = await getattr(tools, tool)(["1", "2"], **kwargs)
    full_result = await getattr(tools, tool)("1", full=True, **kwargs)
    assert len(result.items) == 2
    assert result.items[0][field]
    assert "raw" not in result.items[0]
    assert full_result.items[0]["raw"]
    assert getattr(inner, method).await_count == 3
    assert "no distinct fetch operation" in result.summary


@pytest.mark.asyncio
async def test_usage_and_validation() -> None:
    import patent_client_agents.mcp.tools.thai_dip as tools

    usage = await tools.thai_dip_usage()
    assert "synthetic JSON fixtures" in usage
    assert "Community help is welcome" in usage

    searches = [
        tools.search_thai_dip_patents,
        tools.search_thai_dip_trademarks,
        tools.search_thai_dip_copyrights,
        tools.search_thai_dip_songs,
        tools.search_thai_dip_geographical_indications,
    ]
    for search in searches:
        with pytest.raises(ValidationError):
            await search("q", limit=0)
    with pytest.raises(ValidationError):
        await tools.get_thai_dip_patent([])
    with pytest.raises(ValidationError):
        await tools.get_thai_dip_trademark([str(index) for index in range(51)])
