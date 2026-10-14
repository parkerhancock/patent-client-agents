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
from unittest.mock import patch

import pytest

from mcp_data_core.exceptions import NotFoundError, RateLimitError
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


@pytest.mark.asyncio
async def test_get_patent_list_reports_missing_patent() -> None:
    class MixedClient(_FakeClient):
        async def get_patent_data(self, patent_number: str):
            if patent_number == "US9999999B2":
                raise FileNotFoundError(f"Patent {patent_number} not found on Google Patents")
            return {"patent_number": patent_number, "title": "Widget"}

    with patch.object(patents_module, "GooglePatentsClient", lambda: MixedClient()):
        result = await patents_module.get_patent(["US10123456B2", "US9999999B2", "EP3456789A1"])

    assert [item["patent_number"] for item in result.items] == ["US10123456B2", "EP3456789A1"]
    assert result.not_found == ["US9999999B2"]
    assert result.summary == "Fetched 2 of 3 patents. Not found: US9999999B2."
