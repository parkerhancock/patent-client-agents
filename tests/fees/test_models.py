"""Schema-level unit tests for patent_client_agents.fees.models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeItem,
    FeeSchedule,
    RecurringFeeCoverage,
    RecurringFeeCoverageStatus,
    RightType,
)


def _filing(**overrides) -> FeeItem:
    base = dict(
        code="1011",
        label="Basic filing fee - Utility",
        category=FeeCategory.filing,
        rights=[RightType.patent],
        amount=Decimal("350.00"),
        currency="USD",
        tier=EntityTier.large,
    )
    base.update(overrides)
    return FeeItem(**base)


class TestFeeItemValidation:
    def test_currency_normalized_to_upper(self) -> None:
        fee = _filing(currency="usd")
        assert fee.currency == "USD"

    def test_renewal_requires_year(self) -> None:
        with pytest.raises(ValidationError, match="requires 'year' to be set"):
            _filing(category=FeeCategory.renewal, code="7201")

    def test_maintenance_requires_year(self) -> None:
        with pytest.raises(ValidationError, match="requires 'year' to be set"):
            _filing(category=FeeCategory.maintenance, code="1551")

    def test_late_fee_allows_year(self) -> None:
        # EPO codes 752-770 are late-fee surcharges on a specific renewal year.
        fee = _filing(category=FeeCategory.late_fee, code="755", year=5)
        assert fee.year == 5


class TestFeeScheduleValidation:
    def _schedule(self, **overrides) -> FeeSchedule:
        base = dict(
            jurisdiction="US",
            issuing_body="U.S. Patent and Trademark Office",
            office_code="USPTO",
            right=RightType.patent,
            currency="USD",
            effective_date=date(2026, 5, 1),
            source_url="https://www.uspto.gov/fees",
            retrieved_at=date(2026, 5, 18),
            fees=[_filing()],
        )
        base.update(overrides)
        return FeeSchedule(**base)

    def test_jurisdiction_uppercased(self) -> None:
        s = self._schedule(jurisdiction="us")
        assert s.jurisdiction == "US"

    def test_currency_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not match schedule currency"):
            self._schedule(fees=[_filing(currency="EUR")])

    def test_right_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not include schedule right"):
            self._schedule(fees=[_filing(rights=[RightType.trademark])])

    def test_existing_schedule_defaults_to_explicit_partial_coverage(self) -> None:
        coverage = self._schedule().recurring_fee_coverage

        assert coverage.status == RecurringFeeCoverageStatus.partial
        assert coverage.notes == "Recurring-fee coverage has not been audited for completeness."

    def test_partial_coverage_accepts_explicit_gaps(self) -> None:
        coverage = RecurringFeeCoverage(
            status=RecurringFeeCoverageStatus.partial,
            missing_categories=[FeeCategory.renewal],
            missing_years=[5, 6],
        )

        assert coverage.missing_categories == [FeeCategory.renewal]
        assert coverage.missing_years == [5, 6]

    def test_non_recurring_missing_category_rejected(self) -> None:
        with pytest.raises(ValidationError, match="only renewal or maintenance"):
            RecurringFeeCoverage(
                status=RecurringFeeCoverageStatus.partial,
                missing_categories=[FeeCategory.filing],
            )

    def test_complete_coverage_cannot_declare_gaps(self) -> None:
        with pytest.raises(ValidationError, match="cannot declare missing"):
            RecurringFeeCoverage(
                status=RecurringFeeCoverageStatus.complete,
                missing_years=[5],
            )
