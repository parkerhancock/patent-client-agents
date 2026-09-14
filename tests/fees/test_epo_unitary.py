"""Tests for the EPO Unitary Patent renewal-fee schedule."""

from __future__ import annotations

from decimal import Decimal

import pytest

from patent_client_agents.fees.models import (
    FeeCategory,
    RecurringFeeCoverageStatus,
    RightType,
)
from patent_client_agents.fees.registry import get_scraper
from patent_client_agents.fees.scrapers.epo_unitary import (
    UNITARY_PATENT_FEES_URL,
    UNITARY_PATENT_RENEWAL_FEES,
    scrape_epo_unitary_patents,
)


def test_official_ladder_is_complete_and_exact() -> None:
    assert list(UNITARY_PATENT_RENEWAL_FEES) == list(range(2, 21))
    assert UNITARY_PATENT_RENEWAL_FEES == {
        2: Decimal("35"),
        3: Decimal("105"),
        4: Decimal("145"),
        5: Decimal("315"),
        6: Decimal("475"),
        7: Decimal("630"),
        8: Decimal("815"),
        9: Decimal("990"),
        10: Decimal("1175"),
        11: Decimal("1460"),
        12: Decimal("1775"),
        13: Decimal("2105"),
        14: Decimal("2455"),
        15: Decimal("2830"),
        16: Decimal("3240"),
        17: Decimal("3640"),
        18: Decimal("4055"),
        19: Decimal("4455"),
        20: Decimal("4855"),
    }


@pytest.mark.asyncio
async def test_schedule_is_distinct_and_recurring_coverage_is_complete() -> None:
    schedule = await scrape_epo_unitary_patents()

    assert schedule.jurisdiction == "UP"
    assert schedule.office_code == "EPO-UP"
    assert schedule.right == RightType.patent
    assert schedule.currency == "EUR"
    assert schedule.source_url == UNITARY_PATENT_FEES_URL
    assert schedule.recurring_fee_coverage.status == RecurringFeeCoverageStatus.complete

    renewals = [fee for fee in schedule.fees if fee.category == FeeCategory.renewal]
    assert [fee.year for fee in renewals] == list(range(2, 21))
    assert [fee.amount for fee in renewals] == list(UNITARY_PATENT_RENEWAL_FEES.values())


@pytest.mark.asyncio
async def test_late_fee_rows_are_fifty_percent_of_each_renewal() -> None:
    schedule = await scrape_epo_unitary_patents()
    renewals = {fee.year: fee for fee in schedule.fees if fee.category == FeeCategory.renewal}
    late_fees = {fee.year: fee for fee in schedule.fees if fee.category == FeeCategory.late_fee}

    assert late_fees.keys() == renewals.keys()
    for year, renewal in renewals.items():
        late = late_fees[year]
        assert late.amount == renewal.amount * Decimal("0.5")
        assert late.condition is not None
        assert late.condition.trigger == "late_days"
        assert "six-month" in (late.condition.description or "")


def test_registry_uses_a_separate_unitary_patent_route() -> None:
    assert get_scraper("EPO", RightType.patent) is not scrape_epo_unitary_patents
    assert get_scraper("EPO-UP", RightType.patent) is scrape_epo_unitary_patents
