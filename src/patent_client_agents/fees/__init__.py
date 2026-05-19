"""IP-office fee schedules — live-fetch with hishel cache.

Per-office scrapers translate the upstream fee table into a uniform
:class:`FeeSchedule`. Each scraper inherits from
:class:`law_tools_core.BaseAsyncClient` and shares the hishel-backed
SQLite cache machinery used by the rest of the connectors; default TTL
is 7 days (fees don't change weekly, an adjustment reaches new sessions
the same day at worst).

v1 routes:

* US/USPTO  — patents, trademarks, designs (one HTML page)
* EP/EPO    — patents
* EP/EUIPO  — trademarks, designs (REUD reform 2024/2822)

CONNECTOR_STANDARDS.md classification: ``category=substantive_law``,
``transport=mcp_proxy``, ``update_strategy=live_proxy``,
``update_cadence=annual``.
"""

from __future__ import annotations

from .api import (
    estimate_freshness,
    get_schedule,
    list_jurisdictions,
    lookup_fee,
)
from .client import FeesClient, UnknownJurisdictionError, resolve_jurisdiction
from .models import (
    ConditionalTrigger,
    EntityTier,
    FeeCategory,
    FeeCondition,
    FeeItem,
    FeeSchedule,
    JurisdictionMeta,
    RightType,
)
from .registry import OFFICES, list_supported_routes

__all__ = [
    "FeesClient",
    "UnknownJurisdictionError",
    "resolve_jurisdiction",
    "FeeSchedule",
    "FeeItem",
    "FeeCondition",
    "FeeCategory",
    "EntityTier",
    "RightType",
    "ConditionalTrigger",
    "JurisdictionMeta",
    "get_schedule",
    "list_jurisdictions",
    "lookup_fee",
    "estimate_freshness",
    "OFFICES",
    "list_supported_routes",
]
