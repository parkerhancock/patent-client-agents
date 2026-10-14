"""High-level async helpers for Thailand's DIP Data Exchange."""

from __future__ import annotations

from patent_client_agents.shared.api import one_shot

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


def _new_client() -> ThaiDipClient:
    return ThaiDipClient()


@one_shot(_new_client, ThaiDipClient.search_patents)
async def search_thai_dip_patents(
    query: str,
    *,
    right_type: PatentKind = "invention",
    field: PatentField = "title",
    limit: int = 25,
) -> tuple[list[ThaiDipPatentRecord], int]: ...


@one_shot(_new_client, ThaiDipClient.get_patent)
async def get_thai_dip_patent(
    number: str, *, right_type: PatentKind = "invention"
) -> ThaiDipPatentRecord: ...


@one_shot(_new_client, ThaiDipClient.search_trademarks)
async def search_thai_dip_trademarks(
    query: str, *, field: TrademarkField = "name", limit: int = 25
) -> tuple[list[ThaiDipTrademarkRecord], int]: ...


@one_shot(_new_client, ThaiDipClient.get_trademark)
async def get_thai_dip_trademark(number: str) -> ThaiDipTrademarkRecord: ...


@one_shot(_new_client, ThaiDipClient.search_copyrights)
async def search_thai_dip_copyrights(
    query: str, *, field: CopyrightField = "work_name", limit: int = 25
) -> tuple[list[ThaiDipCopyrightRecord], int]: ...


@one_shot(_new_client, ThaiDipClient.get_copyright)
async def get_thai_dip_copyright(number: str) -> ThaiDipCopyrightRecord: ...


@one_shot(_new_client, ThaiDipClient.search_songs)
async def search_thai_dip_songs(
    query: str, *, field: SongField = "song_name", limit: int = 25
) -> tuple[list[ThaiDipSongRecord], int]: ...


@one_shot(_new_client, ThaiDipClient.search_geographical_indications)
async def search_thai_dip_geographical_indications(
    query: str, *, field: GiField = "name", limit: int = 25
) -> tuple[list[ThaiDipGiRecord], int]: ...


@one_shot(_new_client, ThaiDipClient.get_geographical_indication)
async def get_thai_dip_geographical_indication(application_id: str) -> ThaiDipGiRecord: ...
