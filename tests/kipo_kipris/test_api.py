"""Smoke tests for the KIPO KIPRIS module-level helpers.

Each helper opens a context-managed :class:`KiprisClient` and delegates
to the matching client method. We mock ``KiprisClient`` so these tests
are pure delegation contract checks — separate from the client-level
request/response tests in :mod:`test_client`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

import patent_client_agents.kipo_kipris.api as api


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch ``KiprisClient`` with an async-context AsyncMock and return the inner mock."""
    inner = AsyncMock()

    class _MockCtx:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    def _factory(*args: Any, **kwargs: Any) -> _MockCtx:
        return _MockCtx()

    monkeypatch.setattr(api, "KiprisClient", _factory)
    return inner


# ──────────────────────────────────────────────────────────────────────
# Patents + Utility Models
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_kipo_patents_delegates(mock_client: AsyncMock) -> None:
    mock_client.search_patents_word = AsyncMock(return_value=([{"applicationNumber": "X"}], {}))
    items, _ = await api.search_kipo_patents("battery")
    assert items[0]["applicationNumber"] == "X"
    mock_client.search_patents_word.assert_awaited_once()
    call = mock_client.search_patents_word.call_args
    assert call.kwargs["word"] == "battery"
    # Defaults forwarded.
    assert call.kwargs["patent"] is True
    assert call.kwargs["utility"] is True


@pytest.mark.asyncio
async def test_search_kipo_patents_advanced_forwards_filters(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_patents_advanced = AsyncMock(return_value=([], {}))
    await api.search_kipo_patents_advanced(
        invention_title="배터리",
        applicant="삼성",
        ipc="H01M",
    )
    call = mock_client.search_patents_advanced.call_args
    assert call.kwargs["invention_title"] == "배터리"
    assert call.kwargs["applicant"] == "삼성"
    assert call.kwargs["ipc"] == "H01M"


@pytest.mark.asyncio
async def test_get_kipo_patent_delegates(mock_client: AsyncMock) -> None:
    mock_client.get_patent = AsyncMock(return_value=([{"applicationNumber": "X"}], {}))
    items, _ = await api.get_kipo_patent("1020230012345")
    assert items[0]["applicationNumber"] == "X"
    mock_client.get_patent.assert_awaited_with("1020230012345")


# ──────────────────────────────────────────────────────────────────────
# Trademarks
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_kipo_trademarks_delegates(mock_client: AsyncMock) -> None:
    mock_client.search_trademarks_word = AsyncMock(return_value=([{"title": "GALAXY"}], {}))
    items, _ = await api.search_kipo_trademarks("GALAXY")
    assert items[0]["title"] == "GALAXY"
    mock_client.search_trademarks_word.assert_awaited_once()
    call = mock_client.search_trademarks_word.call_args
    assert call.kwargs["word"] == "GALAXY"


@pytest.mark.asyncio
async def test_search_kipo_trademarks_advanced_forwards_filters(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_trademarks_advanced = AsyncMock(return_value=([], {}))
    await api.search_kipo_trademarks_advanced(
        title="GALAXY",
        applicant="삼성",
        classification="09",
        vienna_code="26.04.01",
    )
    call = mock_client.search_trademarks_advanced.call_args
    assert call.kwargs["title"] == "GALAXY"
    assert call.kwargs["classification"] == "09"
    assert call.kwargs["vienna_code"] == "26.04.01"


@pytest.mark.asyncio
async def test_get_kipo_trademark_delegates(mock_client: AsyncMock) -> None:
    mock_client.get_trademark = AsyncMock(return_value=([{"title": "GALAXY"}], {}))
    items, _ = await api.get_kipo_trademark("4020230123456")
    assert items[0]["title"] == "GALAXY"
    mock_client.get_trademark.assert_awaited_with("4020230123456")


# ──────────────────────────────────────────────────────────────────────
# Designs
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_kipo_designs_delegates(mock_client: AsyncMock) -> None:
    mock_client.search_designs_word = AsyncMock(return_value=([{"articleName": "전화기"}], {}))
    items, _ = await api.search_kipo_designs("전화기")
    assert items[0]["articleName"] == "전화기"
    call = mock_client.search_designs_word.call_args
    assert call.kwargs["word"] == "전화기"


@pytest.mark.asyncio
async def test_search_kipo_designs_advanced_forwards_filters(
    mock_client: AsyncMock,
) -> None:
    mock_client.search_designs_advanced = AsyncMock(return_value=([], {}))
    await api.search_kipo_designs_advanced(
        article_name="전화기",
        applicant="삼성",
        loc_code="14-03",
    )
    call = mock_client.search_designs_advanced.call_args
    assert call.kwargs["article_name"] == "전화기"
    assert call.kwargs["loc_code"] == "14-03"


@pytest.mark.asyncio
async def test_get_kipo_design_delegates(mock_client: AsyncMock) -> None:
    mock_client.get_design = AsyncMock(return_value=([{"articleName": "전화기"}], {}))
    items, _ = await api.get_kipo_design("3020230012345")
    assert items[0]["articleName"] == "전화기"
    mock_client.get_design.assert_awaited_with("3020230012345")
