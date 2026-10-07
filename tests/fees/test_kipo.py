"""Tests for the KIPO Korea fee scraper.

Two layers:

* **Unit tests** of helpers — amount extractor, electronic/paper
  splitter, section-to-category mappers, design annuity band parser.
* **Integration tests** that drive the per-right builders against
  the cached KIPO HTML fixture
  (``tests/fees/fixtures/kr_kipo_trademarks_designs_2026-05-20.html``).

Refresh the fixture by re-fetching:

    https://www.kipo.go.kr/en/HtmlApp?c=93006&catmenu=ek04_04_01
"""

from __future__ import annotations

import asyncio
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
from patent_client_agents.fees.scrapers import kipo

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TM_DES_FIXTURE = FIXTURE_DIR / "kr_kipo_trademarks_designs_2026-05-20.html"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestExtractAmounts:
    def test_single_amount(self) -> None:
        assert kipo._extract_amounts("52,000") == [Decimal("52000")]

    def test_newline_separated(self) -> None:
        assert kipo._extract_amounts("201,000\n2,000") == [
            Decimal("201000"),
            Decimal("2000"),
        ]

    def test_four_amounts(self) -> None:
        # Registration lump-sum + installment row carries four amounts.
        assert kipo._extract_amounts("201,000\n2,000\n122,000\n1,000") == [
            Decimal("201000"),
            Decimal("2000"),
            Decimal("122000"),
            Decimal("1000"),
        ]

    def test_ignores_inline_count(self) -> None:
        # "exceeding 10 designated goods" — the 10 is not a fee.
        assert kipo._extract_amounts("exceeding 10 designated goods") == []

    def test_empty(self) -> None:
        assert kipo._extract_amounts("") == []

    def test_skips_sub_thousand(self) -> None:
        # 200 KRW would never be a real KIPO fee — minimum is 1,000.
        assert kipo._extract_amounts("200") == []


class TestElectronicPaperAmounts:
    def test_paired(self) -> None:
        elec, paper = kipo._electronic_paper_amounts(
            "18,000(electronic application) 20,000(paper-based application)"
        )
        assert elec == Decimal("18000")
        assert paper == Decimal("20000")

    def test_paired_with_newlines(self) -> None:
        elec, paper = kipo._electronic_paper_amounts(
            "9,000(electronic application)\n 10,000(paper-based application)"
        )
        assert elec == Decimal("9000")
        assert paper == Decimal("10000")

    def test_no_label(self) -> None:
        assert kipo._electronic_paper_amounts("52,000") == (None, None)


class TestSectionToTmCategory:
    def test_application_filing(self) -> None:
        assert (
            kipo._section_to_tm_category(
                "Application Fee", "Trademark application fee for each class"
            )
            == FeeCategory.filing
        )

    def test_application_opposition(self) -> None:
        # The second "Application fee" section header in the KIPO
        # trademark table covers oppositions — must categorize as
        # opposition, not filing.
        assert (
            kipo._section_to_tm_category(
                "Application fee", "Filling an opposition to a registration"
            )
            == FeeCategory.opposition
        )

    def test_examination_preferential(self) -> None:
        assert (
            kipo._section_to_tm_category(
                "Examination Fee", "Request for a preferential examination"
            )
            == FeeCategory.petition
        )

    def test_registration_grant(self) -> None:
        assert (
            kipo._section_to_tm_category(
                "Registration Fee", "Registration for establishment of right"
            )
            == FeeCategory.grant
        )

    def test_registration_renewal(self) -> None:
        assert (
            kipo._section_to_tm_category("Registration Fee", "Renewal of registration")
            == FeeCategory.renewal
        )

    def test_registration_late_renewal(self) -> None:
        assert (
            kipo._section_to_tm_category("Registration Fee", "Late renewal of registration")
            == FeeCategory.late_fee
        )


class TestSectionToDesignCategory:
    def test_application_filing(self) -> None:
        assert (
            kipo._section_to_design_category(
                "Application Fee", "Request for a substantive examination"
            )
            == FeeCategory.filing
        )

    def test_examination_preferential(self) -> None:
        assert (
            kipo._section_to_design_category(
                "Examination Fee", "Request for a preferential examination"
            )
            == FeeCategory.petition
        )

    def test_annual_fee_renewal(self) -> None:
        assert (
            kipo._section_to_design_category("Annual Fee", "Substantive examination")
            == FeeCategory.renewal
        )

    def test_others_opposition(self) -> None:
        assert (
            kipo._section_to_design_category("Others", "Filling an opposition to a registration")
            == FeeCategory.opposition
        )


class TestDesignAnnuityBands:
    def test_five_band_substantive(self) -> None:
        bands = kipo._design_annuity_bands(
            "Substantive examination\n"
            "a. 1 to 3 years, annually, for each design\n"
            "b. 4 to 6 years, annually, for each design\n"
            "c. 7 to 9 years, annually, for each design\n"
            "d. 10 to 12 years, annually, for each design\n"
            "e. 13 to 20 years, annually, for each design"
        )
        assert bands == [(1, 3), (4, 6), (7, 9), (10, 12), (13, 20)]

    def test_two_band_partial(self) -> None:
        bands = kipo._design_annuity_bands(
            "Partial-substantive examination\n"
            "a. 1 to 3 years, annually, for each design\n"
            "b. 4 to 20 years, annually, for each design"
        )
        assert bands == [(1, 3), (4, 20)]

    def test_no_bands(self) -> None:
        assert kipo._design_annuity_bands("Request for a preferential examination") == []


# ──────────────────────────────────────────────────────────────────────
# Integration tests against the cached HTML fixture
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def tm_des_doc() -> L.HtmlElement:
    return L.fromstring(TM_DES_FIXTURE.read_bytes())


class TestBuildTrademarkFees:
    def test_yields_schedule(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        # 10 logical rows × multi-amount expansion → ~20+ FeeItems.
        assert len(fees) >= 20

    def test_application_fee_electronic(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        # 52,000 KRW per class (electronic).
        match = [
            f for f in fees if f.amount == Decimal("52000") and f.category == FeeCategory.filing
        ]
        assert match
        assert match[0].currency == "KRW"
        assert match[0].condition is not None
        assert match[0].condition.trigger == ConditionalTrigger.classes_over

    def test_renewal_carries_year_10(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert renewals
        assert all(f.year == 10 for f in renewals)
        # Renewal at 300,000 KRW (single lump sum) must be present.
        single_lump_sum = [f for f in renewals if f.amount == Decimal("300000")]
        assert single_lump_sum

    def test_renewal_two_installments_split(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        # Renewal as two installments = 184,000 KRW basic per class.
        two_installments = [
            f for f in fees if f.category == FeeCategory.renewal and f.amount == Decimal("184000")
        ]
        assert two_installments

    def test_late_renewal_at_330k(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        late = [
            f for f in fees if f.category == FeeCategory.late_fee and f.amount == Decimal("330000")
        ]
        assert late

    def test_excess_classes_surcharge_at_2000(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        # Per-goods surcharge over 10 per class — 2,000 KRW under
        # single lump sum, 1,000 KRW under two installments.
        excess = [f for f in fees if f.category == FeeCategory.excess_classes]
        assert excess
        # Check the FeeCondition is properly set.
        for fee in excess:
            assert fee.condition is not None
            assert fee.condition.trigger == ConditionalTrigger.classes_over
            assert fee.condition.threshold == 10
            assert fee.condition.per_unit is True

    def test_opposition_at_50k(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        opp = [
            f for f in fees if f.category == FeeCategory.opposition and f.amount == Decimal("50000")
        ]
        assert opp

    def test_no_design_codes_leak(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_trademark_fees(tm_des_doc)
        for f in fees:
            assert f.code.startswith("kr-tm-")
            assert RightType.trademark in f.rights
            assert f.tier == EntityTier.none


class TestBuildDesignFees:
    def test_yields_schedule(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        # 22 logical rows + 5-band × 20-year annuity expansion → 50+.
        assert len(fees) >= 50

    def test_substantive_examination_filing(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        # 94,000 KRW electronic application fee.
        filings = [
            f for f in fees if f.category == FeeCategory.filing and f.amount == Decimal("94000")
        ]
        assert filings

    def test_annuity_substantive_year_1_at_25k(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        # Year 1 of substantive examination annuity.
        y1 = [
            f
            for f in fees
            if f.category == FeeCategory.renewal and f.year == 1 and f.amount == Decimal("25000")
        ]
        assert y1

    def test_annuity_substantive_year_13_at_210k(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        # Year 13-20 band at 210,000 KRW.
        y13_20 = sorted(
            {
                f.year
                for f in fees
                if f.category == FeeCategory.renewal
                and f.amount == Decimal("210000")
                and f.year is not None
            }
        )
        assert y13_20 == [13, 14, 15, 16, 17, 18, 19, 20]

    def test_annuity_full_year_coverage(self, tm_des_doc: L.HtmlElement) -> None:
        # The substantive-examination annuity track should cover years 1-20.
        fees = kipo._build_design_fees(tm_des_doc)
        sub_years = sorted(
            {f.year for f in fees if f.code.startswith("kr-des-annuity-substantive-examination-y")}
        )
        assert sub_years == list(range(1, 21))

    def test_annuity_partial_substantive_track(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        partial = [
            f for f in fees if f.code.startswith("kr-des-annuity-partial-substantive-examinatio-y")
        ]
        # Years 1-3 at 25k, years 4-20 at 34k → 20 items total.
        assert len(partial) == 20
        y1_3 = [f for f in partial if f.year in (1, 2, 3)]
        assert all(f.amount == Decimal("25000") for f in y1_3)
        y4_20 = [f for f in partial if f.year is not None and 4 <= f.year <= 20]
        assert all(f.amount == Decimal("34000") for f in y4_20)

    def test_design_application_paper_variant(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        # Paper application fee 104,000 KRW.
        paper = [
            f for f in fees if f.category == FeeCategory.filing and f.amount == Decimal("104000")
        ]
        assert paper

    def test_opposition_at_50k(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        opp = [
            f for f in fees if f.category == FeeCategory.opposition and f.amount == Decimal("50000")
        ]
        assert opp

    def test_no_trademark_codes_leak(self, tm_des_doc: L.HtmlElement) -> None:
        fees = kipo._build_design_fees(tm_des_doc)
        for f in fees:
            assert f.code.startswith("kr-des-")
            assert RightType.design in f.rights
            assert f.tier == EntityTier.none


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape tests (network call mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_fetch_tm_des(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: kipo.KIPOFeesClient) -> str:
        return TM_DES_FIXTURE.read_text()

    monkeypatch.setattr(kipo.KIPOFeesClient, "fetch_tm_des_html", fake_fetch)


@pytest.mark.asyncio
async def test_kipo_trademarks_schedule_has_filing_and_renewal(
    patch_fetch_tm_des: None,
) -> None:
    """Required smoke test: trademark schedule covers filing + renewal."""
    schedule = await kipo.scrape_kipo_trademarks()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "KR"
    assert schedule.office_code == "KIPO"
    assert schedule.right == RightType.trademark
    assert schedule.currency == "KRW"
    assert schedule.effective_date == kipo.KIPO_EFFECTIVE_DATE
    assert schedule.source_url == kipo.KIPO_TM_DES_FEES_URL
    assert schedule.statutory_basis is not None
    assert "Trademark" in schedule.statutory_basis

    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats
    # Excess-classes surcharge for goods beyond 10 per class.
    assert FeeCategory.excess_classes in cats


@pytest.mark.asyncio
async def test_kipo_designs_schedule_has_filing_and_registration(
    patch_fetch_tm_des: None,
) -> None:
    """Required smoke test: design schedule covers filing + registration (annuity)."""
    schedule = await kipo.scrape_kipo_designs()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "KR"
    assert schedule.office_code == "KIPO"
    assert schedule.right == RightType.design
    assert schedule.currency == "KRW"
    assert schedule.effective_date == kipo.KIPO_EFFECTIVE_DATE
    assert schedule.source_url == kipo.KIPO_TM_DES_FEES_URL
    assert schedule.statutory_basis is not None
    assert "Design" in schedule.statutory_basis

    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    # KIPO bundles registration (grant) into the annuity year-1 amount —
    # so "registration" is represented as the year-1 renewal entry.
    assert FeeCategory.renewal in cats
    # Verify at least one year-1 annuity is present.
    y1 = [f for f in schedule.fees if f.category == FeeCategory.renewal and f.year == 1]
    assert y1


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_registry_dispatches_all_three_kr_routes() -> None:
    from patent_client_agents.fees.registry import get_scraper

    p = get_scraper("KIPO", RightType.patent)
    tm = get_scraper("KIPO", RightType.trademark)
    d = get_scraper("KIPO", RightType.design)
    assert p is kipo.scrape_kipo_patents
    assert tm is kipo.scrape_kipo_trademarks
    assert d is kipo.scrape_kipo_designs


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", ["fetch_html", "fetch_tm_des_html"])
async def test_live_fetch_has_total_deadline(
    monkeypatch: pytest.MonkeyPatch, method_name: str
) -> None:
    async def never_connects(self: kipo.KIPOFeesClient, *args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(kipo, "KIPO_REQUEST_DEADLINE_SECONDS", 0.01, raising=False)
    monkeypatch.setattr(kipo.KIPOFeesClient, "_request", never_connects)

    async with kipo.KIPOFeesClient(use_cache=False) as client:
        with pytest.raises(TimeoutError, match="KIPO fee page request exceeded"):
            await asyncio.wait_for(getattr(client, method_name)(), timeout=0.2)
