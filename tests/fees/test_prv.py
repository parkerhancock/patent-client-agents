"""Tests for the PRV Sweden fee scraper.

Two layers:

* **Unit tests** of helpers — SEK amount parser (Swedish space-thousands
  convention with ``kr`` / ``SEK`` suffixes), zero-detection, formula
  detection, per-class/per-claim condition detection, categorizers.
* **Integration tests** that drive the per-right builders against the
  cached PRV HTML pages
  (``tests/fees/fixtures/se_prv_{patents,trademarks,designs}_2026-05-20.html``)
  so the schedule shape is exercised without a network call.

Refresh the fixtures by re-fetching:

    https://www.prv.se/en/patents/the-advanced-patent-guide/fees-and-payment/
    https://www.prv.se/en/trademarks/prepare-for-the-trademark-application/fees-and-payment/
    https://www.prv.se/en/designs/prepare-for-the-design-application/fees-for-designs/
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from lxml import html as L

from patent_client_agents.fees.models import (
    ConditionalTrigger,
    EntityTier,
    FeeCategory,
    FeeSchedule,
    RightType,
)
from patent_client_agents.fees.scrapers import prv_se as prv

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PATENT_FIXTURE = FIXTURE_DIR / "se_prv_patents_2026-05-20.html"
TM_FIXTURE = FIXTURE_DIR / "se_prv_trademarks_2026-05-20.html"
DESIGN_FIXTURE = FIXTURE_DIR / "se_prv_designs_2026-05-20.html"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseSekAmounts:
    """Swedish convention: '3 000 kr' = 3000; '2 700 SEK' = 2700."""

    def test_kr_with_space_thousands(self) -> None:
        assert prv._parse_sek_amounts("3 000 kr") == [Decimal("3000")]

    def test_sek_with_space_thousands(self) -> None:
        assert prv._parse_sek_amounts("2 700 SEK") == [Decimal("2700")]

    def test_small_amount_no_separator(self) -> None:
        assert prv._parse_sek_amounts("150 kr") == [Decimal("150")]

    def test_zero(self) -> None:
        assert prv._parse_sek_amounts("0 kr") == [Decimal("0")]

    def test_non_breaking_space_separator(self) -> None:
        # PRV occasionally uses non-breaking spaces (U+00A0).
        assert prv._parse_sek_amounts("3 000 kr") == [Decimal("3000")]

    def test_five_digit_amount(self) -> None:
        # PCT-1: "15 680 kr"
        assert prv._parse_sek_amounts("15 680 kr") == [Decimal("15680")]
        # NT-2: "20 000 kr"
        assert prv._parse_sek_amounts("20 000 kr") == [Decimal("20000")]

    def test_empty(self) -> None:
        assert prv._parse_sek_amounts("") == []

    def test_per_sheet_suffix(self) -> None:
        # PCT-2: "180 kr per sheet"
        amounts = prv._parse_sek_amounts("180 kr per sheet")
        assert amounts == [Decimal("180")]

    def test_per_hour_suffix(self) -> None:
        assert prv._parse_sek_amounts("1 700 kr per hour") == [Decimal("1700")]

    def test_no_amount(self) -> None:
        assert prv._parse_sek_amounts("By quotation") == []
        assert prv._parse_sek_amounts("As described") == []


class TestIsZeroExplicit:
    def test_zero_kr(self) -> None:
        assert prv._is_zero_explicit("0 kr")

    def test_zero_sek(self) -> None:
        assert prv._is_zero_explicit("0 SEK")

    def test_not_zero_when_amount_present(self) -> None:
        assert not prv._is_zero_explicit("3 000 kr")

    def test_not_zero_when_empty(self) -> None:
        assert not prv._is_zero_explicit("")


class TestLooksLikeFormula:
    def test_as_described(self) -> None:
        assert prv._looks_like_formula("As described")

    def test_50_percent_addition(self) -> None:
        assert prv._looks_like_formula("50% addition")

    def test_by_quotation(self) -> None:
        assert prv._looks_like_formula("By quotation")

    def test_normal_amount_is_not_formula(self) -> None:
        assert not prv._looks_like_formula("3 000 kr")


class TestPatentIdPrefix:
    def test_se(self) -> None:
        assert prv._patent_id_prefix("SE-1") == "SE"

    def test_n(self) -> None:
        assert prv._patent_id_prefix("N-3") == "N"

    def test_pct(self) -> None:
        assert prv._patent_id_prefix("PCT-15") == "PCT"

    def test_invalid(self) -> None:
        assert prv._patent_id_prefix("not-a-code") is None


class TestPatentAnnuityYear:
    def test_3rd_year(self) -> None:
        assert prv._patent_annuity_year("3rd annual fee") == 3

    def test_20th_year(self) -> None:
        assert prv._patent_annuity_year("20th annual fee") == 20

    def test_1st_year_with_due_note(self) -> None:
        assert prv._patent_annuity_year("1st annual fee (due together with 3rd annual fee)") == 1

    def test_no_year(self) -> None:
        assert prv._patent_annuity_year("Fee for grant") is None


class TestPatentCategorizer:
    def test_se1_filing(self) -> None:
        assert prv._categorize_patent("SE-1", "Filing fee") == FeeCategory.filing

    def test_se8_grant(self) -> None:
        assert (
            prv._categorize_patent("SE-8", "Fee for grant: Basic fee for publication")
            == FeeCategory.grant
        )

    def test_se3_excess_claims(self) -> None:
        assert (
            prv._categorize_patent(
                "SE-3", "Additional fee for each patent claim beyond the first ten"
            )
            == FeeCategory.excess_claims
        )

    def test_n3_renewal(self) -> None:
        assert prv._categorize_patent("N-3", "3rd annual fee") == FeeCategory.renewal

    def test_npb1_cancellation(self) -> None:
        assert (
            prv._categorize_patent(
                "NPB-1", "Fee for request for patent limitation or revocation of a patent"
            )
            == FeeCategory.cancellation
        )

    def test_nt2_renewal(self) -> None:
        # SPC annual fee is a renewal.
        assert (
            prv._categorize_patent(
                "NT-2", "Annual fee for supplementary protection certificate (SPC)"
            )
            == FeeCategory.renewal
        )

    def test_pct1_filing(self) -> None:
        assert prv._categorize_patent("PCT-1", "International filing fee") == FeeCategory.filing

    def test_pct2_excess_pages(self) -> None:
        assert (
            prv._categorize_patent("PCT-2", "Additional fee for each additional sheet.")
            == FeeCategory.excess_pages
        )

    def test_pct11_late_fee(self) -> None:
        assert prv._categorize_patent("PCT-11", "Late payment fee") == FeeCategory.late_fee

    def test_kt1_search(self) -> None:
        assert prv._categorize_patent("KT-1", "Novelty search") == FeeCategory.search


class TestPatentCondition:
    def test_se3_claims_over_10(self) -> None:
        cond = prv._patent_condition(
            "SE-3", "Additional fee for each patent claim beyond the first ten"
        )
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.claims_over
        assert cond.threshold == 10
        assert cond.per_unit is True

    def test_pct2_pages_over_30(self) -> None:
        cond = prv._patent_condition("PCT-2", "Additional fee for each additional sheet.")
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.pages_over
        assert cond.threshold == 30
        assert cond.per_unit is True

    def test_none_for_plain_row(self) -> None:
        assert prv._patent_condition("SE-1", "Filing fee") is None


class TestPerClassCondition:
    def test_each_additional_class(self) -> None:
        cond = prv._per_class_condition("For each additional class")
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.classes_over
        assert cond.threshold == 1

    def test_no_per_class(self) -> None:
        assert prv._per_class_condition("Application for registration of a trademark") is None


class TestTrademarkCategorizer:
    def test_application(self) -> None:
        assert (
            prv._categorize_trademark(
                "Application for registration of a trademark for protection in one class",
                "Fees for Swedish trademark application",
            )
            == FeeCategory.filing
        )

    def test_each_additional_class(self) -> None:
        assert (
            prv._categorize_trademark(
                "For each additional class", "Fees for Swedish trademark application"
            )
            == FeeCategory.excess_classes
        )

    def test_renewal(self) -> None:
        assert (
            prv._categorize_trademark(
                "Renewal application for protection in one class",
                "Fees for changing, renewing and reinstatement a Swedish trademark",
            )
            == FeeCategory.renewal
        )

    def test_late_renewal_increased_fee(self) -> None:
        assert (
            prv._categorize_trademark(
                "Increased fee for each class due to late renewal application",
                "Fees for changing, renewing and reinstatement a Swedish trademark",
            )
            == FeeCategory.late_fee
        )

    def test_international_registration(self) -> None:
        assert (
            prv._categorize_trademark(
                "Application for international registration for protection in a class of trademark",
                "Fees for international trademark protection",
            )
            == FeeCategory.madrid
        )


class TestDesignCategorizer:
    def test_filing_electronic(self) -> None:
        assert (
            prv._categorize_design(
                "Filing fee for registration of 1 design using our electronic services. One five-year period.",
                "Application fees for design registration in Sweden",
            )
            == FeeCategory.filing
        )

    def test_renewal(self) -> None:
        assert (
            prv._categorize_design(
                "Renewal fee for a registered design using our electronic services.",
                "Renewal fees",
            )
            == FeeCategory.renewal
        )

    def test_class_fee_additional_class(self) -> None:
        # Direct call: this label triggers the class-fee branch in
        # _categorize_design; the surcharge condition is layered in by
        # the builder.
        assert (
            prv._categorize_design(
                "Class fee for each additional class a design or several designs from a multiple registration are classified in.",
                "Additional fees",
            )
            == FeeCategory.excess_classes
        )

    def test_announcement_fee(self) -> None:
        assert (
            prv._categorize_design(
                "Announcement fee for each image in addition to the first.",
                "Additional fees",
            )
            == FeeCategory.publication
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
    def test_yields_substantial_schedule(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        # ~98 unique rows + ~18 annuity "Increased fee" siblings → ~100+.
        assert len(fees) >= 80

    def test_se1_filing_fee(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        se1 = next(f for f in fees if f.code.startswith("se-pat-se-1"))
        assert se1.amount == Decimal("3000")
        assert se1.category == FeeCategory.filing
        assert se1.currency == "SEK"
        assert se1.tier == EntityTier.none

    def test_se3_excess_claims_with_condition(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        se3 = next(f for f in fees if f.code.startswith("se-pat-se-3"))
        assert se3.amount == Decimal("150")
        assert se3.category == FeeCategory.excess_claims
        assert se3.condition is not None
        assert se3.condition.trigger == ConditionalTrigger.claims_over
        assert se3.condition.threshold == 10
        assert se3.condition.per_unit is True

    def test_se8_grant_fee(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        se8 = next(f for f in fees if f.code.startswith("se-pat-se-8"))
        assert se8.amount == Decimal("3000")
        assert se8.category == FeeCategory.grant

    def test_n3_annuity_year_3(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        # N-3: 3rd annual fee, regular = 1600 kr, increased = 1920 kr
        n3 = next(f for f in fees if f.code == "se-pat-n-3" and f.category == FeeCategory.renewal)
        assert n3.amount == Decimal("1600")
        assert n3.year == 3

    def test_n3_increased_late_fee(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        inc = next(f for f in fees if f.code == "se-pat-n-3-increased")
        assert inc.amount == Decimal("1920")
        assert inc.category == FeeCategory.late_fee
        assert inc.year == 3

    def test_n20_annuity_year_20(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        n20 = next(f for f in fees if f.code == "se-pat-n-20" and f.category == FeeCategory.renewal)
        assert n20.amount == Decimal("8000")
        assert n20.year == 20

    def test_first_two_annuities_are_zero(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        n1 = next(f for f in fees if f.code == "se-pat-n-1")
        n2 = next(f for f in fees if f.code == "se-pat-n-2")
        # Years 1 + 2 are due together with year 3 — published as 0 kr.
        assert n1.amount == Decimal("0")
        assert n2.amount == Decimal("0")
        assert n1.year == 1
        assert n2.year == 2
        assert n1.category == FeeCategory.renewal

    def test_pct1_filing(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        pct1 = next(
            f for f in fees if f.code.startswith("se-pat-pct-1") and "se-pat-pct-1" == f.code
        )
        assert pct1.amount == Decimal("15680")
        assert pct1.category == FeeCategory.filing

    def test_pct2_excess_pages_with_condition(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        pct2 = next(f for f in fees if f.code == "se-pat-pct-2")
        assert pct2.amount == Decimal("180")
        assert pct2.category == FeeCategory.excess_pages
        assert pct2.condition is not None
        assert pct2.condition.trigger == ConditionalTrigger.pages_over
        assert pct2.condition.threshold == 30

    def test_all_fees_are_patent_and_sek(self, patent_doc: L.HtmlElement) -> None:
        fees = prv._build_patent_fees(patent_doc)
        for f in fees:
            assert RightType.patent in f.rights
            assert f.currency == "SEK"
            assert f.tier == EntityTier.none

    def test_renewal_rows_have_year(self, patent_doc: L.HtmlElement) -> None:
        # Pydantic validator requires renewal/maintenance rows to have year.
        fees = prv._build_patent_fees(patent_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        for r in renewals:
            assert r.year is not None and r.year >= 1


class TestBuildTrademarkFees:
    def test_yields_schedule(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        # ~30 rows across application, renewal, other, international.
        assert len(fees) >= 20

    def test_application_e_service_rate(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        # First table under "Fees for Swedish trademark application" is e-service.
        e_service = [
            f
            for f in fees
            if f.category == FeeCategory.filing
            and f.amount == Decimal("2700")
            and "e-service" in (f.notes or "").lower()
        ]
        assert e_service

    def test_application_paper_rate(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        # Second table under "Fees for Swedish trademark application" is paper.
        paper = [
            f
            for f in fees
            if f.category == FeeCategory.filing
            and f.amount == Decimal("3900")
            and "paper" in (f.notes or "").lower()
        ]
        assert paper

    def test_renewal_e_service_at_2700(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert renewals
        # All renewals should carry year=10.
        for r in renewals:
            assert r.year == 10
        # At least one e-service renewal at 2700.
        e_service = [r for r in renewals if r.amount == Decimal("2700")]
        assert e_service

    def test_each_additional_class_emits_excess_classes(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        excess = [
            f
            for f in fees
            if f.category == FeeCategory.excess_classes and f.amount == Decimal("1000")
        ]
        assert excess
        for e in excess:
            assert e.condition is not None
            assert e.condition.trigger == ConditionalTrigger.classes_over
            assert e.condition.threshold == 1

    def test_madrid_routing(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        madrid = [f for f in fees if f.category == FeeCategory.madrid]
        assert madrid

    def test_all_fees_are_trademark_and_sek(self, trademark_doc: L.HtmlElement) -> None:
        fees = prv._build_trademark_fees(trademark_doc)
        for f in fees:
            assert RightType.trademark in f.rights
            assert f.currency == "SEK"
            assert f.tier == EntityTier.none


class TestBuildDesignFees:
    def test_yields_schedule(self, design_doc: L.HtmlElement) -> None:
        fees = prv._build_design_fees(design_doc)
        # ~18 rows: filing + additional fees + renewal + ownership + cert + community.
        assert len(fees) >= 12

    def test_filing_e_service_at_2000(self, design_doc: L.HtmlElement) -> None:
        fees = prv._build_design_fees(design_doc)
        filings_e = [
            f for f in fees if f.category == FeeCategory.filing and f.amount == Decimal("2000")
        ]
        assert filings_e

    def test_filing_paper_at_2500(self, design_doc: L.HtmlElement) -> None:
        fees = prv._build_design_fees(design_doc)
        filings_p = [
            f for f in fees if f.category == FeeCategory.filing and f.amount == Decimal("2500")
        ]
        assert filings_p

    def test_renewal_e_service_at_2500(self, design_doc: L.HtmlElement) -> None:
        fees = prv._build_design_fees(design_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert renewals
        # All renewals carry year=10 sentinel.
        for r in renewals:
            assert r.year == 10
        e_service = [r for r in renewals if r.amount == Decimal("2500")]
        assert e_service

    def test_class_fee_emits_excess_classes(self, design_doc: L.HtmlElement) -> None:
        fees = prv._build_design_fees(design_doc)
        excess = [f for f in fees if f.category == FeeCategory.excess_classes]
        assert excess
        for e in excess:
            assert e.condition is not None
            assert e.condition.trigger == ConditionalTrigger.classes_over

    def test_all_fees_are_design_and_sek(self, design_doc: L.HtmlElement) -> None:
        fees = prv._build_design_fees(design_doc)
        for f in fees:
            assert RightType.design in f.rights
            assert f.currency == "SEK"
            assert f.tier == EntityTier.none


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape tests (network call mocked)
# ──────────────────────────────────────────────────────────────────────


_FIXTURE_BY_RIGHT = {
    "patents": PATENT_FIXTURE,
    "trademarks": TM_FIXTURE,
    "designs": DESIGN_FIXTURE,
}


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: prv.PrvFeesClient, right: str) -> str:
        return _FIXTURE_BY_RIGHT[right].read_text()

    monkeypatch.setattr(prv.PrvFeesClient, "fetch_html", fake_fetch)


@pytest.mark.asyncio
async def test_prv_patents_schedule_has_filing_renewal(patch_fetch: None) -> None:
    schedule = await prv.scrape_prv_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "SE"
    assert schedule.office_code == "PRV"
    assert schedule.right == RightType.patent
    assert schedule.currency == "SEK"
    assert schedule.effective_date == prv.PRV_PATENTS_EFFECTIVE_DATE
    assert "Patentlagen" in (schedule.statutory_basis or "")
    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats
    assert FeeCategory.grant in cats
    assert FeeCategory.excess_claims in cats


@pytest.mark.asyncio
async def test_prv_trademarks_schedule_has_filing_renewal(patch_fetch: None) -> None:
    schedule = await prv.scrape_prv_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "SEK"
    assert schedule.effective_date == prv.PRV_TRADEMARKS_EFFECTIVE_DATE
    assert "Varumärkeslagen" in (schedule.statutory_basis or "")
    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats
    assert FeeCategory.excess_classes in cats


@pytest.mark.asyncio
async def test_prv_designs_schedule_has_filing_renewal(patch_fetch: None) -> None:
    schedule = await prv.scrape_prv_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "SEK"
    assert schedule.effective_date == prv.PRV_DESIGNS_EFFECTIVE_DATE
    assert "Mönsterskyddslagen" in (schedule.statutory_basis or "")
    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_prv_all_routes_registered_in_registry() -> None:
    from patent_client_agents.fees.registry import OFFICES, get_scraper

    p = get_scraper("PRV", RightType.patent)
    tm = get_scraper("PRV", RightType.trademark)
    d = get_scraper("PRV", RightType.design)
    assert p is prv.scrape_prv_patents
    assert tm is prv.scrape_prv_trademarks
    assert d is prv.scrape_prv_designs
    assert "PRV" in OFFICES
