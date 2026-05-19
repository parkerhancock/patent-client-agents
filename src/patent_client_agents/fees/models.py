"""Pydantic models for the IP-office fee schedules corpus.

Closed-vocab discriminators (``FeeCategory``, ``EntityTier``, ``RightType``,
``ConditionalTrigger``) keep cross-jurisdiction comparisons honest — the
union of fee types we model is bounded and explicit. New jurisdictions
must reuse the existing vocab or extend it via PR; freeform strings are
not permitted in fee categorization.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    computed_field,
    field_validator,
    model_validator,
)


class RightType(StrEnum):
    """The IP right a fee schedule covers.

    One schedule per ``(jurisdiction, right)`` pair. Plant variety,
    copyright, and trade-secret rights are present in the vocab for
    future expansion but no v1 schedule covers them.
    """

    patent = "patent"
    utility_model = "utility_model"
    trademark = "trademark"
    design = "design"
    plant_variety = "plant_variety"
    copyright = "copyright"
    gi = "gi"


class EntityTier(StrEnum):
    """Discount tier applied to the fee.

    ``none`` means the jurisdiction does not differentiate by entity
    size (e.g., USPTO trademarks since 2025; EPO patents). USPTO patents
    and designs use ``large``/``small``/``micro`` per 37 CFR §§ 1.27, 1.29.
    """

    large = "large"
    small = "small"
    micro = "micro"
    none = "none"


class FeeCategory(StrEnum):
    """Cross-jurisdiction fee category.

    Closed vocab — adding a new category requires a schema change and
    migration of existing corpora. Map new fee types to the closest
    existing category and use ``label`` + ``notes`` for nuance before
    adding a new value.
    """

    # Pre-grant
    filing = "filing"
    search = "search"
    examination = "examination"
    designation = "designation"
    grant = "grant"
    publication = "publication"

    # Post-grant continuing
    renewal = "renewal"  # EPO/EUIPO annual or term-based
    maintenance = "maintenance"  # USPTO 3.5/7.5/11.5

    # Excess / surcharge
    excess_claims = "excess_claims"
    excess_pages = "excess_pages"
    excess_classes = "excess_classes"  # trademarks
    application_size = "application_size"

    # Procedural
    extension = "extension"
    late_fee = "late_fee"
    rce = "rce"
    reissue = "reissue"

    # Adversarial / appellate
    appeal = "appeal"
    petition = "petition"
    opposition = "opposition"
    cancellation = "cancellation"
    ptab = "ptab"
    trial = "trial"

    # Trademarks / Madrid lifecycle
    statement_of_use = "statement_of_use"
    declaration_of_use = "declaration_of_use"
    madrid = "madrid"

    # Designs
    deferment = "deferment"

    # Misc
    translation = "translation"
    transfer = "transfer"
    other = "other"


class ConditionalTrigger(StrEnum):
    """What triggers a conditional / surcharge fee.

    Pairs with ``FeeCondition.threshold`` and ``per_unit`` to express
    common patterns:

    * ``claims_over`` (threshold=20, per_unit=True) — USPTO charge per
      claim over 20.
    * ``pages_over`` (threshold=35, per_unit=True) — EPO page fee for
      each page over 35.
    * ``classes_over`` (threshold=1, per_unit=True) — multi-class TM
      surcharge for each class over the first.
    * ``intent_to_use`` (no threshold) — applies only when ITU basis.
    """

    claims_over = "claims_over"
    independent_claims_over = "independent_claims_over"
    pages_over = "pages_over"
    sheets_over = "sheets_over"  # application size (USPTO)
    classes_over = "classes_over"  # trademarks
    intent_to_use = "intent_to_use"
    paper_filing = "paper_filing"
    late_days = "late_days"
    deferred_publication = "deferred_publication"
    multi_design = "multi_design"  # EUIPO designs, post-2024 reform


class FeeCondition(BaseModel):
    """Conditions under which a surcharge / variable fee applies.

    ``threshold`` is the count at which the fee starts applying.
    ``per_unit`` indicates whether the listed ``amount`` is charged once
    or per-additional-unit over the threshold.
    """

    model_config = ConfigDict(frozen=True)

    trigger: ConditionalTrigger
    threshold: NonNegativeInt | None = None
    per_unit: bool = False
    description: str | None = Field(
        default=None,
        description="Free-text explanation when the trigger alone is ambiguous.",
    )


class FeeItem(BaseModel):
    """One line item from an IP-office fee schedule."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(
        description=(
            "Office-internal fee code, e.g. USPTO '1011' or EPO '001'. "
            "When the office does not publish a stable code, use a "
            "kebab-case slug derived from the label."
        ),
    )
    label: str = Field(description="Human-readable name as published by the office.")
    category: FeeCategory
    rights: list[RightType] = Field(
        min_length=1,
        description=(
            "The rights this fee applies to. Usually a single-element list "
            "matching the parent schedule's ``right``."
        ),
    )
    amount: Decimal = Field(
        ge=Decimal("0"),
        description="Fee amount in the schedule's currency. Decimal — never float.",
    )
    currency: str = Field(
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g., 'USD', 'EUR').",
    )
    tier: EntityTier = EntityTier.none
    year: PositiveInt | None = Field(
        default=None,
        description="Renewal/maintenance year. Required iff category is renewal or maintenance.",
    )
    condition: FeeCondition | None = None
    source_url: str | None = Field(
        default=None,
        description="Deep link to this specific fee (rare — most offices only deep-link the schedule).",
    )
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _year_required_for_recurring(self) -> FeeItem:
        recurring = {FeeCategory.renewal, FeeCategory.maintenance}
        if self.category in recurring and self.year is None:
            raise ValueError(f"{self.category.value} fee {self.code!r} requires 'year' to be set")
        # 'year' is also meaningful on late_fee rows that surcharge a specific
        # renewal year (e.g., EPO codes 752-770 surcharge the matching 732-750
        # renewal year). We don't reject year on non-recurring categories
        # because some offices index surcharges by year — but renewal/maintenance
        # are the categories where year is *required*.
        return self


class FeeSchedule(BaseModel):
    """A fee schedule for one ``(jurisdiction, right)`` pair, at a point in time."""

    model_config = ConfigDict(frozen=True)

    jurisdiction: str = Field(
        description=(
            "ISO 3166 alpha-2 jurisdiction code, or 'EP' for European regional "
            "offices (EPO, EUIPO), or 'UPC' / 'UP'."
        ),
    )
    issuing_body: str = Field(
        description="Full office name (e.g., 'U.S. Patent and Trademark Office')."
    )
    office_code: str = Field(
        description="Short office code (USPTO, EPO, EUIPO, JPO, ...).",
    )
    right: RightType
    currency: str = Field(min_length=3, max_length=3)
    effective_date: date = Field(
        description="Date the schedule became (or becomes) the operative fee table.",
    )
    source_url: str = Field(description="Canonical upstream URL for the schedule.")
    statutory_basis: str | None = Field(
        default=None,
        description="Statute / regulation the schedule is set under (e.g., '37 CFR 1.16').",
    )
    retrieved_at: date = Field(
        description="Date the schedule was last fetched from upstream.",
    )
    fees: list[FeeItem] = Field(min_length=1)
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("jurisdiction")
    @classmethod
    def _jurisdiction_upper(cls, v: str) -> str:
        return v.upper()

    @model_validator(mode="after")
    def _fees_match_right_and_currency(self) -> FeeSchedule:
        for fee in self.fees:
            if fee.currency != self.currency:
                raise ValueError(
                    f"fee {fee.code!r} currency {fee.currency!r} does not match "
                    f"schedule currency {self.currency!r}"
                )
            if self.right not in fee.rights:
                raise ValueError(
                    f"fee {fee.code!r} rights {fee.rights} does not include "
                    f"schedule right {self.right.value!r}"
                )
        return self

    @computed_field  # type: ignore[misc]
    @property
    def key(self) -> str:
        """Stable lookup key: ``'<jurisdiction>/<office_code>/<right>'``."""
        return f"{self.jurisdiction}/{self.office_code}/{self.right.value}"


class JurisdictionMeta(BaseModel):
    """Lean summary row used by ``list_jurisdictions``.

    One row per bundled schedule; surfaces freshness without forcing the
    caller to load every fee table.
    """

    model_config = ConfigDict(frozen=True)

    jurisdiction: str
    office_code: str
    issuing_body: str
    right: RightType
    currency: str
    effective_date: date
    retrieved_at: date
    source_url: str
    fee_count: NonNegativeInt
    days_since_retrieval: NonNegativeInt


# Type alias used by the lookup API; declared here so importers can
# `from patent_client_agents.fees.models import JurisdictionKey`.
JurisdictionKey = tuple[str, RightType]
"""``(jurisdiction-or-office-code, right)`` lookup key. Resolved by the client."""


# Re-exported literal narrowings for tool annotation use sites that
# want autocomplete on the small handful of v1 jurisdictions.
JurisdictionV1 = Literal["US", "EP", "USPTO", "EPO", "EUIPO"]


__all__ = [
    "RightType",
    "EntityTier",
    "FeeCategory",
    "ConditionalTrigger",
    "FeeCondition",
    "FeeItem",
    "FeeSchedule",
    "JurisdictionMeta",
    "JurisdictionKey",
    "JurisdictionV1",
]
