from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper_name", "client_method", "args", "expected"),
    [
        ("get_iponz_patent", "get_patent", ("P1",), "patent"),
        (
            "list_iponz_patents_updated",
            "list_patents_updated",
            (date(2026, 1, 1), date(2026, 1, 2)),
            ["p"],
        ),
        ("get_iponz_trademark", "get_trademark", ("T1",), "trademark"),
        (
            "list_iponz_trademarks_updated",
            "list_trademarks_updated",
            (date(2026, 1, 1), date(2026, 1, 2)),
            ["t"],
        ),
        ("get_iponz_design", "get_design", ("D1",), "design"),
        (
            "list_iponz_designs_updated",
            "list_designs_updated",
            (date(2026, 1, 1), date(2026, 1, 2)),
            ["d"],
        ),
        (
            "list_iponz_designs_registered",
            "list_designs_registered",
            (date(2026, 1, 1), date(2026, 1, 2)),
            ["r"],
        ),
    ],
)
async def test_api_helper_delegates_to_client(
    monkeypatch: pytest.MonkeyPatch,
    helper_name: str,
    client_method: str,
    args: tuple[Any, ...],
    expected: Any,
) -> None:
    from patent_client_agents.iponz_new_zealand import api

    inner = AsyncMock()
    getattr(inner, client_method).return_value = expected

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(api, "IponzClient", Context)
    result = await getattr(api, helper_name)(*args)
    assert result == expected
    getattr(inner, client_method).assert_awaited_once_with(*args)
