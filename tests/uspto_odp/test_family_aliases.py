"""Compatibility aliases for commonly miscalled USPTO family tools."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.mcp.tools.uspto import get_patent_family


@pytest.mark.asyncio
async def test_get_patent_family_accepts_publication_number_alias() -> None:
    fake_response = SimpleNamespace(model_dump=lambda: {"rootApplication": "17123456"})

    with patch("patent_client_agents.mcp.tools.uspto.UsptoOdpClient") as mock_cls:
        mock_client = mock_cls.return_value.__aenter__.return_value
        mock_client.get_family = AsyncMock(return_value=fake_response)

        result = await get_patent_family(publication_number="US20230012345A1")

    mock_client.get_family.assert_awaited_once_with(
        "US20230012345A1",
        identifier_type="publication",
    )
    assert result["rootApplication"] == "17123456"
