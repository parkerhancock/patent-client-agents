"""Tokens, sessions and rate limiters are shared across clients in a process.

MCP tools build a new client per call; before this, every call logged in again
and per-office request caps never applied across calls.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from patent_client_agents.euipo_trademarks import EuipoTrademarksClient
from patent_client_agents.ip_australia_patents import IpAustraliaPatentsClient
from patent_client_agents.ipi_swissreg.client import TOKEN_URL as IPI_TOKEN_URL
from patent_client_agents.ipi_swissreg.client import IpiSwissregClient
from patent_client_agents.jpo.client import JpoClient
from patent_client_agents.shared.auth import LoopLock, process_shared, reset_process_shared

IPI_FIXTURES = Path(__file__).parents[1] / "ipi_swissreg" / "fixtures"


def _token_counting(token_path_suffix: str, body: object = None, **response: object):
    """Transport that answers the token endpoint and counts token requests."""
    hits = {"token": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path.endswith(token_path_suffix) or str(request.url) == token_path_suffix:
            hits["token"] += 1
            return httpx2.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx2.Response(200, json=body if body is not None else {}, **response)  # type: ignore[arg-type]

    return httpx2.MockTransport(handler), hits


async def test_ip_australia_clients_share_one_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "id")
    monkeypatch.setenv("IPAUSTRALIA_CLIENT_SECRET", "secret")
    transport, hits = _token_counting("/access_token")
    for _ in range(3):
        async with IpAustraliaPatentsClient(transport=transport, use_cache=False) as client:
            await client.get_patent("2019204205")
    assert hits["token"] == 1

    monkeypatch.setenv("IPAUSTRALIA_CLIENT_ID", "another-id")
    async with IpAustraliaPatentsClient(transport=transport, use_cache=False) as client:
        await client.get_patent("2019204205")
    assert hits["token"] == 2


async def test_euipo_clients_share_one_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EUIPO_CLIENT_ID", "id")
    monkeypatch.setenv("EUIPO_CLIENT_SECRET", "secret")
    monkeypatch.delenv("EUIPO_ENV", raising=False)
    transport, hits = _token_counting(
        "/accessToken",
        body={"trademarks": [], "totalElements": 0, "totalPages": 0, "size": 25, "page": 0},
    )
    for _ in range(3):
        async with EuipoTrademarksClient(transport=transport, use_cache=False) as client:
            await client.search(query="x")
    assert hits["token"] == 1


async def test_swiss_ipi_clients_share_one_login() -> None:
    hits = {"token": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == IPI_TOKEN_URL:
            hits["token"] += 1
            return httpx2.Response(200, json={"access_token": "tok", "expires_in": 600})
        return httpx2.Response(200, content=(IPI_FIXTURES / "patent_search.xml").read_bytes())

    for _ in range(3):
        async with IpiSwissregClient(
            "user", "password", transport=httpx2.MockTransport(handler)
        ) as client:
            await client.search_patents("q")
    assert hits["token"] == 1


async def test_jpo_clients_share_one_token_and_one_rate_budget() -> None:
    hits = {"token": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/auth/token":
            hits["token"] += 1
            return httpx2.Response(200, json={"access_token": "tok", "expires_in": 3600})
        return httpx2.Response(
            200, content=json.dumps({"result": {"statusCode": "107", "data": {}}})
        )

    clients = []
    for _ in range(3):
        http = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
        async with JpoClient("user", "password", client=http) as client:
            await client.get_patent_progress("2020123456")
            clients.append(client)
    assert hits["token"] == 1
    assert len({id(c._rate_limiter) for c in clients}) == 1


def test_loop_lock_works_across_event_loops() -> None:
    lock = process_shared("lock", LoopLock)

    async def use() -> None:
        async with lock:
            await asyncio.sleep(0)

    asyncio.run(use())
    asyncio.run(use())  # a plain asyncio.Lock would be bound to the first loop here


def test_reset_forgets_shared_state() -> None:
    first = process_shared("k", object)
    assert process_shared("k", object) is first
    reset_process_shared()
    assert process_shared("k", object) is not first
