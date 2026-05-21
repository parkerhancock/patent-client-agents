"""Tests for the IPOS Singapore fee scraper.

Two layers:

* **Unit tests** of helpers — amount parser, no-fee detection, PF15
  year-band expander, design 5-year-period year mapper, per-class /
  per-claim condition detection, categorizers.
* **Integration tests** that drive the per-right builders against
  the cached IPOS HTML pages
  (``tests/fees/fixtures/sg_ipos_{patents,trademarks,designs}_2026-05-19.html``).

Refresh the fixtures by re-fetching:

    https://www.ipos.gov.sg/about-ip/patents/forms-and-fees-singapore/
    https://www.ipos.gov.sg/about-ip/trade-marks/forms-and-fees/
    https://www.ipos.gov.sg/about-ip/designs/forms-and-fees/
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html as L

from patent_client_agents.fees.models import (
    ConditionalTrigger,
    FeeCategory,
    FeeSchedule,
    RightType,
)
from patent_client_agents.fees.scrapers import ipos

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PATENT_FIXTURE = FIXTURE_DIR / "sg_ipos_patents_2026-05-19.html"
TM_FIXTURE = FIXTURE_DIR / "sg_ipos_trademarks_2026-05-19.html"
DESIGN_FIXTURE = FIXTURE_DIR / "sg_ipos_designs_2026-05-19.html"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseSgdAmounts:
    def test_single_amount(self) -> None:
        assert ipos._parse_sgd_amounts("S$170") == [Decimal("170")]

    def test_with_thousands(self) -> None:
        assert ipos._parse_sgd_amounts("S$1,735") == [Decimal("1735")]
        assert ipos._parse_sgd_amounts("S$1,750 plus S$80 for each claim") == [
            Decimal("1750"),
            Decimal("80"),
        ]

    def test_tm4_split_pricing(self) -> None:
        # TM4 publishes two prices in one body — pre-approved DB vs
        # custom specification.
        amounts = ipos._parse_sgd_amounts(
            "For class(es) whose specification items are fully adopted from "
            "IPOS' Classification Database of pre-approved descriptions of "
            "goods and servicesS$280 per classFor class(es) whose "
            "specification items are not fully adopted from IPOS' "
            "Classification Database:S$410 per class"
        )
        assert amounts == [Decimal("280"), Decimal("410")]

    def test_design_d3_multi_amount(self) -> None:
        # D3 publishes two amounts in one body — per design + per
        # deferment request.
        amounts = ipos._parse_sgd_amounts(
            "S$200 in respect of each designS$40 in respect of each request"
        )
        assert amounts == [Decimal("200"), Decimal("40")]

    def test_no_amount(self) -> None:
        assert ipos._parse_sgd_amounts("No fee") == []

    def test_empty(self) -> None:
        assert ipos._parse_sgd_amounts("") == []


class TestHasNoFee:
    def test_no_fee_payable(self) -> None:
        assert ipos._has_no_fee("No fee payable")

    def test_no_fee_lower(self) -> None:
        assert ipos._has_no_fee("No fee")

    def test_amount_present_is_not_no_fee(self) -> None:
        assert not ipos._has_no_fee("S$170")


class TestPf15RenewalYears:
    def test_5_6_7_band(self) -> None:
        assert ipos._pf15_renewal_years(
            "For each year of renewal in respect of the 5th, 6th or 7th year of the patent"
        ) == [5, 6, 7]

    def test_8_9_10_band(self) -> None:
        assert ipos._pf15_renewal_years(
            "For each year of renewal in respect of the 8th, 9th or 10th year of the patent"
        ) == [8, 9, 10]

    def test_year_20_single(self) -> None:
        assert ipos._pf15_renewal_years("For renewal of the 20th year of the patent") == [20]

    def test_post_20(self) -> None:
        # "after the 20th year" represents post-20 renewals; year=21
        # is a sentinel for "post-final-statutory-term".
        assert ipos._pf15_renewal_years(
            "For each year of renewal after the 20th year of the patent"
        ) == [21]

    def test_no_year(self) -> None:
        assert ipos._pf15_renewal_years("Late payment of renewal fee") == []


class TestDesignRenewalYear:
    def test_first_period(self) -> None:
        assert ipos._design_renewal_year("(a) for the first period of 5 years") == 10

    def test_second_period(self) -> None:
        assert ipos._design_renewal_year("(b) for the second period of 5 years") == 15

    def test_third_period(self) -> None:
        assert ipos._design_renewal_year("(c) for the third period of 5 years") == 20

    def test_fourth_period(self) -> None:
        assert ipos._design_renewal_year("(d) for the fourth period of 5 years") == 25

    def test_no_match(self) -> None:
        assert ipos._design_renewal_year("Application for extension") is None


class TestPerClaimCondition:
    def test_pf11_claim_over_15(self) -> None:
        cond = ipos._per_claim_condition("S$1,750 plus S$80 for each claim over 15 claims")
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.claims_over
        assert cond.threshold == 15
        assert cond.per_unit is True

    def test_pf14_claim_over_20(self) -> None:
        cond = ipos._per_claim_condition("S$210 plus S$40 for each claim in excess of 20 claims")
        assert cond is not None
        assert cond.threshold == 20

    def test_no_per_claim(self) -> None:
        assert ipos._per_claim_condition("S$1,250") is None


class TestPerClassCondition:
    def test_per_additional_class(self) -> None:
        cond = ipos._per_class_condition("S$1,000 per additional class")
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.classes_over
        assert cond.threshold == 1

    def test_per_class_only(self) -> None:
        # "S$280 per class" applies to every class — threshold=0.
        cond = ipos._per_class_condition("S$280 per class")
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.classes_over
        assert cond.threshold == 0

    def test_no_per_class(self) -> None:
        assert ipos._per_class_condition("S$1,250") is None


class TestCategorizers:
    def test_patent_pf1_filing(self) -> None:
        assert (
            ipos._categorize_patent("PF1", "Request for the Grant of a Patent")
            == FeeCategory.filing
        )

    def test_patent_pf15_renewal(self) -> None:
        assert (
            ipos._categorize_patent(
                "PF15",
                "For each year of renewal in respect of the 5th, 6th or 7th year of the patent",
            )
            == FeeCategory.renewal
        )

    def test_patent_late_payment(self) -> None:
        assert (
            ipos._categorize_patent(
                "PF15", "For late payment of renewal fee not exceeding one month"
            )
            == FeeCategory.late_fee
        )

    def test_patent_additional_fee_section_opener_not_late_fee(self) -> None:
        # The PF15 section opener "Payment of Renewal Fee and Any
        # Additional Fee" must NOT trigger late_fee — only "late
        # payment" should.
        assert (
            ipos._categorize_patent(
                "PF15",
                "Payment of Renewal Fee and Any Additional Fee — Renewal Fee(a) For each year of renewal in respect of the 5th, 6th or 7th year of the patent",
            )
            == FeeCategory.renewal
        )

    def test_trademark_tm4_filing(self) -> None:
        assert (
            ipos._categorize_trademark("TM4", "Application to register a trade mark")
            == FeeCategory.filing
        )

    def test_trademark_renewal(self) -> None:
        assert (
            ipos._categorize_trademark("TM19", "Application for renewal of trade mark")
            == FeeCategory.renewal
        )

    def test_trademark_madrid(self) -> None:
        assert (
            ipos._categorize_trademark("MM2(E)", "Application for international registration")
            == FeeCategory.madrid
        )

    def test_design_extension_is_renewal(self) -> None:
        # The D8 "Application for extension of period of registration"
        # row is the design renewal track — must NOT be miscategorized
        # as filing despite containing "registration of a design".
        assert (
            ipos._categorize_design(
                "D8",
                "Application for extension of period of registration of a design — (a) for the first period of 5 years",
            )
            == FeeCategory.renewal
        )

    def test_design_d3_filing(self) -> None:
        assert (
            ipos._categorize_design(
                "D3", "Application for registration of a design under Section 11"
            )
            == FeeCategory.filing
        )


# ──────────────────────────────────────────────────────────────────────
# Integration tests against the cached HTML fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def patent_doc() -> L.HtmlElement:
    return L.fromstring(PATENT_FIXTURE.read_bytes())


@pytest.fixture(scope="module")
def trademark_doc() -> L.HtmlElement:
    return L.fromstring(TM_FIXTURE.read_bytes())


@pytest.fixture(scope="module")
def design_doc() -> L.HtmlElement:
    return L.fromstring(DESIGN_FIXTURE.read_bytes())


class TestBuildPatentFees:
    def test_yields_substantial_schedule(self, patent_doc) -> None:
        fees = ipos._build_patent_fees(patent_doc)
        # 102-row patent table + PF15 year expansion → ~100+ FeeItems.
        assert len(fees) >= 80

    def test_pf1_filing_fee(self, patent_doc) -> None:
        fees = ipos._build_patent_fees(patent_doc)
        pf1 = next(f for f in fees if f.code == "sg-pat-pf1-request-for-the-grant-of-a-patent")
        assert pf1.amount == Decimal("170")
        assert pf1.category == FeeCategory.filing

    def test_excess_claims_emits_surcharge(self, patent_doc) -> None:
        fees = ipos._build_patent_fees(patent_doc)
        excess = [f for f in fees if f.category == FeeCategory.excess_claims]
        assert len(excess) >= 1
        # PF11/PF12 surcharge is S$80 per claim over 15.
        s80 = [f for f in excess if f.amount == Decimal("80")]
        assert s80
        cond = s80[0].condition
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.claims_over
        assert cond.threshold == 15

    def test_pf15_year_band_5_to_7_at_176(self, patent_doc) -> None:
        fees = ipos._build_patent_fees(patent_doc)
        y5_7 = [
            f
            for f in fees
            if f.category == FeeCategory.renewal
            and f.amount == Decimal("176")
            and f.year in (5, 6, 7)
        ]
        # Years 5, 6, 7 each emit once (PF15(a)).
        years = sorted(f.year for f in y5_7)
        assert 5 in years
        assert 6 in years
        assert 7 in years

    def test_pf15_year_band_8_to_10_at_460(self, patent_doc) -> None:
        fees = ipos._build_patent_fees(patent_doc)
        years = sorted(
            {
                f.year
                for f in fees
                if f.category == FeeCategory.renewal
                and f.amount == Decimal("460")
                and f.year in (8, 9, 10)
            }
        )
        assert years == [8, 9, 10]

    def test_pf15_post_20_year_band(self, patent_doc) -> None:
        # PF15(g) covers "after the 20th year" — represented as year=21.
        fees = ipos._build_patent_fees(patent_doc)
        post20 = [
            f
            for f in fees
            if f.category == FeeCategory.renewal and f.year == 21 and f.amount == Decimal("1470")
        ]
        assert post20


class TestBuildTrademarkFees:
    def test_yields_schedule(self, trademark_doc) -> None:
        fees = ipos._build_trademark_fees(trademark_doc)
        assert len(fees) >= 25

    def test_tm4_emits_both_pricing_tiers(self, trademark_doc) -> None:
        fees = ipos._build_trademark_fees(trademark_doc)
        preapproved = next(f for f in fees if f.code == "sg-tm-tm4-preapproved")
        custom = next(f for f in fees if f.code == "sg-tm-tm4-custom")
        # 2026-04-01 rates: pre-approved S$280 vs custom S$410.
        assert preapproved.amount == Decimal("280")
        assert custom.amount == Decimal("410")
        assert preapproved.category == FeeCategory.filing
        assert custom.category == FeeCategory.filing
        assert (
            preapproved.notes is not None
            and "pre-approved" in preapproved.notes.lower()
            or "fully adopted" in preapproved.notes.lower()
        )

    def test_tm4_carries_per_class_condition(self, trademark_doc) -> None:
        fees = ipos._build_trademark_fees(trademark_doc)
        preapproved = next(f for f in fees if f.code == "sg-tm-tm4-preapproved")
        assert preapproved.condition is not None
        assert preapproved.condition.trigger == ConditionalTrigger.classes_over

    def test_madrid_routing(self, trademark_doc) -> None:
        fees = ipos._build_trademark_fees(trademark_doc)
        madrid = [f for f in fees if f.category == FeeCategory.madrid]
        assert madrid

    def test_renewal_carries_year_10(self, trademark_doc) -> None:
        fees = ipos._build_trademark_fees(trademark_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert renewals
        assert all(f.year == 10 for f in renewals)

    def test_no_design_or_patent_codes_leak(self, trademark_doc) -> None:
        fees = ipos._build_trademark_fees(trademark_doc)
        for f in fees:
            assert f.code.startswith("sg-tm-")
            assert RightType.trademark in f.rights


class TestBuildDesignFees:
    def test_yields_schedule(self, design_doc) -> None:
        fees = ipos._build_design_fees(design_doc)
        assert len(fees) >= 20

    def test_d3_filing_fee(self, design_doc) -> None:
        fees = ipos._build_design_fees(design_doc)
        d3 = [f for f in fees if f.code.startswith("sg-des-d3-")]
        assert d3
        # First amount in D3 cell is S$200 per design.
        s200 = [f for f in d3 if f.amount == Decimal("200")]
        assert s200

    def test_d8_renewal_all_four_periods(self, design_doc) -> None:
        # D8 publishes (a)/(b)/(c)/(d) sub-rows for each 5-year period.
        # The walker's section_context propagation must carry the D8
        # "extension of period of registration" prefix into each
        # sub-row so they all classify as renewal.
        fees = ipos._build_design_fees(design_doc)
        d8_renewals = [
            f for f in fees if f.category == FeeCategory.renewal and f.code.startswith("sg-des-d8-")
        ]
        years = sorted({f.year for f in d8_renewals if f.year is not None})
        assert years == [10, 15, 20, 25]
        amounts = sorted(f.amount for f in d8_renewals)
        assert amounts == [Decimal("220"), Decimal("330"), Decimal("440"), Decimal("550")]


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape test (network call mocked)
# ──────────────────────────────────────────────────────────────────────


_FIXTURE_BY_RIGHT = {
    "patents": PATENT_FIXTURE,
    "trade-marks": TM_FIXTURE,
    "designs": DESIGN_FIXTURE,
}


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: ipos.IPOSFeesClient, right: str) -> str:
        return _FIXTURE_BY_RIGHT[right].read_text()

    monkeypatch.setattr(ipos.IPOSFeesClient, "fetch_html", fake_fetch)


@pytest.mark.asyncio
async def test_scrape_patents_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await ipos.scrape_ipos_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "SG"
    assert schedule.office_code == "IPOS"
    assert schedule.right == RightType.patent
    assert schedule.currency == "SGD"
    assert schedule.effective_date == ipos.IPOS_EFFECTIVE_DATE
    assert schedule.statutory_basis is not None
    assert "PA1994-R1" in schedule.statutory_basis
    assert len(schedule.fees) >= 80


@pytest.mark.asyncio
async def test_scrape_trademarks_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await ipos.scrape_ipos_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "SGD"
    assert "TMA1998-R1" in (schedule.statutory_basis or "")
    assert len(schedule.fees) >= 25


@pytest.mark.asyncio
async def test_scrape_designs_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await ipos.scrape_ipos_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "SGD"
    assert "RDA2000-R1" in (schedule.statutory_basis or "")
    assert len(schedule.fees) >= 20


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_registry_dispatches_all_three_sg_routes() -> None:
    from patent_client_agents.fees.registry import get_scraper

    p = get_scraper("IPOS", RightType.patent)
    tm = get_scraper("IPOS", RightType.trademark)
    d = get_scraper("IPOS", RightType.design)
    assert p is ipos.scrape_ipos_patents
    assert tm is ipos.scrape_ipos_trademarks
    assert d is ipos.scrape_ipos_designs
