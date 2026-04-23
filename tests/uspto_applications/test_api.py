from __future__ import annotations

from typing import Any, cast

import pytest

from patent_client_agents.uspto_applications import api as apps_api
from patent_client_agents.uspto_odp.models import (
    ApplicationResponse,
    DocumentsResponse,
    FamilyGraphResponse,
    SearchResponse,
)


@pytest.mark.asyncio
async def test_search_applications() -> None:
    class DummyClient:
        async def search_applications(self, **kwargs: object) -> SearchResponse:
            assert kwargs["query"] == "inventor:doe"
            return SearchResponse(count=1, patentBag=[{"applicationNumberText": "123"}])

    result = await apps_api.search_applications(q="inventor:doe", client=cast(Any, DummyClient()))
    assert isinstance(result, SearchResponse)
    assert result.count == 1
    assert result.patentBag[0]["applicationNumberText"] == "123"


@pytest.mark.asyncio
async def test_get_application() -> None:
    class DummyClient:
        async def get_application(self, application_number: str) -> ApplicationResponse:
            assert application_number == "16890123"
            return ApplicationResponse(count=1, patentBag=[{"applicationNumberText": "16890123"}])

    result = await apps_api.get_application("16890123", client=cast(Any, DummyClient()))
    assert isinstance(result, ApplicationResponse)
    assert result.patentBag[0]["applicationNumberText"] == "16890123"


@pytest.mark.asyncio
async def test_list_documents() -> None:
    class DummyClient:
        async def get_documents(
            self, application_number: str, include_associated: bool = True
        ) -> DocumentsResponse:
            assert include_associated is False
            assert application_number == "16890123"
            return DocumentsResponse(documents=[], associatedDocuments=[{"foo": "bar"}])

    result = await apps_api.list_documents(
        "16890123",
        include_associated=False,
        client=cast(Any, DummyClient()),
    )
    assert isinstance(result, DocumentsResponse)
    assert result.associatedDocuments is not None
    assert result.associatedDocuments[0]["foo"] == "bar"


@pytest.mark.asyncio
async def test_get_family() -> None:
    class DummyClient:
        async def get_family(self, identifier: str) -> FamilyGraphResponse:
            assert identifier == "16890123"
            return FamilyGraphResponse(rootApplication="16890123", nodes=[], edges=[])

    result = await apps_api.get_family("16890123", client=cast(Any, DummyClient()))
    assert isinstance(result, FamilyGraphResponse)
    assert result.rootApplication == "16890123"
