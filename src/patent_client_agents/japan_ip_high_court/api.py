"""MCP-free convenience API for the Japan IP High Court connector."""

from __future__ import annotations

from typing import Literal

from .client import JapanIpHighCourtClient
from .models import JapanIpHighCourtCase, JapanIpHighCourtCaseList


async def list_cases() -> JapanIpHighCourtCaseList:
    async with JapanIpHighCourtClient() as client:
        return await client.list_cases()


async def get_case(
    case_number: str,
    *,
    case_status: Literal["pending", "closed", "all"] = "all",
) -> JapanIpHighCourtCase:
    async with JapanIpHighCourtClient() as client:
        return await client.get_case(case_number, case_status=case_status)


__all__ = ["get_case", "list_cases"]
