"""Thailand DIP Data Exchange connector. Catalogue-schema tested only."""

from .api import (
    get_thai_dip_copyright,
    get_thai_dip_geographical_indication,
    get_thai_dip_patent,
    get_thai_dip_trademark,
    search_thai_dip_copyrights,
    search_thai_dip_geographical_indications,
    search_thai_dip_patents,
    search_thai_dip_songs,
    search_thai_dip_trademarks,
)
from .client import ThaiDipClient
from .models import (
    ThaiDipCopyrightRecord,
    ThaiDipGiRecord,
    ThaiDipPatentRecord,
    ThaiDipSongRecord,
    ThaiDipTrademarkRecord,
)

__all__ = [
    "ThaiDipClient",
    "ThaiDipCopyrightRecord",
    "ThaiDipGiRecord",
    "ThaiDipPatentRecord",
    "ThaiDipSongRecord",
    "ThaiDipTrademarkRecord",
    "get_thai_dip_copyright",
    "get_thai_dip_geographical_indication",
    "get_thai_dip_patent",
    "get_thai_dip_trademark",
    "search_thai_dip_copyrights",
    "search_thai_dip_geographical_indications",
    "search_thai_dip_patents",
    "search_thai_dip_songs",
    "search_thai_dip_trademarks",
]
