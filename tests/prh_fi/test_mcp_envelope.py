"""MCP envelope shape tests for the PRH (Finland) tools."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

from mcp_data_core.envelope import ListEnvelope
from patent_client_agents.mcp.tools.prh_fi import (
    download_prh_design_image,
    download_prh_trademark_image,
    get_prh_patent,
    search_prh_designs,
    search_prh_patents,
    search_prh_trademarks,
    search_prh_well_known_trademarks,
)
from patent_client_agents.prh_fi import PrhClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _factory_for(fixture: str):  # type: ignore[no-untyped-def]
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_fixture(fixture))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrhClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrhClient(client=client) as c:
            yield c

    return _factory


def _patch_client(monkeypatch: pytest.MonkeyPatch, factory) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prh_fi.PrhClient",
        lambda: factory(),
    )


# ----------------------------------------------------------------------
# search_prh_patents
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prh_patents_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, _factory_for("patent-search.json"))

    result = await search_prh_patents(applicant="Audience")
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "Audience" in result.summary
    assert result.provenance.source_url.startswith("https://patenttitietopalvelu.prh.fi")
    # Lean view drops the per-row ordinal.
    assert "ordinal" not in result.items[0]


@pytest.mark.asyncio
async def test_search_prh_patents_full_keeps_ordinal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _factory_for("patent-search.json"))
    result = await search_prh_patents(applicant="Audience", full=True)
    assert result.items[0]["ordinal"] == 1


# ----------------------------------------------------------------------
# get_prh_patent
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_prh_patent_envelope_lean_drops_heavy_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _factory_for("patent-get.json"))

    result = await get_prh_patent("20100001")
    assert isinstance(result, ListEnvelope)
    record = result.items[0]
    assert record["applicationNumber"] == "20100001"
    # Lean drops the heavy fields.
    for k in ("documents", "paymentDetails", "events"):
        assert k not in record
    # Keeps the lighter slots.
    assert record["examiner"]["fullName"] == "Pasi Helminen"
    assert record["patentTitle"]


@pytest.mark.asyncio
async def test_get_prh_patent_envelope_full_keeps_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _factory_for("patent-get.json"))
    result = await get_prh_patent("20100001", full=True)
    record = result.items[0]
    assert record["documents"] is not None


@pytest.mark.asyncio
async def test_get_prh_patent_accepts_list(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json=_fixture("patent-get.json"))

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrhClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrhClient(client=client) as c:
            yield c

    monkeypatch.setattr(
        "patent_client_agents.mcp.tools.prh_fi.PrhClient",
        lambda: _factory(),
    )

    result = await get_prh_patent(["20100001", "20100002"])
    assert len(result.items) == 2
    assert len(captured) == 2


@pytest.mark.asyncio
async def test_get_prh_patent_rejects_empty_input() -> None:
    from mcp_data_core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await get_prh_patent([])


# ----------------------------------------------------------------------
# search_prh_trademarks
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prh_trademarks_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _factory_for("tm-search.json"))
    result = await search_prh_trademarks(trademark_word="AUDI")
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "AUDI" in result.summary
    assert result.provenance.source_url.startswith("https://tavaramerkkitietopalvelu.prh.fi")
    # Lean view drops the thumbnail URLs.
    row = result.items[0]
    assert "thumbnailUrl" not in row
    assert "largeThumbnailUrl" not in row
    # Keeps the canonical image URL.
    assert "imageUrl" in row


# ----------------------------------------------------------------------
# search_prh_well_known_trademarks
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prh_well_known_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _factory_for("tmr-search.json"))
    result = await search_prh_well_known_trademarks()
    assert isinstance(result, ListEnvelope)
    assert "well-known trademarks (TMR)" in result.summary
    # TMR endpoint reaches the /tmr path.
    assert result.provenance.source_url.endswith("/tmr")
    assert any(row.get("targetGroup") for row in result.items)


# ----------------------------------------------------------------------
# search_prh_designs
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_prh_designs_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _factory_for("design-search.json"))
    result = await search_prh_designs(applicant_name="Marimekko")
    assert isinstance(result, ListEnvelope)
    assert result.items
    assert "Marimekko" in result.summary
    assert result.provenance.source_url.startswith("https://mallioikeustietopalvelu.prh.fi")


# ----------------------------------------------------------------------
# download_prh_trademark_image
# ----------------------------------------------------------------------


def _bytes_factory(content: bytes, content_type: str):  # type: ignore[no-untyped-def]
    def handler(_req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers={"content-type": content_type})

    @asynccontextmanager
    async def _factory() -> AsyncIterator[PrhClient]:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        async with PrhClient(client=client) as c:
            yield c

    return _factory


@pytest.mark.asyncio
async def test_download_prh_trademark_image_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _bytes_factory(b"GIF89a fake", "image/gif"))

    result = await download_prh_trademark_image("T196503880", "49497")
    assert result["content_type"] == "image/gif"
    assert result["size_bytes"] == len(b"GIF89a fake")
    assert result["filename"].endswith(".gif")
    assert result["resource_uri"].startswith("pca://prh_fi/trademark/image/")
    # In stdio mode the bytes are written to a tempfile.
    assert "file_path" in result or "download_url" in result
    assert result["application_number"] == "T196503880"
    assert result["registration_number"] == "49497"


@pytest.mark.asyncio
async def test_download_prh_trademark_image_handles_no_regno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(monkeypatch, _bytes_factory(b"GIF", "image/gif"))

    result = await download_prh_trademark_image("2007007")  # well-known TMR row
    assert result["registration_number"] is None
    assert "prh-tm-2007007-image.gif" == result["filename"]


# ----------------------------------------------------------------------
# download_prh_design_image
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_prh_design_image_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_client(
        monkeypatch,
        _bytes_factory(b"\xff\xd8\xff fake jpeg", "image/jpeg"),
    )

    result = await download_prh_design_image("M19710014.1.1", variant="thumbnail/medium")
    assert result["content_type"] == "image/jpeg"
    assert result["filename"].endswith(".jpg")
    assert result["filename"].startswith("prh-design-M19710014.1.1-thumbnail_medium")
    assert result["image_id"] == "M19710014.1.1"
    assert result["variant"] == "thumbnail/medium"
    # Path safe for caching: slashes in variant become underscores in the URI.
    assert result["resource_uri"] == "pca://prh_fi/design/thumbnail_medium/M19710014.1.1"
