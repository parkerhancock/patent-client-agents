from __future__ import annotations

from typing import Any, cast

import pytest

from law_tools_core.exceptions import NotFoundError
from patent_client_agents.epo_ops import api as ops_api
from patent_client_agents.epo_ops.models import (
    BiblioRecord,
    BiblioResponse,
    DocumentId,
    FamilyResponse,
    FullTextResponse,
    LegalEvent,
    LegalEventsResponse,
    NumberConversionResponse,
    PdfDownloadResponse,
    SearchResponse,
)


@pytest.mark.asyncio
async def test_search_published() -> None:
    class DummyClient:
        async def search_published(self, **kwargs: object) -> SearchResponse:
            assert kwargs["query"] == "pn=EP1000000"
            return SearchResponse(total_results=1, results=[])

    result = await ops_api.search_published("pn=EP1000000", client=cast(Any, DummyClient()))
    assert isinstance(result, SearchResponse)
    assert result.total_results == 1


@pytest.mark.asyncio
async def test_fetch_biblio() -> None:
    class DummyClient:
        async def fetch_biblio(self, **kwargs: object) -> BiblioResponse:
            assert kwargs["number"] == "EP1000000"
            return BiblioResponse(documents=[BiblioRecord(docdb_number="EP1000000")])

    result = await ops_api.fetch_biblio("EP1000000", client=cast(Any, DummyClient()))
    assert isinstance(result, BiblioResponse)


@pytest.mark.asyncio
async def test_fetch_fulltext() -> None:
    class DummyClient:
        async def fetch_fulltext(self, **kwargs: object) -> FullTextResponse:
            assert kwargs["section"] == "claims"
            return FullTextResponse(section="claims", claims=[])

    result = await ops_api.fetch_fulltext(
        "EP1000000", section="claims", client=cast(Any, DummyClient())
    )
    assert isinstance(result, FullTextResponse)
    assert result.section == "claims"


@pytest.mark.asyncio
async def test_fetch_fulltext_translates_404_to_friendly_value_error() -> None:
    # EPO returns 404 for publications without indexed full text
    # (especially older or non-EP/non-WO documents). The library-level
    # NotFoundError carries an internal log-path hint via ApiError.__str__
    # which is unhelpful for that domain failure — surface a clean
    # ValueError that a tool / agent can show to the user verbatim.
    class DummyClient:
        async def fetch_fulltext(self, **kwargs: object) -> FullTextResponse:
            raise NotFoundError("HTTP 404", 404, "")

    with pytest.raises(ValueError, match="EPO has no claims full text"):
        await ops_api.fetch_fulltext(
            "EP1000000", section="claims", client=cast(Any, DummyClient())
        )


@pytest.mark.asyncio
async def test_fetch_family() -> None:
    class DummyClient:
        async def fetch_family(self, **kwargs: object) -> FamilyResponse:
            assert kwargs["number"] == "EP1000000"
            return FamilyResponse(publication_number="EP1000000", num_records=1, members=[])

    result = await ops_api.fetch_family("EP1000000", client=cast(Any, DummyClient()))
    assert isinstance(result, FamilyResponse)


@pytest.mark.asyncio
async def test_fetch_legal_events() -> None:
    class DummyClient:
        async def fetch_legal_events(self, **kwargs: object) -> LegalEventsResponse:
            assert kwargs["number"] == "EP1000000"
            return LegalEventsResponse(
                publication_reference=DocumentId(number="EP1000000"),
                events=[LegalEvent(event_code="XYZ")],
            )

    result = await ops_api.fetch_legal_events("EP1000000", client=cast(Any, DummyClient()))
    assert isinstance(result, LegalEventsResponse)


@pytest.mark.asyncio
async def test_convert_number() -> None:
    class DummyClient:
        async def convert_number(self, **kwargs: object) -> NumberConversionResponse:
            assert kwargs["input_format"] == "original"
            return NumberConversionResponse(
                input_document=DocumentId(number="EP1000000"),
                output_document=DocumentId(number="1000000"),
            )

    result = await ops_api.convert_number("EP1000000", client=cast(Any, DummyClient()))
    assert isinstance(result, NumberConversionResponse)


@pytest.mark.asyncio
async def test_download_pdf() -> None:
    class DummyClient:
        async def download_pdf(self, **kwargs: object) -> PdfDownloadResponse:
            assert kwargs["number"] == "EP1000000"
            return PdfDownloadResponse(
                publication_number="EP1000000", num_pages=1, pdf_base64="Zm9v"
            )

    result = await ops_api.download_pdf("EP1000000", client=cast(Any, DummyClient()))
    assert isinstance(result, PdfDownloadResponse)
    assert result.publication_number == "EP1000000"
