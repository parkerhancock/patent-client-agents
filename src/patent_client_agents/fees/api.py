"""One-shot convenience helpers around :class:`FeesClient`.

Mirror the dpma_statutes / tw_trade_secrets pattern: a context-managed
client for repeated calls, plus module-level coroutines that handle
construction and cleanup for one-off lookups.
"""

from __future__ import annotations

from datetime import date

from .client import FeesClient
from .models import (
    EntityTier,
    FeeItem,
    FeeSchedule,
    JurisdictionMeta,
    RightType,
)


async def get_schedule(
    jurisdiction: str,
    right: RightType | str = RightType.patent,
) -> FeeSchedule:
    """Fetch the full schedule for ``(jurisdiction, right)``."""
    async with FeesClient() as client:
        return await client.get_schedule(jurisdiction, right)


async def list_jurisdictions() -> list[JurisdictionMeta]:
    """Return one ``JurisdictionMeta`` per supported ``(office, right)`` route."""
    async with FeesClient() as client:
        return await client.list_schedules()


async def lookup_fee(
    jurisdiction: str,
    *,
    category: str | None = None,
    tier: EntityTier | str = EntityTier.large,
    year: int | None = None,
    right: RightType | str = RightType.patent,
) -> list[FeeItem]:
    """Filter a schedule down to matching line items. See :meth:`FeesClient.lookup_fee`."""
    async with FeesClient() as client:
        return await client.lookup_fee(
            jurisdiction,
            category=category,
            tier=tier,
            year=year,
            right=right,
        )


def estimate_freshness(schedule: FeeSchedule) -> dict[str, int | str | bool]:
    """Compute a small dict describing how stale a schedule is.

    Returns ``{"days_since_retrieval", "days_since_effective",
    "retrieved_at", "effective_date"}``. Pure function — no I/O.
    Callers (e.g., MCP tools) use this to decorate response summaries.
    """
    today = date.today()
    return {
        "retrieved_at": schedule.retrieved_at.isoformat(),
        "effective_date": schedule.effective_date.isoformat(),
        "days_since_retrieval": max(0, (today - schedule.retrieved_at).days),
        "days_since_effective": max(0, (today - schedule.effective_date).days),
    }


__all__ = [
    "get_schedule",
    "list_jurisdictions",
    "lookup_fee",
    "estimate_freshness",
]
