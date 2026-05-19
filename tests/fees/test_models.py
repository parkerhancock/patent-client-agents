"""Schema-level unit tests for patent_client_agents.fees.models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeCondition,
    FeeItem,
    FeeSchedule,
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
    def test_minimal_valid_filing_fee(self) -> None:
        fee = _filing()
        assert fee.amount == Decimal("350.00")
        assert fee.tier == EntityTier.large
        assert fee.year is None

    def test_currency_normalized_to_upper(self) -> None:
        fee = _filing(currency="usd")
        assert fee.currency == "USD"

    def test_renewal_requires_year(self) -> None:
        with pytest.raises(ValidationError, match="requires 'year' to be set"):
            _filing(category=FeeCategory.renewal, code="7201")

    def test_maintenance_requires_year(self) -> None:
        with pytest.raises(ValidationError, match="requires 'year' to be set"):
            _filing(category=FeeCategory.maintenance, code="1551")

    def test_renewal_with_year_is_valid(self) -> None:
        fee = _filing(category=FeeCategory.renewal, code="7201", year=10)
        assert fee.year == 10

    def test_late_fee_allows_year(self) -> None:
        # EPO codes 752-770 are late-fee surcharges on a specific renewal year.
        fee = _filing(category=FeeCategory.late_fee, code="755", year=5)
        assert fee.year == 5

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _filing(amount=Decimal("-1"))

    def test_empty_rights_list_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _filing(rights=[])

    def test_condition_attached(self) -> None:
        cond = FeeCondition(trigger="claims_over", threshold=20, per_unit=True)
        fee = _filing(category=FeeCategory.excess_claims, condition=cond)
        assert fee.condition is not None
        assert fee.condition.threshold == 20


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

    def test_minimal_valid_schedule(self) -> None:
        s = self._schedule()
        assert s.currency == "USD"
        assert s.right == RightType.patent
        assert s.key == "US/USPTO/patent"

    def test_jurisdiction_uppercased(self) -> None:
        s = self._schedule(jurisdiction="us")
        assert s.jurisdiction == "US"

    def test_currency_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not match schedule currency"):
            self._schedule(fees=[_filing(currency="EUR")])

    def test_right_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="does not include schedule right"):
            self._schedule(fees=[_filing(rights=[RightType.trademark])])

    def test_empty_fees_rejected(self) -> None:
        with pytest.raises(ValidationError):
            self._schedule(fees=[])
