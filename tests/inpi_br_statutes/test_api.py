"""Tests for the one-shot convenience helpers in the LPI api module."""

from __future__ import annotations

from pathlib import Path

import pytest

from patent_client_agents.inpi_br_statutes import (
    USAGE_RESOURCE_URI,
    InpiBrStatutesClient,
    SearchInput,
    SectionInput,
    get_client,
    get_section,
    get_usage_resource,
    list_versions,
    search,
)


@pytest.fixture(autouse=True)
def _set_corpus(lpi_corpus_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INPI_BR_STATUTES_CORPUS_PATH", str(lpi_corpus_path))


def test_usage_resource_uri_is_stable() -> None:
    assert USAGE_RESOURCE_URI == "resource://inpi_br_statutes/usage"


def test_usage_resource_returns_markdown() -> None:
    body = get_usage_resource()
    assert "LPI" in body
    assert "Search" in body


def test_get_client_returns_an_unentered_client() -> None:
    c = get_client()
    assert isinstance(c, InpiBrStatutesClient)
    # Not yet entered; closing should be a no-op (no db opened).
    import asyncio

    asyncio.run(c.close())


@pytest.mark.asyncio
async def test_search_helper_creates_client_internally() -> None:
    response = await search(SearchInput(query="concorrência desleal"))
    assert response.hits
    assert any(h.href == "art195" for h in response.hits)


@pytest.mark.asyncio
async def test_get_section_helper_from_string() -> None:
    section = await get_section("Art. 6")
    assert section.href == "art6"
    assert section.text_en is not None


@pytest.mark.asyncio
async def test_get_section_helper_from_input_model() -> None:
    section = await get_section(SectionInput(section="Art. 195"))
    assert section.href == "art195"


@pytest.mark.asyncio
async def test_list_versions_helper() -> None:
    versions = await list_versions()
    assert versions
    assert versions[0].current is True
    assert "1996" in versions[0].label


@pytest.mark.asyncio
async def test_search_with_pagination_params() -> None:
    response = await search(SearchInput(query="patente", per_page=2, page=1))
    assert response.per_page == 2
    assert response.page == 1


@pytest.mark.asyncio
async def test_search_with_sort_outline() -> None:
    response = await search(SearchInput(query="patente", sort="outline"))
    # Order by article_number (string sort, so "Art. 10" sorts before "Art. 6").
    assert response.hits


@pytest.mark.asyncio
async def test_search_empty_query_returns_no_hits() -> None:
    response = await search(SearchInput(query="   "))
    assert response.hits == []
    assert response.has_more is False
