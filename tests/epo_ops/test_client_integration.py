"""VCR-recorded integration tests for EpoOpsClient."""

from __future__ import annotations

import os

import pytest

from ip_tools.epo_ops.client import EpoOpsClient, client_from_env

pytestmark = pytest.mark.skipif(not os.getenv("EPO_OPS_API_KEY"), reason="EPO_OPS_API_KEY not set")


@pytest.fixture
def client():
    """Create an EpoOpsClient from environment variables."""
    return client_from_env()


class TestEpoOpsClientIntegration:
    @pytest.mark.vcr
    async def test_search_published(self, client: EpoOpsClient):
        async with client:
            results = await client.search_published(query="ti=robot", range_begin=1, range_end=5)
            assert results.total_results is not None
            assert results.total_results > 0
            assert len(results.results) > 0

    @pytest.mark.vcr
    async def test_fetch_biblio(self, client: EpoOpsClient):
        async with client:
            biblio = await client.fetch_biblio(number="EP1000000A1")
            assert len(biblio.documents) > 0
            doc = biblio.documents[0]
            assert doc.title

    @pytest.mark.vcr
    async def test_fetch_claims(self, client: EpoOpsClient):
        async with client:
            fulltext = await client.fetch_fulltext(number="EP1000000A1", section="claims")
            assert fulltext.section == "claims"
            assert len(fulltext.claims) > 0

    @pytest.mark.vcr
    async def test_fetch_family(self, client: EpoOpsClient):
        async with client:
            family = await client.fetch_family(number="EP1000000A1")
            assert len(family.members) > 0

    @pytest.mark.vcr
    async def test_fetch_legal_events(self, client: EpoOpsClient):
        async with client:
            legal = await client.fetch_legal_events(number="EP1000000A1")
            assert len(legal.events) > 0

    @pytest.mark.vcr
    async def test_convert_number(self, client: EpoOpsClient):
        async with client:
            result = await client.convert_number(
                number="US10123456",
                input_format="docdb",
                output_format="epodoc",
            )
            assert result.output_document is not None

    @pytest.mark.vcr
    async def test_search_families(self, client: EpoOpsClient):
        async with client:
            results = await client.search_families(query="ti=solar", range_begin=1, range_end=5)
            assert len(results.families) > 0

    @pytest.mark.vcr
    async def test_fetch_description(self, client: EpoOpsClient):
        async with client:
            fulltext = await client.fetch_fulltext(number="EP1000000A1", section="description")
            assert fulltext.section == "description"
            assert fulltext.description is not None

    @pytest.mark.vcr
    async def test_retrieve_cpc(self, client: EpoOpsClient):
        async with client:
            result = await client.retrieve_cpc(symbol="H04L9/32")
            assert result.scheme is not None
            assert len(result.scheme.items) > 0

    @pytest.mark.vcr
    async def test_search_cpc(self, client: EpoOpsClient):
        async with client:
            result = await client.search_cpc(query="robot")
            assert result.query == "robot"
            assert len(result.results) > 0

    @pytest.mark.vcr
    async def test_map_classification(self, client: EpoOpsClient):
        async with client:
            result = await client.map_classification(
                input_schema="ipc", symbol="H04L9/32", output_schema="cpc"
            )
            assert len(result.mappings) > 0

    @pytest.mark.vcr
    async def test_fetch_cpci_biblio(self, client: EpoOpsClient):
        async with client:
            result = await client.fetch_cpci_biblio(number="EP1000000A1")
            assert len(result.records) > 0

    @pytest.mark.vcr
    async def test_search_register(self, client: EpoOpsClient):
        async with client:
            result = await client.search_register(query='pa="Siemens"', range_begin=1, range_end=5)
            assert result.total_results is not None
            assert len(result.results) > 0

    # NOTE: register biblio/events/procedural-steps/upp tests omitted —
    # the EPO register API requires specific epodoc-format application numbers
    # (e.g., "EP05703281") that differ from publication numbers. The register
    # search endpoint (test_search_register) validates the register code path.
