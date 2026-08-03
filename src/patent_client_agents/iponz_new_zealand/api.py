"""High-level async helpers for the New Zealand IPONZ API."""

from __future__ import annotations

from datetime import date

from .client import IponzClient
from .models import (
    IponzDesignRecord,
    IponzPatentRecord,
    IponzRegisterSummary,
    IponzTrademarkRecord,
)


async def get_iponz_patent(number: str) -> IponzPatentRecord:
    async with IponzClient() as client:
        return await client.get_patent(number)


async def list_iponz_patents_updated(start: date, end: date) -> list[IponzRegisterSummary]:
    async with IponzClient() as client:
        return await client.list_patents_updated(start, end)


async def get_iponz_trademark(number: str) -> IponzTrademarkRecord:
    async with IponzClient() as client:
        return await client.get_trademark(number)


async def list_iponz_trademarks_updated(start: date, end: date) -> list[IponzRegisterSummary]:
    async with IponzClient() as client:
        return await client.list_trademarks_updated(start, end)


async def get_iponz_design(number: str) -> IponzDesignRecord:
    async with IponzClient() as client:
        return await client.get_design(number)


async def list_iponz_designs_updated(start: date, end: date) -> list[IponzRegisterSummary]:
    async with IponzClient() as client:
        return await client.list_designs_updated(start, end)


async def list_iponz_designs_registered(start: date, end: date) -> list[IponzRegisterSummary]:
    async with IponzClient() as client:
        return await client.list_designs_registered(start, end)
