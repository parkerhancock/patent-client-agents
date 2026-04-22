from __future__ import annotations

import base64
from typing import Any

import pytest

from ip_tools.google_patents import api as gp_api
from ip_tools.google_patents.client import GooglePatentsSearchResponse, PatentData


@pytest.fixture
def sample_patent() -> PatentData:
    return PatentData(
        patent_number="US7654321B2",
        application_number="US 13/246,810",
        title="Example patent",
        abstract="An example abstract.",
        status="Active",
        current_assignee="Example Corp",
        inventors=["Alice", "Bob"],
        filing_date="2018-01-01",
        grant_date="2020-01-01",
        publication_date="2019-01-01",
        expiration_date="2038-01-01",
        priority_date="2017-06-06",
        claims=[{"number": "1", "text": "Sample claim", "type": "independent", "depends_on": None}],
        description="Example description",
        pdf_url="https://example.com/example.pdf",
        structured_limitations={"1": ["Sample limitation"]},
        raw_html="<html></html>",
    )


@pytest.fixture
def dummy_client(sample_patent: PatentData) -> Any:
    class DummyClient:
        async def get_patent_data(self, patent_number: str) -> PatentData:
            assert patent_number == "US7654321B2"
            return sample_patent

        async def download_patent_pdf(self, patent_number: str, *, use_cache: bool = True) -> bytes:
            assert patent_number == "us7654321b2"
            assert use_cache
            return b"%PDF-1.7 content"

        async def get_patent_figures(self, patent_number: str) -> list[dict[str, object]]:
            assert patent_number == "US7654321B2"
            return [
                {
                    "index": 0,
                    "page_number": 1,
                    "image_id": "US7654321-D00001.png",
                    "thumbnail_url": "https://example.com/thumb.png",
                    "full_image_url": "https://example.com/full.png",
                    "callouts": [
                        {
                            "figure_page": 1,
                            "reference_id": "10",
                            "label": "apparatus",
                            "bounds": {"left": 1, "top": 2, "right": 3, "bottom": 4},
                        }
                    ],
                }
            ]

        async def search_patents(self, **kwargs: object) -> GooglePatentsSearchResponse:
            return GooglePatentsSearchResponse(
                query_url="http://example.com?q=abc",
                total_results=1,
                total_pages=1,
                page=1,
                page_size=1,
                has_more=False,
                results=[],
            )

    return DummyClient()


@pytest.mark.asyncio
async def test_fetch(sample_patent: PatentData, dummy_client: Any) -> None:
    result = await gp_api.fetch("US7654321B2", client=dummy_client)
    assert isinstance(result, PatentData)
    assert result.title == "Example patent"
    assert result.claims[0]["number"] == "1"


@pytest.mark.asyncio
async def test_fetch_pdf(dummy_client: Any) -> None:
    pdf_bytes = await gp_api.fetch_pdf("us7654321b2", client=dummy_client)
    assert base64.b64encode(pdf_bytes).startswith(b"JVBER")


@pytest.mark.asyncio
async def test_fetch_figures(dummy_client: Any) -> None:
    figures = await gp_api.fetch_figures("US7654321B2", client=dummy_client)
    assert len(figures) == 1
    assert figures[0].page_number == 1
    assert figures[0].callouts[0].bounds.left == 1


@pytest.mark.asyncio
async def test_search_validation_requires_filter() -> None:
    with pytest.raises(ValueError):
        await gp_api.search(gp_api.GooglePatentsSearchInput(keywords=[], cpc_codes=[]))


@pytest.mark.asyncio
async def test_search_calls_client(dummy_client: Any) -> None:
    input_data = gp_api.GooglePatentsSearchInput(keywords=["widget"])
    response = await gp_api.search(input_data, client=dummy_client)
    assert isinstance(response, GooglePatentsSearchResponse)
    assert response.total_results == 1
