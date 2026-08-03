"""High-level async helpers for Thailand's DIP Data Exchange."""

from __future__ import annotations

from .client import (
    CopyrightField,
    GiField,
    PatentField,
    PatentKind,
    SongField,
    ThaiDipClient,
    TrademarkField,
)
from .models import (
    ThaiDipCopyrightRecord,
    ThaiDipGiRecord,
    ThaiDipPatentRecord,
    ThaiDipSongRecord,
    ThaiDipTrademarkRecord,
)


async def search_thai_dip_patents(
    query: str,
    *,
    right_type: PatentKind = "invention",
    field: PatentField = "title",
    limit: int = 25,
) -> tuple[list[ThaiDipPatentRecord], int]:
    async with ThaiDipClient() as client:
        return await client.search_patents(query, right_type=right_type, field=field, limit=limit)


async def get_thai_dip_patent(
    number: str, *, right_type: PatentKind = "invention"
) -> ThaiDipPatentRecord:
    async with ThaiDipClient() as client:
        return await client.get_patent(number, right_type=right_type)


async def search_thai_dip_trademarks(
    query: str, *, field: TrademarkField = "name", limit: int = 25
) -> tuple[list[ThaiDipTrademarkRecord], int]:
    async with ThaiDipClient() as client:
        return await client.search_trademarks(query, field=field, limit=limit)


async def get_thai_dip_trademark(number: str) -> ThaiDipTrademarkRecord:
    async with ThaiDipClient() as client:
        return await client.get_trademark(number)


async def search_thai_dip_copyrights(
    query: str, *, field: CopyrightField = "work_name", limit: int = 25
) -> tuple[list[ThaiDipCopyrightRecord], int]:
    async with ThaiDipClient() as client:
        return await client.search_copyrights(query, field=field, limit=limit)


async def get_thai_dip_copyright(number: str) -> ThaiDipCopyrightRecord:
    async with ThaiDipClient() as client:
        return await client.get_copyright(number)


async def search_thai_dip_songs(
    query: str, *, field: SongField = "song_name", limit: int = 25
) -> tuple[list[ThaiDipSongRecord], int]:
    async with ThaiDipClient() as client:
        return await client.search_songs(query, field=field, limit=limit)


async def search_thai_dip_geographical_indications(
    query: str, *, field: GiField = "name", limit: int = 25
) -> tuple[list[ThaiDipGiRecord], int]:
    async with ThaiDipClient() as client:
        return await client.search_geographical_indications(query, field=field, limit=limit)


async def get_thai_dip_geographical_indication(application_id: str) -> ThaiDipGiRecord:
    async with ThaiDipClient() as client:
        return await client.get_geographical_indication(application_id)
