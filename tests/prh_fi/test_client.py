"""Client-level tests for the PRH (Finland) connector."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from patent_client_agents.prh_fi import PrhClient
from patent_client_agents.prh_fi.client import (
    DEFAULT_PATENT_STATUSES,
    DEFAULT_PATENT_TYPES,
    DEFAULT_PUBLICATION_TYPES,
    DEFAULT_USER_AGENT,
    DESIGN_HOST,
    DESIGN_PATH,
    PATENT_HOST,
    PATENT_PATH,
    TMR_PATH,
    TRADEMARK_HOST,
    TRADEMARK_PATH,
    build_design_search_body,
    build_patent_search_body,
    build_trademark_search_body,
)


def _mock(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _fixture(name: str) -> dict:
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text())


# ----------------------------------------------------------------------
# Body builders — defaults applied automatically
# ----------------------------------------------------------------------


def test_patent_body_defaults_inclusion_filters() -> None:
    body = build_patent_search_body(applicant="Nokia")
    assert body["applicant"] == "Nokia"
    assert body["dossierStatus"] == DEFAULT_PATENT_STATUSES
    assert body["patentTypes"] == DEFAULT_PATENT_TYPES
    assert body["publicationTypes"] == DEFAULT_PUBLICATION_TYPES
    # 30 keys total per the SPA form-state shape.
    assert len(body) == 30
    # Strings default to empty (not None) so PRH accepts the body.
    assert body["patentTitle"] == ""
    assert body["spcBasePatentNumber"] == ""


def test_patent_body_respects_explicit_empty_lists() -> None:
    body = build_patent_search_body(patent_types=[])
    assert body["patentTypes"] == []
    # Other defaults still apply when not overridden.
    assert body["dossierStatus"] == DEFAULT_PATENT_STATUSES


def test_trademark_body_has_21_string_fields() -> None:
    body = build_trademark_search_body(trademark_word="SISU")
    assert len(body) == 21
    assert body["trademarkWord"] == "SISU"
    assert all(isinstance(v, str) for v in body.values())


def test_design_body_has_19_string_fields() -> None:
    body = build_design_search_body(applicant_name="Fiskars")
    assert len(body) == 19
    assert body["applicantName"] == "Fiskars"
    assert all(isinstance(v, str) for v in body.values())


# ----------------------------------------------------------------------
# Multi-host URL routing
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_patents_routes_to_patent_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patent-search.json"))

    async with PrhClient(client=_mock(handler)) as client:
        await client.search_patents(applicant="Audience")

    assert len(captured) == 1
    assert str(captured[0].url).startswith(PATENT_HOST)
    assert captured[0].url.path == PATENT_PATH
    body = json.loads(captured[0].content)
    assert body["applicant"] == "Audience"
    assert body["patentTypes"] == DEFAULT_PATENT_TYPES


@pytest.mark.asyncio
async def test_get_patent_routes_to_patent_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patent-get.json"))

    async with PrhClient(client=_mock(handler)) as client:
        await client.get_patent("20100001")

    req = captured[0]
    assert str(req.url).startswith(PATENT_HOST)
    assert req.url.path == f"{PATENT_PATH}/20100001"


@pytest.mark.asyncio
async def test_get_patent_rejects_empty_application_number() -> None:
    async with PrhClient(client=_mock(lambda _: httpx.Response(200, json={}))) as client:
        with pytest.raises(ValueError):
            await client.get_patent("")


@pytest.mark.asyncio
async def test_search_trademarks_routes_to_trademark_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("tm-search.json"))

    async with PrhClient(client=_mock(handler)) as client:
        await client.search_trademarks(trademark_word="AUDI")

    assert str(captured[0].url).startswith(TRADEMARK_HOST)
    assert captured[0].url.path == TRADEMARK_PATH


@pytest.mark.asyncio
async def test_search_well_known_routes_to_tmr_path() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("tmr-search.json"))

    async with PrhClient(client=_mock(handler)) as client:
        await client.search_well_known_trademarks()

    assert str(captured[0].url).startswith(TRADEMARK_HOST)
    assert captured[0].url.path == TMR_PATH


@pytest.mark.asyncio
async def test_search_designs_routes_to_design_host() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("design-search.json"))

    async with PrhClient(client=_mock(handler)) as client:
        await client.search_designs(applicant_name="Marimekko")

    assert str(captured[0].url).startswith(DESIGN_HOST)
    assert captured[0].url.path == DESIGN_PATH


# ----------------------------------------------------------------------
# User-Agent identifies project + contact
# ----------------------------------------------------------------------


def test_default_user_agent_identifies_project() -> None:
    assert "patent-client-agents" in DEFAULT_USER_AGENT
    assert "avoindata@prh.fi" in DEFAULT_USER_AGENT


# ----------------------------------------------------------------------
# Live smoke (cassette-replayed)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_search_patents_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        result = await client.search_patents(applicant="Audience")
    assert result.total_results > 0


@pytest.mark.asyncio
async def test_live_get_patent_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        result = await client.get_patent("20100001")
    assert result.application_number == "20100001"


@pytest.mark.asyncio
async def test_live_search_trademarks_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        result = await client.search_trademarks(trademark_word="AUDI")
    assert result.total_results > 0


@pytest.mark.asyncio
async def test_live_search_well_known_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        result = await client.search_well_known_trademarks()
    # The TMR is small and curated; expect a non-trivial count.
    assert result.total_results >= 1


@pytest.mark.asyncio
async def test_live_search_designs_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        result = await client.search_designs(applicant_name="Marimekko")
    assert result.total_results >= 1


# ----------------------------------------------------------------------
# Image downloads — URL routing + validation
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_trademark_image_routes_with_regno() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"GIF89a fake", headers={"content-type": "image/gif"})

    async with PrhClient(client=_mock(handler)) as client:
        content, ct = await client.download_trademark_image("T196503880", "49497")

    assert content.startswith(b"GIF89a")
    assert ct == "image/gif"
    assert str(captured[0].url).startswith(TRADEMARK_HOST)
    assert captured[0].url.path == "/opendata/trademark/image/T196503880/49497"


@pytest.mark.asyncio
async def test_download_trademark_image_without_regno() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"GIF", headers={"content-type": "image/gif"})

    async with PrhClient(client=_mock(handler)) as client:
        await client.download_trademark_image("2007007", variant="thumbnail")

    # TMR rows reach the image surface with just the application number.
    assert captured[0].url.path == "/opendata/trademark/thumbnail/2007007"


@pytest.mark.asyncio
async def test_download_trademark_image_rejects_bad_variant() -> None:
    async with PrhClient(client=_mock(lambda _: httpx.Response(200, b""))) as client:
        with pytest.raises(ValueError, match="variant must be"):
            await client.download_trademark_image("X", variant="huge")


@pytest.mark.asyncio
async def test_download_design_image_routes() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200, content=b"\xff\xd8\xff fake jpeg", headers={"content-type": "image/jpeg"}
        )

    async with PrhClient(client=_mock(handler)) as client:
        content, ct = await client.download_design_image(
            "M19710014.1.1", variant="thumbnail/medium"
        )

    assert ct == "image/jpeg"
    assert str(captured[0].url).startswith(DESIGN_HOST)
    assert captured[0].url.path == "/opendata/design/thumbnail/medium/M19710014.1.1"


@pytest.mark.asyncio
async def test_download_design_image_rejects_empty_id() -> None:
    async with PrhClient(client=_mock(lambda _: httpx.Response(200, b""))) as client:
        with pytest.raises(ValueError, match="image_id must be"):
            await client.download_design_image("")


# ----------------------------------------------------------------------
# Live image-download smoke
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_download_trademark_image_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        content, ct = await client.download_trademark_image(
            "T196503880", "49497", variant="thumbnail"
        )
    assert ct.startswith("image/")
    assert len(content) > 100


@pytest.mark.asyncio
async def test_live_download_design_image_smoke(vcr_cassette: object) -> None:
    del vcr_cassette
    async with PrhClient() as client:
        content, ct = await client.download_design_image("M19710014.1.1", variant="thumbnail")
    assert ct.startswith("image/")
    assert len(content) > 100
