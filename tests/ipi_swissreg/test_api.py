from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper_name", "client_method", "argument", "kwargs", "expected"),
    [
        ("search_ipi_patents", "search_patents", "q", {"limit": 3, "cursor": "c"}, ([], "m")),
        ("get_ipi_patent", "get_patent", "P1", {}, "patent"),
        (
            "search_ipi_patent_publications",
            "search_patent_publications",
            "q",
            {"limit": 4, "cursor": None},
            ([], "m"),
        ),
        (
            "search_ipi_trademarks",
            "search_trademarks",
            "q",
            {"limit": 5, "cursor": None},
            ([], "m"),
        ),
        ("get_ipi_trademark", "get_trademark", "T1", {}, "trademark"),
        ("search_ipi_spcs", "search_spcs", "q", {"limit": 6, "cursor": None}, ([], "m")),
        ("get_ipi_spc", "get_spc", "S1", {}, "spc"),
        (
            "search_ipi_spc_publications",
            "search_spc_publications",
            "q",
            {"limit": 7, "cursor": "next"},
            ([], "m"),
        ),
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
    from patent_client_agents.ipi_swissreg import api

    inner = AsyncMock()
    getattr(inner, client_method).return_value = expected

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(api, "IpiSwissregClient", Context)
    result = await getattr(api, helper_name)(argument, **kwargs)
    assert result == expected
    getattr(inner, client_method).assert_awaited_once_with(argument, **kwargs)
