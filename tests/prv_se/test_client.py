"""Client-level tests for the PRV (Sweden) connector.

Exercises the multi-host URL routing (``_build_url`` passthrough), the
shared simple-search body builder, and per-method dispatch using
``httpx.MockTransport`` so the suite is offline.

Live smoke calls (one per endpoint) record VCR cassettes that pin the
upstream response shape — see the test_live_* functions below.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from patent_client_agents.prv_se import PrvClient
from patent_client_agents.prv_se.client import (
    API_HOST,
    DV_HOST,
    MAX_PAGE_SIZE,
    PATENTS_HOST,
    _build_advanced_search_body,
    _build_simple_search_body,
)


def _mock(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _fixture(name: str) -> dict:
    path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text())


# ----------------------------------------------------------------------
# Simple-search body builder
# ----------------------------------------------------------------------


def test_body_includes_required_fields() -> None:
    body = _build_simple_search_body(
        text="Volvo",
        page=2,
        page_size=15,
        sort_column="filingDate",
        sort_order="DESC",
        extra=None,
    )
    assert body == {
        "page": 2,
        "pageSize": 15,
        "sortColumn": "filingDate",
        "sortOrder": "DESC",
        "simpleSearchText": "Volvo",
    }


def test_body_clamps_page_size() -> None:
    body = _build_simple_search_body(
        text=None,
        page=0,
        page_size=10_000,
        sort_column=None,
        sort_order=None,
        extra=None,
    )
    assert body["pageSize"] == MAX_PAGE_SIZE


def test_body_drops_falsy_text() -> None:
    body = _build_simple_search_body(
        text=None,
        page=0,
        page_size=5,
        sort_column=None,
        sort_order=None,
        extra=None,
    )
    assert "simpleSearchText" not in body


def test_body_merges_extra() -> None:
    body = _build_simple_search_body(
        text=None,
        page=0,
        page_size=5,
        sort_column=None,
        sort_order=None,
        extra={"applicantName": "Volvo Trucks", "ignoreMe": None},
    )
    assert body["applicantName"] == "Volvo Trucks"
    assert "ignoreMe" not in body


# ----------------------------------------------------------------------
# Multi-host URL routing
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_patents_routes_to_patents_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patents-search.json"))

    async with PrvClient(client=_mock(handler)) as client:
        await client.search_patents(text="Volvo", page_size=5)

    assert len(captured) == 1
    assert str(captured[0].url).startswith(PATENTS_HOST)
    assert captured[0].url.path == "/searchpatent/patentsimplesearch/"
    body = json.loads(captured[0].content)
    assert body["simpleSearchText"] == "Volvo"


@pytest.mark.asyncio
async def test_search_trademarks_routes_to_dv_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("tm-search.json"))

    async with PrvClient(client=_mock(handler)) as client:
        await client.search_trademarks(text="IKEA")

    assert str(captured[0].url).startswith(DV_HOST)
    assert captured[0].url.path == "/searchtrademark/tmsimplesearch/"


@pytest.mark.asyncio
async def test_search_designs_routes_to_dv_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("design-search.json"))

    async with PrvClient(client=_mock(handler)) as client:
        await client.search_designs(text="stol")

    assert str(captured[0].url).startswith(DV_HOST)
    assert captured[0].url.path == "/searchdesign/dssimplesearch/"


@pytest.mark.asyncio
async def test_get_patent_routes_to_api_host_with_query_param() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patent-get.json"))

    async with PrvClient(client=_mock(handler)) as client:
        await client.get_patent("SE2615555-6")

    req = captured[0]
    assert str(req.url).startswith(API_HOST)
    assert req.url.path == "/patents/applications/SE2615555-6"
    assert req.url.params["applicationType"] == "NAT"


@pytest.mark.asyncio
async def test_get_patent_accepts_application_type_override() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patent-get.json"))

    async with PrvClient(client=_mock(handler)) as client:
        await client.get_patent("SE2615555-6", application_type="EP")

    assert captured[0].url.params["applicationType"] == "EP"


@pytest.mark.asyncio
async def test_get_patent_rejects_empty_application_number() -> None:
    async with PrvClient(client=_mock(lambda _: httpx.Response(200, json={}))) as client:
        with pytest.raises(ValueError):
            await client.get_patent("")


# ----------------------------------------------------------------------
# Courtesy User-Agent identifies project + contact
# ----------------------------------------------------------------------


def test_default_user_agent_identifies_project() -> None:
    from patent_client_agents.prv_se.client import DEFAULT_USER_AGENT

    assert "patent-client-agents" in DEFAULT_USER_AGENT
    assert "data@prv.se" in DEFAULT_USER_AGENT


# ----------------------------------------------------------------------
# Live smoke (cassette-replayed)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_search_patents_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrvClient() as client:
        result = await client.search_patents(text="Volvo", page_size=2)
    assert result.total_hits > 0
    assert len(result.search_patent_dtos) <= 2


@pytest.mark.asyncio
async def test_live_get_patent_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrvClient() as client:
        result = await client.get_patent("SE2615555-6")
    assert result.application_number_formatted == "SE2615555-6"


@pytest.mark.asyncio
async def test_live_search_trademarks_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrvClient() as client:
        result = await client.search_trademarks(text="IKEA", page_size=2)
    assert result.total_hits > 0
    assert len(result.trademarks) <= 2


@pytest.mark.asyncio
async def test_live_search_designs_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrvClient() as client:
        result = await client.search_designs(text="stol", page_size=2)
    assert result.total_hits > 0
    assert len(result.designs) <= 2


# ----------------------------------------------------------------------
# Advanced-search body builder (SPC)
# ----------------------------------------------------------------------


def test_advanced_body_wraps_filters() -> None:
    body = _build_advanced_search_body(
        page=0,
        page_size=10,
        sort_column="",
        sort_order="DESC",
        filters={"applicants": "AstraZeneca", "substanceProduct": ""},
    )
    assert body["applicants"] == {"value": "AstraZeneca", "searchType": "CONTAINS"}
    assert "substanceProduct" not in body  # empty values dropped


def test_advanced_body_respects_explicit_match_type() -> None:
    body = _build_advanced_search_body(
        page=0,
        page_size=10,
        sort_column="",
        sort_order="DESC",
        filters={"applicants": ("AstraZeneca", "STARTS_WITH")},
    )
    assert body["applicants"]["searchType"] == "STARTS_WITH"


@pytest.mark.asyncio
async def test_search_spcs_routes_to_patents_host_with_wrapper_body() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("spc-search.json"))

    async with PrvClient(client=_mock(handler)) as client:
        await client.search_spcs(applicants="AstraZeneca")

    req = captured[0]
    assert str(req.url).startswith(PATENTS_HOST)
    assert req.url.path == "/searchpatentspc/patentsearchspc/"
    body = json.loads(req.content)
    # Filter wrapped as {value, searchType}.
    assert body["applicants"] == {"value": "AstraZeneca", "searchType": "CONTAINS"}


@pytest.mark.asyncio
async def test_search_spcs_rejects_empty_filters() -> None:
    async with PrvClient(client=_mock(lambda _: httpx.Response(200, json={}))) as client:
        with pytest.raises(ValueError, match="search_spcs requires"):
            await client.search_spcs()


@pytest.mark.asyncio
async def test_live_search_spcs_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrvClient() as client:
        result = await client.search_spcs(applicants="AstraZeneca", page_size=2)
    assert result.total_hits > 0
    assert len(result.search_spc_dtos) <= 2
