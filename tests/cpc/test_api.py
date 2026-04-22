"""Tests for CPC API module."""

from __future__ import annotations

from typing import Any, cast

import pytest

from ip_tools.cpc import api as cpc_api
from ip_tools.epo_ops.models import (
    ClassificationMappingResponse,
    CpciBiblioResponse,
    CpcMediaResponse,
    CpcRetrievalResponse,
    CpcSearchResponse,
)


class TestCpcExports:
    """Tests for CPC module exports."""

    def test_exports_client(self) -> None:
        assert hasattr(cpc_api, "EpoOpsClient")

    def test_exports_response_models(self) -> None:
        assert hasattr(cpc_api, "CpcRetrievalResponse")
        assert hasattr(cpc_api, "CpcSearchResponse")
        assert hasattr(cpc_api, "ClassificationMappingResponse")
        assert hasattr(cpc_api, "CpcMediaResponse")
        assert hasattr(cpc_api, "CpciBiblioResponse")

    def test_exports_functions(self) -> None:
        assert hasattr(cpc_api, "get_client")
        assert hasattr(cpc_api, "retrieve_cpc")
        assert hasattr(cpc_api, "search_cpc")
        assert hasattr(cpc_api, "map_classification")
        assert hasattr(cpc_api, "fetch_media")
        assert hasattr(cpc_api, "fetch_biblio_cpci")

    def test_exports_resource_uris(self) -> None:
        assert hasattr(cpc_api, "CQL_GUIDE_RESOURCE_URI")
        assert hasattr(cpc_api, "CPC_PARAMETERS_RESOURCE_URI")

    def test_exports_guide_content(self) -> None:
        assert hasattr(cpc_api, "CQL_GUIDE")
        assert hasattr(cpc_api, "CPC_PARAMETERS_GUIDE")


class TestCpcGuides:
    """Tests for CPC guide content."""

    def test_cql_guide_is_string(self) -> None:
        assert isinstance(cpc_api.CQL_GUIDE, str)

    def test_cql_guide_not_empty(self) -> None:
        assert len(cpc_api.CQL_GUIDE) > 100

    def test_cql_guide_has_title(self) -> None:
        assert "CQL" in cpc_api.CQL_GUIDE

    def test_cpc_parameters_guide_is_string(self) -> None:
        assert isinstance(cpc_api.CPC_PARAMETERS_GUIDE, str)

    def test_cpc_parameters_guide_not_empty(self) -> None:
        assert len(cpc_api.CPC_PARAMETERS_GUIDE) > 100

    def test_cpc_parameters_guide_has_title(self) -> None:
        assert "CPC" in cpc_api.CPC_PARAMETERS_GUIDE


class TestCpcResourceUris:
    """Tests for CPC resource URIs."""

    def test_cql_guide_uri_format(self) -> None:
        assert cpc_api.CQL_GUIDE_RESOURCE_URI.startswith("resource://")
        assert "cql" in cpc_api.CQL_GUIDE_RESOURCE_URI.lower()

    def test_cpc_parameters_uri_format(self) -> None:
        assert cpc_api.CPC_PARAMETERS_RESOURCE_URI.startswith("resource://")
        assert "cpc" in cpc_api.CPC_PARAMETERS_RESOURCE_URI.lower()


class TestGetClient:
    """Tests for get_client function."""

    def test_requires_both_credentials(self) -> None:
        with pytest.raises(ValueError, match="Both api_key and api_secret are required"):
            cpc_api.get_client(api_key="test_key")

    def test_requires_both_credentials_secret_only(self) -> None:
        with pytest.raises(ValueError, match="Both api_key and api_secret are required"):
            cpc_api.get_client(api_secret="test_secret")

    def test_creates_client_with_both(self) -> None:
        client = cpc_api.get_client(api_key="test_key", api_secret="test_secret")
        assert client is not None
        assert isinstance(client, cpc_api.EpoOpsClient)


class TestCpcApiMethods:
    """Tests for CPC API methods using DummyClient."""

    @pytest.mark.asyncio
    async def test_retrieve_cpc(self) -> None:
        class DummyClient:
            async def retrieve_cpc(self, **kwargs: object) -> CpcRetrievalResponse:
                assert kwargs["symbol"] == "A01B1/00"
                return CpcRetrievalResponse.model_validate({"scheme": {"items": []}})

        result = await cpc_api.retrieve_cpc("A01B1/00", client=cast(Any, DummyClient()))
        assert isinstance(result, CpcRetrievalResponse)

    @pytest.mark.asyncio
    async def test_search_cpc(self) -> None:
        class DummyClient:
            async def search_cpc(self, **kwargs: object) -> CpcSearchResponse:
                assert kwargs["range_begin"] == 1
                return CpcSearchResponse(query="battery", results=[])

        result = await cpc_api.search_cpc("battery", client=cast(Any, DummyClient()))
        assert isinstance(result, CpcSearchResponse)

    @pytest.mark.asyncio
    async def test_map_classification(self) -> None:
        class DummyClient:
            async def map_classification(self, **kwargs: object) -> ClassificationMappingResponse:
                assert kwargs["input_schema"] == "cpc"
                return ClassificationMappingResponse(mappings=[])

        result = await cpc_api.map_classification(
            input_schema="cpc",
            symbol="A01B1/00",
            output_schema="ipc",
            client=cast(Any, DummyClient()),
        )
        assert isinstance(result, ClassificationMappingResponse)

    @pytest.mark.asyncio
    async def test_fetch_media(self) -> None:
        class DummyClient:
            async def fetch_cpc_media(self, **kwargs: object) -> CpcMediaResponse:
                assert kwargs["media_id"] == "media123"
                return CpcMediaResponse(
                    media_id="media123", mime_type="image/gif", data_base64="AAA"
                )

        result = await cpc_api.fetch_media("media123", client=cast(Any, DummyClient()))
        assert isinstance(result, CpcMediaResponse)

    @pytest.mark.asyncio
    async def test_fetch_biblio_cpci(self) -> None:
        class DummyClient:
            async def fetch_cpci_biblio(self, **kwargs: object) -> CpciBiblioResponse:
                assert kwargs["number"] == "EP1000000"
                return CpciBiblioResponse(records=[])

        result = await cpc_api.fetch_biblio_cpci("EP1000000", client=cast(Any, DummyClient()))
        assert isinstance(result, CpciBiblioResponse)
