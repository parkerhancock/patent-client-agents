"""High-level async helpers for the Swiss IPI datadelivery API."""

from __future__ import annotations

from .client import IpiSwissregClient
from .models import (
    IpiPatentRecord,
    IpiPublicationRecord,
    IpiSearchMeta,
    IpiSpcRecord,
    IpiTrademarkRecord,
)


async def search_ipi_patents(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiPatentRecord], IpiSearchMeta]:
    async with IpiSwissregClient() as client:
        return await client.search_patents(query, limit=limit, cursor=cursor)


async def get_ipi_patent(number: str) -> IpiPatentRecord:
    async with IpiSwissregClient() as client:
        return await client.get_patent(number)


async def search_ipi_patent_publications(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiPublicationRecord], IpiSearchMeta]:
    async with IpiSwissregClient() as client:
        return await client.search_patent_publications(query, limit=limit, cursor=cursor)


async def search_ipi_trademarks(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiTrademarkRecord], IpiSearchMeta]:
    async with IpiSwissregClient() as client:
        return await client.search_trademarks(query, limit=limit, cursor=cursor)


async def get_ipi_trademark(number: str) -> IpiTrademarkRecord:
    async with IpiSwissregClient() as client:
        return await client.get_trademark(number)


async def search_ipi_spcs(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiSpcRecord], IpiSearchMeta]:
    async with IpiSwissregClient() as client:
        return await client.search_spcs(query, limit=limit, cursor=cursor)


async def get_ipi_spc(number: str) -> IpiSpcRecord:
    async with IpiSwissregClient() as client:
        return await client.get_spc(number)


async def search_ipi_spc_publications(
    query: str, *, limit: int = 25, cursor: str | None = None
) -> tuple[list[IpiPublicationRecord], IpiSearchMeta]:
    async with IpiSwissregClient() as client:
        return await client.search_spc_publications(query, limit=limit, cursor=cursor)
