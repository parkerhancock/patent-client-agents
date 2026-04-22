from __future__ import annotations

from typing import Any, cast

import pytest

from ip_tools.mpep import api as mpep_api
from ip_tools.mpep.models import MpepSearchResponse, MpepSection, MpepVersion


@pytest.mark.asyncio
async def test_search() -> None:
    class DummyClient:
        async def search(self, **kwargs: Any) -> MpepSearchResponse:
            assert kwargs["query"] == "obviousness"
            assert kwargs["include_content"] is True
            assert kwargs["include_index"] is True
            assert kwargs["page"] == 2
            return MpepSearchResponse(
                hits=[],
                page=kwargs["page"],
                per_page=kwargs["per_page"],
                has_more=False,
            )

    params = mpep_api.SearchInput(
        query="obviousness",
        include_index=True,
        include_notes=False,
        include_form_paragraphs=False,
        per_page=25,
        page=2,
    )
    result = await mpep_api.search(params, client=cast(Any, DummyClient()))
    assert result.page == 2


@pytest.mark.asyncio
async def test_get_section() -> None:
    class DummyClient:
        async def get_section(self, **kwargs: Any) -> MpepSection:
            assert kwargs["section"] == "d0e123"
            assert kwargs["version"] == "current"
            assert kwargs["highlight_query"] == "obviousness"
            return MpepSection(
                href=kwargs["section"],
                html="<p>text</p>",
                text="text",
                version=kwargs["version"],
            )

    params = mpep_api.SectionInput(href="d0e123", highlight_query="obviousness")
    result = await mpep_api.get_section(params, client=cast(Any, DummyClient()))
    assert result.href == "d0e123"


@pytest.mark.asyncio
async def test_list_versions() -> None:
    class DummyClient:
        async def list_versions(self) -> list[MpepVersion]:
            return [MpepVersion(label="Current", value="current", current=True)]

    result = await mpep_api.list_versions(client=cast(Any, DummyClient()))
    assert result[0].current is True
