"""Integration tests for PublicSearchClient using VCR-recorded cassettes."""

import pytest

from ip_tools.uspto_publications import PublicSearchClient


class TestPublicSearchClientIntegration:
    @pytest.mark.vcr
    async def test_search_biblio(self):
        async with PublicSearchClient() as client:
            page = await client.search_biblio(query="machine learning", limit=5)
            assert page.num_found > 0
            assert len(page.docs) > 0
            doc = page.docs[0]
            assert doc.publication_number
            assert doc.patent_title

    @pytest.mark.vcr
    async def test_search_biblio_pagination(self):
        async with PublicSearchClient() as client:
            page = await client.search_biblio(query="machine learning", start=0, limit=3)
            assert page.num_found > 0
            assert len(page.docs) <= 3

    async def test_search_biblio_empty_query_raises(self):
        async with PublicSearchClient() as client:
            with pytest.raises(ValueError, match="query must be provided"):
                await client.search_biblio(query="")

    async def test_resolve_empty_publication_number_raises(self):
        async with PublicSearchClient() as client:
            with pytest.raises(ValueError, match="must include alphanumeric"):
                await client.resolve_document_by_publication_number("")

    @pytest.mark.vcr
    async def test_get_document_from_search(self):
        """Search, then fetch full document using guid/source from a result."""
        async with PublicSearchClient() as client:
            page = await client.search_biblio(query="machine learning", limit=1)
            assert len(page.docs) > 0
            biblio = page.docs[0]
            assert biblio.guid
            assert biblio.type
            doc = await client.get_document(biblio.guid, source=biblio.type)
            assert doc.guid == biblio.guid
            assert doc.patent_title

    @pytest.mark.vcr
    async def test_search_biblio_with_sources(self):
        async with PublicSearchClient() as client:
            page = await client.search_biblio(
                query="neural network",
                limit=3,
                sources=["USPAT"],
            )
            assert page.num_found > 0
            for doc in page.docs:
                assert doc.type == "USPAT"

    @pytest.mark.vcr
    async def test_search_biblio_result_fields(self):
        """Verify that search results contain expected metadata fields."""
        async with PublicSearchClient() as client:
            page = await client.search_biblio(query="autonomous vehicle", limit=1)
            assert len(page.docs) > 0
            doc = page.docs[0]
            assert doc.guid
            assert doc.type
            assert page.per_page > 0
