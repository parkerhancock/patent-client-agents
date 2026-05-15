"""Tests for the ``get_patent`` MCP tool's error mapping and time budget.

The tool maps:
- Google Patents' "couldn't find this patent" page (``FileNotFoundError``)
  to ``NotFoundError`` so the FriendlyErrors middleware can tag it
  ``[not-retryable] Not found``.
- Wall-clock overruns past ``_GET_PATENT_BUDGET_SECONDS`` to ``RateLimitError``
  so the middleware tags it ``[retryable]``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from law_tools_core.envelope import ListEnvelope
from law_tools_core.exceptions import NotFoundError, RateLimitError
from patent_client_agents.mcp.tools import patents as patents_module


class _FakeClient:
    """Stand-in for GooglePatentsClient that lets each test choose its result."""

    def __init__(self, *, result=None, raises: BaseException | None = None) -> None:
        self._result = result
        self._raises = raises

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get_patent_data(self, patent_number: str):  # noqa: ARG002
        if self._raises is not None:
            raise self._raises
        return self._result


@pytest.mark.asyncio
async def test_get_patent_returns_envelope_on_success() -> None:
    fake_payload = SimpleNamespace(model_dump=lambda: {"patent_number": "US7654321B2"})
    fake = _FakeClient(result=fake_payload)
    with patch.object(patents_module, "GooglePatentsClient", lambda: fake):
        result = await patents_module.get_patent("US7654321B2")
    assert isinstance(result, ListEnvelope)
    assert len(result.items) == 1
    assert result.items[0]["patent_number"] == "US7654321B2"


@pytest.mark.asyncio
async def test_get_patent_maps_filenotfound_to_notfound() -> None:
    fake = _FakeClient(raises=FileNotFoundError("Patent US9999999B2 not found on Google Patents"))
    with patch.object(patents_module, "GooglePatentsClient", lambda: fake):
        with pytest.raises(NotFoundError, match="US9999999B2"):
            await patents_module.get_patent("US9999999B2")


@pytest.mark.asyncio
async def test_get_patent_maps_budget_overrun_to_ratelimit() -> None:
    class SlowClient(_FakeClient):
        async def get_patent_data(self, patent_number: str):  # noqa: ARG002
            await asyncio.sleep(10)
            return None

    with (
        patch.object(patents_module, "GooglePatentsClient", lambda: SlowClient()),
        patch.object(patents_module, "_GET_PATENT_BUDGET_SECONDS", 0.05),
        pytest.raises(RateLimitError, match="rate limiting"),
    ):
        await patents_module.get_patent("US7654321B2")
