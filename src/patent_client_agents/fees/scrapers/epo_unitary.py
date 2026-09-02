"""EPO Unitary Patent renewal-fee schedule.

The EPO publishes the complete year 2-20 ladder in Article 2 of the
Rules relating to Fees for Unitary Patent Protection (RFeesUPP).  Unlike
the pending-application fee schedule, this table is small, stable, and
published directly in the rule, so it is represented as a source-backed
static schedule rather than scraped from the general EPO fee BFF.

This is deliberately a separate ``EPO-UP`` route.  A European patent
application pending before the EPO and a European patent with unitary
effect are different rights with different recurring-fee schedules.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeCondition,
    FeeItem,
    FeeSchedule,
    RecurringFeeCoverage,
    RecurringFeeCoverageStatus,
    RightType,
)

UNITARY_PATENT_FEES_URL = "https://www.epo.org/en/legal/up-upc/2022/upf_2.html"
UNITARY_PATENT_RULE_13_URL = "https://www.epo.org/en/legal/up-upc/2022/upr_13.html"

# Current Article 2(1), item 1 schedule.  The rules entered into force
# with the Unitary Patent system on 1 June 2023.
UNITARY_PATENT_RENEWAL_FEES: dict[int, Decimal] = {
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


def _renewal_fee(year: int, amount: Decimal) -> FeeItem:
    return FeeItem(
        code=f"upp-renewal-{year}",
        label=f"Renewal fee for the {year}{_ordinal_suffix(year)} year",
        category=FeeCategory.renewal,
        rights=[RightType.patent],
        amount=amount,
        currency="EUR",
        tier=EntityTier.none,
        year=year,
        source_url=UNITARY_PATENT_FEES_URL,
    )


def _late_fee(year: int, amount: Decimal) -> FeeItem:
    return FeeItem(
        code=f"upp-late-renewal-{year}",
        label=f"Additional fee for late payment of the {year}{_ordinal_suffix(year)} year",
        category=FeeCategory.late_fee,
        rights=[RightType.patent],
        amount=amount / Decimal("2"),
        currency="EUR",
        tier=EntityTier.none,
        year=year,
        condition=FeeCondition(
            trigger="late_days",
            threshold=0,
            description=(
                "Applies when the renewal fee is paid within the six-month period "
                "under Rule 13(3) UPR; surcharge is 50% of the renewal fee."
            ),
        ),
        source_url=UNITARY_PATENT_FEES_URL,
    )


def _ordinal_suffix(year: int) -> str:
    if 10 <= year % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(year % 10, "th")


async def scrape_epo_unitary_patents() -> FeeSchedule:
    """Return the current official Unitary Patent renewal-fee schedule."""
    fees = [
        item
        for year, amount in UNITARY_PATENT_RENEWAL_FEES.items()
        for item in (_renewal_fee(year, amount), _late_fee(year, amount))
    ]
    return FeeSchedule(
        jurisdiction="UP",
        issuing_body="European Patent Office",
        office_code="EPO-UP",
        right=RightType.patent,
        currency="EUR",
        effective_date=date(2023, 6, 1),
        source_url=UNITARY_PATENT_FEES_URL,
        statutory_basis=(
            "Article 2, Rules relating to Fees for Unitary Patent Protection; "
            "Rule 13, Rules relating to Unitary Patent Protection."
        ),
        retrieved_at=date.today(),
        fees=fees,
        recurring_fee_coverage=RecurringFeeCoverage(
            status=RecurringFeeCoverageStatus.complete,
        ),
        notes=(
            "Complete ordinary renewal ladder for years 2-20, plus the 50% "
            "late-payment surcharge for each year. Fees are due only for years "
            "following the calendar year in which grant is mentioned. Rule 13 "
            "controls due dates, early payment, the six-month late period, and "
            f"registration-notification timing ({UNITARY_PATENT_RULE_13_URL}). "
            "A 15% licence-of-right reduction is not applied by this schedule."
        ),
    )


__all__ = [
    "UNITARY_PATENT_FEES_URL",
    "UNITARY_PATENT_RENEWAL_FEES",
    "UNITARY_PATENT_RULE_13_URL",
    "scrape_epo_unitary_patents",
]
