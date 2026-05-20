"""MCP envelope shape tests for the PRV (Sweden) tools.

Confirms every tool returns a ``ListEnvelope`` per CONNECTOR_STANDARDS
§5.9, that lean projection drops the first-drawing base64 image, and
that provenance points at the right host.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from law_tools_core.envelope import ListEnvelope
from patent_client_agents.mcp.tools.prv_se import (
    get_prv_patent,
    search_prv_designs,
    search_prv_patents,
    search_prv_spcs,
    search_prv_trademarks,
)
from patent_client_agents.prv_se import PrvClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


@asynccontextmanager
async def _mock_client(handler) -> AsyncIterator[PrvClient]:  # type: ignore[no-untyped-def]
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    async with PrvClient(client=client) as wrapped:
        yield wrapped


# ----------------------------------------------------------------------
# search_prv_patents
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prv_patents_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture("patents-search.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await search_prv_patents(text="Volvo", page_size=5)
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "Volvo" in result.summary
    assert "3,309" in result.summary or "3309" in result.summary
    assert result.provenance.source_url.startswith("https://patents-search-api.prv.se")
    assert "PRV" in result.provenance.source_name


# ----------------------------------------------------------------------
# get_prv_patent
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_prv_patent_envelope_lean_drops_drawing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture("patent-get.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await get_prv_patent("SE2615555-6")
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    record = result.items[0]
    assert record["applicationNumberFormatted"] == "SE2615555-6"
    # Lean projection drops the base64 image payload.
    assert "data" not in record["firstDrawing"]
    # But keeps the metadata.
    assert record["firstDrawing"]["pageNumber"] == 1
    assert record["firstDrawing"]["applicationNumber"] == "26155556"


@pytest.mark.asyncio
async def test_get_prv_patent_envelope_full_keeps_drawing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture("patent-get.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await get_prv_patent("SE2615555-6", full=True)
    record = result.items[0]
    assert isinstance(record["firstDrawing"]["data"], str)
    assert len(record["firstDrawing"]["data"]) > 1000


@pytest.mark.asyncio
async def test_get_prv_patent_accepts_list(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patent-get.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await get_prv_patent(["SE2615555-6", "SE2615536-6"])
    assert len(result.items) == 2
    assert len(captured) == 2


@pytest.mark.asyncio
async def test_get_prv_patent_rejects_empty_input() -> None:
    from law_tools_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await get_prv_patent([])


# ----------------------------------------------------------------------
# search_prv_trademarks
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prv_trademarks_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture("tm-search.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await search_prv_trademarks(text="IKEA", page_size=5)
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "IKEA" in result.summary
    assert result.provenance.source_url.startswith("https://dv-search-api.prv.se")


# ----------------------------------------------------------------------
# search_prv_designs
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prv_designs_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture("design-search.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await search_prv_designs(text="stol", page_size=5)
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "stol" in result.summary
    assert result.provenance.source_url.startswith("https://dv-search-api.prv.se")


# ----------------------------------------------------------------------
# search_prv_spcs
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prv_spcs_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture("spc-search.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrvClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrvClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prv_se.PrvClient",
        lambda: _factory(),
    )

    result = await search_prv_spcs(applicants="AstraZeneca", page_size=5)
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "AstraZeneca" in result.summary
    assert result.provenance.source_url.endswith("/searchpatentspc/patentsearchspc/")
    # Row carries the SPC term + substance fields.
    row = result.items[0]
    assert row["substance"]
    assert row["validFromDate"]
    assert row["validUntilDate"]
    assert row["applicationNumberSpcFormatted"]


@pytest.mark.asyncio
async def test_search_prv_spcs_rejects_empty_filters() -> None:
    with pytest.raises(ValueError):
        await search_prv_spcs()
