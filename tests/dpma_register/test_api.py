from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper_name", "client_method", "argument", "kwargs", "expected"),
    [
        ("search_dpma_patents", "search_patents", "q", {"limit": 3}, ([], 0)),
        ("get_dpma_patent", "get_patent", "P1", {}, "patent"),
        ("search_dpma_trademarks", "search_trademarks", "q", {"limit": 4}, ([], 0)),
        ("get_dpma_trademark", "get_trademark", "T1", {}, "trademark"),
        ("search_dpma_designs", "search_designs", "q", {"limit": 5}, ([], 0)),
        ("get_dpma_design", "get_design", "D1", {}, "design"),
    ],
)
async def test_api_helper_delegates_to_client(
    monkeypatch: pytest.MonkeyPatch,
    helper_name: str,
    client_method: str,
    argument: str,
    kwargs: dict[str, Any],
    expected: Any,
) -> None:
    from patent_client_agents.dpma_register import api

    inner = AsyncMock()
    getattr(inner, client_method).return_value = expected

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(api, "DpmaRegisterClient", Context)

    result = await getattr(api, helper_name)(argument, **kwargs)

    assert result == expected
    getattr(inner, client_method).assert_awaited_once_with(argument, **kwargs)
