from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "method", "identifier", "expected"),
    [
        ("get_oepm_patent", "get_patent", "P1", "patent"),
        ("get_oepm_trademark", "get_trademark", "M1", "trademark"),
        ("get_oepm_design", "get_design", "D1", "design"),
    ],
)
async def test_api_helpers_delegate(
    monkeypatch: pytest.MonkeyPatch,
    helper: str,
    method: str,
    identifier: str,
    expected: str,
) -> None:
    from patent_client_agents.oepm_spain import api

    inner = AsyncMock()
    getattr(inner, method).return_value = expected

    class Context:
        async def __aenter__(self) -> AsyncMock:
            return inner

        async def __aexit__(self, *exc: Any) -> None:
            return None

    monkeypatch.setattr(api, "OepmSpainClient", Context)
    assert await getattr(api, helper)(identifier) == expected
    getattr(inner, method).assert_awaited_once_with(identifier)
