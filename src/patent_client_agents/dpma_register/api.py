"""High-level async helpers for DPMAconnectPlus."""

from __future__ import annotations

from .client import DpmaRegisterClient
from .models import DesignRecord, PatentUtilityRecord, TrademarkRecord


async def search_dpma_patents(
    expert_query: str, *, limit: int = 25
) -> tuple[list[PatentUtilityRecord], int | None]:
    async with DpmaRegisterClient() as client:
        return await client.search_patents(expert_query, limit=limit)


async def get_dpma_patent(number: str) -> PatentUtilityRecord:
    async with DpmaRegisterClient() as client:
        return await client.get_patent(number)


async def search_dpma_trademarks(
    expert_query: str, *, limit: int = 25
) -> tuple[list[TrademarkRecord], int | None]:
    async with DpmaRegisterClient() as client:
        return await client.search_trademarks(expert_query, limit=limit)


async def get_dpma_trademark(number: str) -> TrademarkRecord:
    async with DpmaRegisterClient() as client:
        return await client.get_trademark(number)


async def search_dpma_designs(
    expert_query: str, *, limit: int = 25
) -> tuple[list[DesignRecord], int | None]:
    async with DpmaRegisterClient() as client:
        return await client.search_designs(expert_query, limit=limit)


async def get_dpma_design(number: str) -> DesignRecord:
    async with DpmaRegisterClient() as client:
        return await client.get_design(number)
