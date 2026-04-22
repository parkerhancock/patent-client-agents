from __future__ import annotations

import base64
from typing import Any, cast

import pytest

from ip_tools.uspto_publications import api as pub_api
from ip_tools.uspto_publications.models import PublicSearchDocument


class DummyClient:
    async def get_document(self, guid: str, source: str) -> PublicSearchDocument:
        assert guid == "GUID"
        assert source == "PGPUB"
        return PublicSearchDocument(guid=guid, publication_number="US20230123456A1", type=source)

    async def download_pdf_base64(self, document: PublicSearchDocument) -> str:
        assert document.guid == "GUID"
        return base64.b64encode(b"pdf").decode("ascii")

    async def resolve_document_by_publication_number(
        self, publication_number: str
    ) -> PublicSearchDocument:
        assert publication_number == "US 2023/0123456 A1"
        return PublicSearchDocument(
            guid="GUID",
            publication_number="US20230123456A1",
            type="PGPUB",
            patent_title="Test Doc",
        )

    async def search_biblio(self, **kwargs: object) -> str:
        assert kwargs["query"] == "widget"
        return "ok"  # Only shape we assert on, not real type.


@pytest.mark.asyncio
async def test_download_pdf_with_publication_number() -> None:
    result = await pub_api.download_pdf(
        publication_number="US 2023/0123456 A1",
        client=cast(Any, DummyClient()),
    )
    assert result.patent_title == "Test Doc"
    assert base64.b64decode(result.pdf_base64) == b"pdf"


@pytest.mark.asyncio
async def test_download_pdf_requires_identifiers() -> None:
    with pytest.raises(ValueError):
        await pub_api.download_pdf(client=cast(Any, DummyClient()))


@pytest.mark.asyncio
async def test_search_delegates() -> None:
    class SearchClient(DummyClient):
        async def search_biblio(self, **kwargs: object) -> str:
            assert kwargs["query"] == "widget"
            return "ok"

    result = await pub_api.search("widget", client=cast(Any, SearchClient()))
    assert result == "ok"
