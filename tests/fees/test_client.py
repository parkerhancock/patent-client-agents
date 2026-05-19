"""Tests for the FeesClient dispatcher + jurisdiction resolver."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from patent_client_agents.fees import FeesClient, RightType, registry
from patent_client_agents.fees.client import (
    UnknownJurisdictionError,
    resolve_jurisdiction,
)
from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeItem,
    FeeSchedule,
)


class TestResolveJurisdiction:
    def test_uspto_alias(self) -> None:
        assert resolve_jurisdiction("USPTO", RightType.patent) == ("US", "USPTO")

    def test_us_alias(self) -> None:
        assert resolve_jurisdiction("US", RightType.patent) == ("US", "USPTO")

    def test_lowercase_accepted(self) -> None:
        assert resolve_jurisdiction("uspto", RightType.patent) == ("US", "USPTO")

    def test_ep_routes_patent_to_epo(self) -> None:
        assert resolve_jurisdiction("EP", RightType.patent) == ("EP", "EPO")

    def test_ep_routes_trademark_to_euipo(self) -> None:
        assert resolve_jurisdiction("EP", RightType.trademark) == ("EP", "EUIPO")

    def test_ep_routes_design_to_euipo(self) -> None:
        assert resolve_jurisdiction("EP", RightType.design) == ("EP", "EUIPO")

    def test_epo_with_trademark_raises(self) -> None:
        with pytest.raises(UnknownJurisdictionError, match="EPO does not have a trademark"):
            resolve_jurisdiction("EPO", RightType.trademark)

    def test_euipo_with_patent_raises(self) -> None:
        with pytest.raises(UnknownJurisdictionError, match="EUIPO does not have a patent"):
            resolve_jurisdiction("EUIPO", RightType.patent)

    def test_unknown_value_raises(self) -> None:
        with pytest.raises(UnknownJurisdictionError, match="Unknown jurisdiction"):
            resolve_jurisdiction("ZZ", RightType.patent)


def _fixture_schedule() -> FeeSchedule:
    """A small synthetic schedule covering filing, maintenance, excess_claims."""
    return FeeSchedule(
        jurisdiction="US",
        issuing_body="U.S. Patent and Trademark Office",
        office_code="USPTO",
        right=RightType.patent,
        currency="USD",
        effective_date=date(2026, 5, 1),
        source_url="https://www.uspto.gov/fees",
        retrieved_at=date(2026, 5, 18),
        fees=[
            FeeItem(
                code="1011",
                label="Basic filing fee - Utility",
                category=FeeCategory.filing,
                rights=[RightType.patent],
                amount=Decimal("350"),
                currency="USD",
                tier=EntityTier.large,
            ),
            FeeItem(
                code="2011",
                label="Basic filing fee - Utility",
                category=FeeCategory.filing,
                rights=[RightType.patent],
                amount=Decimal("140"),
                currency="USD",
                tier=EntityTier.small,
            ),
            FeeItem(
                code="1551",
                label="Maintenance 3.5yr",
                category=FeeCategory.maintenance,
                rights=[RightType.patent],
                amount=Decimal("2150"),
                currency="USD",
                tier=EntityTier.large,
                year=4,
            ),
            FeeItem(
                code="1552",
                label="Maintenance 7.5yr",
                category=FeeCategory.maintenance,
                rights=[RightType.patent],
                amount=Decimal("4040"),
                currency="USD",
                tier=EntityTier.large,
                year=8,
            ),
        ],
    )


@pytest.fixture
def patched_dispatch():
    """Replace the real USPTO scraper with one that returns the synthetic schedule."""

    async def _fake_scraper() -> FeeSchedule:
        return _fixture_schedule()

    with patch.dict(
        registry._DISPATCH,
        {("USPTO", RightType.patent): _fake_scraper},
    ):
        yield


class TestFeesClientLookup:
    @pytest.mark.asyncio
    async def test_get_schedule_routes_through_dispatcher(self, patched_dispatch) -> None:
        async with FeesClient() as c:
            sched = await c.get_schedule("US", RightType.patent)
        assert sched.office_code == "USPTO"
        assert len(sched.fees) == 4

    @pytest.mark.asyncio
    async def test_lookup_filters_by_category_and_tier(self, patched_dispatch) -> None:
        async with FeesClient() as c:
            hits = await c.lookup_fee("USPTO", category="filing", tier=EntityTier.small)
        assert len(hits) == 1
        assert hits[0].code == "2011"
        assert hits[0].amount == Decimal("140")

    @pytest.mark.asyncio
    async def test_lookup_year_filter(self, patched_dispatch) -> None:
        async with FeesClient() as c:
            hits = await c.lookup_fee(
                "USPTO", category="maintenance", year=8, tier=EntityTier.large
            )
        assert len(hits) == 1
        assert hits[0].code == "1552"

    @pytest.mark.asyncio
    async def test_lookup_excludes_renewal_when_year_not_specified(self, patched_dispatch) -> None:
        async with FeesClient() as c:
            hits = await c.lookup_fee("USPTO", tier=EntityTier.large)
        # Only filing rows should come back (year=None filter excludes maintenance)
        codes = sorted(h.code for h in hits)
        assert codes == ["1011"]
