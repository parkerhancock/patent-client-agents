"""Module-level PPUBS helpers, driven against an in-process PPUBS."""

from __future__ import annotations

import base64
import json

import pytest

from patent_client_agents.uspto_publications import api as pub_api
from patent_client_agents.uspto_publications.client import PublicSearchClient
from tests.uspto_publications.fake_ppubs import (
    BASE,
    COUNTS,
    HIGHLIGHT,
    PDF_BYTES,
    PRINT_REQUEST,
    FakePpubs,
)


@pytest.mark.asyncio
async def test_download_pdf_with_publication_number() -> None:
    ppubs = FakePpubs()
    client = PublicSearchClient(transport=ppubs.transport())

    with pytest.warns(DeprecationWarning, match="client= is deprecated"):
        result = await pub_api.download_pdf(publication_number="US 2023/0123456 A1", client=client)
    await client.close()

    assert result.guid == "US-20230123456-A1"
    assert result.publication_number == "20230123456"
    assert result.patent_title == "Neural widget"
    assert base64.b64decode(result.pdf_base64) == PDF_BYTES
    # Resolved by an exact publication-number query, then fetched by GUID.
    assert json.loads(ppubs.hits(COUNTS)[0].content)["q"] == "20230123456.pn."
    (highlight,) = ppubs.hits(f"{HIGHLIGHT}/US-20230123456-A1")
    assert highlight.url.params["source"] == "US-PGPUB"
    print_job = json.loads(ppubs.hits(PRINT_REQUEST)[0].content)
    assert print_job["pageKeys"] == [
        "pgpub/2023/0123/456/00000001.tif",
        "pgpub/2023/0123/456/00000002.tif",
    ]
    assert str(ppubs.requests[-1].url) == f"{BASE}/api/print/save/doc.pdf"


@pytest.mark.asyncio
async def test_download_pdf_requires_identifiers() -> None:
    ppubs = FakePpubs()
    client = PublicSearchClient(transport=ppubs.transport())

    with pytest.warns(DeprecationWarning), pytest.raises(ValueError, match="publication_number"):
        await pub_api.download_pdf(guid="US-20230123456-A1", client=client)
    await client.close()

    assert ppubs.requests == []


@pytest.mark.asyncio
async def test_search_returns_parsed_page() -> None:
    ppubs = FakePpubs()
    client = PublicSearchClient(transport=ppubs.transport())

    with pytest.warns(DeprecationWarning):
        page = await pub_api.search("widget", client=client)
    await client.close()

    assert [d.publication_number for d in page.docs] == ["20230123456"]
    assert json.loads(ppubs.hits(COUNTS)[0].content)["q"] == "widget"
