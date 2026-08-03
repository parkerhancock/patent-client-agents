"""High-level async helpers for Spain's OEPM CEO service."""

from __future__ import annotations

from .client import OepmSpainClient
from .models import OepmDesignRecord, OepmPatentRecord, OepmTrademarkRecord


async def get_oepm_patent(identifier: str) -> OepmPatentRecord:
    async with OepmSpainClient() as client:
        return await client.get_patent(identifier)


async def get_oepm_trademark(identifier: str) -> OepmTrademarkRecord:
    async with OepmSpainClient() as client:
        return await client.get_trademark(identifier)


async def get_oepm_design(identifier: str) -> OepmDesignRecord:
    async with OepmSpainClient() as client:
        return await client.get_design(identifier)
