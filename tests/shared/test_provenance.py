"""Provenance reports cache hits and original fetch times (CONNECTOR_STANDARDS §3)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import pytest
from fastmcp import Client, FastMCP

from mcp_data_core.envelope import ListEnvelope
from patent_client_agents.mcp.full import ip_mcp
from patent_client_agents.mcp.middleware import FetchTracking
from patent_client_agents.shared.client import ConnectorClient
from patent_client_agents.shared.provenance import provenance_for, track_fetches

URL = "https://source.test/records"


def _seconds(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds())


class _Client(ConnectorClient):
    DEFAULT_BASE_URL = "https://source.test"
    CACHE_NAME = "provenance_test"


def _cacheable(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json={"ok": True}, headers={"Cache-Control": "max-age=600"})


async def test_live_then_cached_response(tmp_path: Path) -> None:
    async with _Client(cache_path=tmp_path, transport=httpx2.MockTransport(_cacheable)) as client:
        with track_fetches():
            before = datetime.now(UTC)
            await client._request("GET", "/a")
            live = provenance_for(URL, "Source")
        time.sleep(0.05)
        with track_fetches():
            second_call = datetime.now(UTC)
            await client._request("GET", "/a")
            cached = provenance_for(URL, "Source")

    assert live.cache_hit is False
    assert live.retrieved_at >= before
    assert cached.cache_hit is True
    # The cached response reports when it was originally fetched, not when it was read.
    assert _seconds(cached.retrieved_at, live.retrieved_at) < 0.01
    assert _seconds(second_call, cached.retrieved_at) >= 0.04


async def test_mixed_call_is_not_a_cache_hit_and_reports_oldest_fetch(tmp_path: Path) -> None:
    async with _Client(cache_path=tmp_path, transport=httpx2.MockTransport(_cacheable)) as client:
        with track_fetches():
            await client._request("GET", "/a")
            first = provenance_for(URL, "Source").retrieved_at
        time.sleep(0.05)
        with track_fetches():
            await client._request("GET", "/a")  # cached
            await client._request("GET", "/b")  # live
            mixed = provenance_for(URL, "Source")

    assert mixed.cache_hit is False
    assert _seconds(mixed.retrieved_at, first) < 0.01


async def test_explicit_values_win_and_no_scope_falls_back(tmp_path: Path) -> None:
    fixed = datetime(2020, 1, 1, tzinfo=UTC)
    async with _Client(cache_path=tmp_path, transport=httpx2.MockTransport(_cacheable)) as client:
        await client._request("GET", "/a")
        with track_fetches():
            await client._request("GET", "/a")
            explicit = provenance_for(URL, "Source", cache_hit=False, retrieved_at=fixed)
    assert (explicit.cache_hit, explicit.retrieved_at) == (False, fixed)

    outside = provenance_for(URL, "Source")
    assert outside.cache_hit is False
    assert (datetime.now(UTC) - outside.retrieved_at).total_seconds() < 5


async def test_mcp_tool_calls_report_cache_hits_through_the_middleware(
    tmp_path: Path,
) -> None:
    child = FastMCP("child")

    @child.tool
    async def get_record() -> ListEnvelope[dict]:
        async with _Client(
            cache_path=tmp_path, transport=httpx2.MockTransport(_cacheable)
        ) as client:
            data = (await client._request("GET", "/a")).json()
        return ListEnvelope[dict](summary="one", items=[data], provenance=provenance_for(URL, "S"))

    parent = FastMCP("parent")
    parent.add_middleware(FetchTracking())
    parent.mount(child)

    async with Client(parent) as mcp_client:
        first = (await mcp_client.call_tool("get_record", {})).structured_content
        second = (await mcp_client.call_tool("get_record", {})).structured_content

    assert first["provenance"]["cache_hit"] is False
    assert second["provenance"]["cache_hit"] is True
    first_at = datetime.fromisoformat(first["provenance"]["retrieved_at"])
    second_at = datetime.fromisoformat(second["provenance"]["retrieved_at"])
    assert _seconds(second_at, first_at) < 0.01


def test_server_registers_fetch_tracking() -> None:
    assert any(isinstance(m, FetchTracking) for m in ip_mcp.middleware)


@pytest.mark.parametrize("from_cache", [True, False])
async def test_hook_is_installed_once_on_injected_clients(from_cache: bool) -> None:
    shared = httpx2.AsyncClient(transport=httpx2.MockTransport(_cacheable))
    _Client(client=shared, use_cache=False)
    _Client(client=shared, use_cache=False)
    assert len(shared.event_hooks["response"]) == 1
    await shared.aclose()
