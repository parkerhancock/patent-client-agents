"""DPMAconnectPlus register connector.

This connector is mock-only tested. Community validation with a real account
or sanitized response samples is welcome.
"""

from .api import (
    get_dpma_design,
    get_dpma_patent,
    get_dpma_trademark,
    search_dpma_designs,
    search_dpma_patents,
    search_dpma_trademarks,
)
from .client import DpmaRegisterClient
from .models import DesignRecord, PatentUtilityRecord, TrademarkRecord

__all__ = [
    "DesignRecord",
    "DpmaRegisterClient",
    "PatentUtilityRecord",
    "TrademarkRecord",
    "get_dpma_design",
    "get_dpma_patent",
    "get_dpma_trademark",
    "search_dpma_designs",
    "search_dpma_patents",
    "search_dpma_trademarks",
]
