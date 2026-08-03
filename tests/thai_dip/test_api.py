from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "method", "argument", "kwargs", "expected"),
    [
        (
            "search_thai_dip_patents",
            "search_patents",
            "q",
            {"right_type": "design", "field": "title", "limit": 3},
            ([], 0),
        ),
        (
            "get_thai_dip_patent",
            "get_patent",
            "P1",
            {"right_type": "petty_patent"},
            "patent",
        ),
        (
            "search_thai_dip_trademarks",
            "search_trademarks",
            "q",
            {"field": "name", "limit": 4},
            ([], 0),
        ),
        ("get_thai_dip_trademark", "get_trademark", "T1", {}, "trademark"),
        (
            "search_thai_dip_copyrights",
            "search_copyrights",
            "q",
            {"field": "owner", "limit": 5},
            ([], 0),
        ),
        ("get_thai_dip_copyright", "get_copyright", "C1", {}, "copyright"),
        (
            "search_thai_dip_songs",
            "search_songs",
            "q",
            {"field": "composer", "limit": 6},
            ([], 0),
        ),
        (
            "search_thai_dip_geographical_indications",
            "search_geographical_indications",
            "q",
            {"field": "name", "limit": 7},
            ([], 0),
        ),
        (
            "get_thai_dip_geographical_indication",
            "get_geographical_indication",
            "G1",
            {},
            "gi",
        ),
    ],
)
async def test_api_helpers_delegate(
    monkeypatch: pytest.MonkeyPatch,
    helper: str,
    method: str,
    argument: str,
    kwargs: dict[str, Any],
    expected: Any,
) -> None:
    from patent_client_agents.thai_dip import api

    inner = AsyncMock()
    getattr(inner, method).return_value = expected

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: object) -> None:
            return None

    monkeypatch.setattr(api, "ThaiDipClient", Context)
    result = await getattr(api, helper)(argument, **kwargs)
    assert result == expected
    getattr(inner, method).assert_awaited_once_with(argument, **kwargs)
