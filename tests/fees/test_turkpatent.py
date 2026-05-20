"""Tests for the TÜRKPATENT Turkey fee scraper.

Two layers:

* **Unit tests** of helpers — amount parser (TR thousands-then-decimal
  convention), formula detection, year extraction, per-class
  threshold detection, design multi-amount body parser.
* **Integration tests** that drive the per-right builders against
  the cached TÜRKPATENT HTML pages
  (``tests/fees/fixtures/tr_turkpatent_{patents,trademarks,designs}_2026-05-19.html``)
  so the schedule shape is exercised without a network call.

Refresh the fixtures by re-fetching:

    https://www.turkpatent.gov.tr/patent-islem-ucretleri
    https://www.turkpatent.gov.tr/marka-islem-ucretleri
    https://www.turkpatent.gov.tr/tasarim-islem-ucretleri
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
from patent_client_agents.fees.scrapers import turkpatent as tr

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PATENT_FIXTURE = FIXTURE_DIR / "tr_turkpatent_patents_2026-05-19.html"
TM_FIXTURE = FIXTURE_DIR / "tr_turkpatent_trademarks_2026-05-19.html"
DESIGN_FIXTURE = FIXTURE_DIR / "tr_turkpatent_designs_2026-05-19.html"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseTrAmount:
    """Turkish/EU number convention: ``2.402,67`` = 2402.67."""

    def test_thousands_separator_then_decimal(self) -> None:
        assert tr._parse_tr_amount("2.402,67") == Decimal("2402.67")

    def test_no_thousands_separator_decimal(self) -> None:
        # The bug fix that made this test exist: "1674,90" was being
        # truncated to "167" because the first regex branch would match
        # the 3-digit cap without backtracking to the no-separator
        # alternative.
        assert tr._parse_tr_amount("1674,90") == Decimal("1674.90")

    def test_no_separators_at_all(self) -> None:
        # Patent rows for 01.01.03/04 publish "9000" / "10800" without
        # any thousands separator at all.
        assert tr._parse_tr_amount("3800") == Decimal("3800")
        assert tr._parse_tr_amount("9000") == Decimal("9000")
        assert tr._parse_tr_amount("10800") == Decimal("10800")
        assert tr._parse_tr_amount("26650") == Decimal("26650")

    def test_decimal_only_no_thousands(self) -> None:
        assert tr._parse_tr_amount("2636,8") == Decimal("2636.8")
        assert tr._parse_tr_amount("81,42") == Decimal("81.42")

    def test_with_tl_suffix(self) -> None:
        assert tr._parse_tr_amount("1674,90TL") == Decimal("1674.90")
        assert tr._parse_tr_amount("318,70 TL") == Decimal("318.70")

    def test_empty_returns_none(self) -> None:
        assert tr._parse_tr_amount("") is None

    def test_garbage_returns_none(self) -> None:
        assert tr._parse_tr_amount("not-an-amount") is None


class TestFormulaDetection:
    def test_yillik_ucret_formula(self) -> None:
        assert tr._looks_like_formula(
            "Ödenmesi gereken yıllık ücret + (Ödenmesi gereken yıllık ücret - harç)ın %50'si"
        )

    def test_kati_formula(self) -> None:
        assert tr._looks_like_formula("Ödenmesi gereken ücretin 1,5 katı")

    def test_plain_amount_is_not_formula(self) -> None:
        assert not tr._looks_like_formula("3800")
        assert not tr._looks_like_formula("2.402,67")

    def test_chf_row_detected(self) -> None:
        assert tr._is_chf_row("30 CHF")


class TestPatentAnnuityYear:
    def test_year_3(self) -> None:
        assert tr._patent_annuity_year("3.Yıl Sicil Kayıt Ücreti") == 3

    def test_year_20(self) -> None:
        assert tr._patent_annuity_year("20.Yıl Sicil Kayıt Ücreti") == 20

    def test_year_with_space(self) -> None:
        assert tr._patent_annuity_year("4. Yıl Sicil Kayıt Ücreti") == 4

    def test_non_annuity_returns_none(self) -> None:
        assert tr._patent_annuity_year("Patent Başvuru Ücreti") is None


class TestTmExcessClassThreshold:
    def test_2nd_class_row(self) -> None:
        # "Marka Başvurusu Ek Sınıf Ücreti (2.sınıf)" — threshold=1
        # (the fee kicks in starting at the 2nd class).
        assert tr._tm_excess_class_threshold(
            "Marka Başvurusu Ek Sınıf Ücreti (2.sınıf)"
        ) == 1

    def test_3rd_class_row(self) -> None:
        assert tr._tm_excess_class_threshold(
            "Marka Başvurusu Ek Sınıf Ücreti (3 üncü sınıf ve sonraki her bir sınıf için)"
        ) == 2

    def test_ilave_her_bir_row(self) -> None:
        # Threshold detection routes through the "3 üncü" substring in
        # the parenthetical — the bare "İlave Her bir Sınıf" prefix
        # alone is insufficient because Python's locale-independent
        # lower() on "İ" produces "i̇" (i + combining dot), which
        # doesn't match a plain-ASCII "i" pattern. The real-world TM
        # row 02.01.32 always carries the "3 üncü" qualifier, so the
        # detection still works in practice.
        assert tr._tm_excess_class_threshold(
            "İlave Her bir Sınıf İçin Marka Yenileme Ücreti (3 üncü ve sonraki herbir sınıf için)"
        ) == 2

    def test_non_class_row_returns_none(self) -> None:
        assert tr._tm_excess_class_threshold("Tek Sınıflı Marka Başvuru Ücreti") is None


class TestDesignMultiBody:
    """The 04.01.02 row publishes three sub-amounts in a prose body."""

    def test_parses_all_three_tiers(self) -> None:
        body = (
            "Başvurudaki 2. tasarım için tasarım başvuru ücreti: 1674,90TL"
            "Başvurudaki 3. 4. ve 5. her bir tasarım için tasarım başvuru ücreti: 318,70 TL"
            "Başvurudaki 6. ve fazlası her bir tasarım için tasarım başvuru ücreti: 760,00 TL"
        )
        result = tr._parse_design_multi_body(body)
        suffixes = {s for s, _ in result}
        assert "d2" in suffixes
        assert "d3to5" in suffixes
        assert "d6plus" in suffixes

    def test_amounts_correct(self) -> None:
        body = (
            "Başvurudaki 2. tasarım için tasarım başvuru ücreti: 1674,90TL"
            "Başvurudaki 3. 4. ve 5. her bir tasarım için tasarım başvuru ücreti: 318,70 TL"
            "Başvurudaki 6. ve fazlası her bir tasarım için tasarım başvuru ücreti: 760,00 TL"
        )
        by_suffix = dict(tr._parse_design_multi_body(body))
        assert by_suffix["d2"] == Decimal("1674.90")
        assert by_suffix["d3to5"] == Decimal("318.70")
        assert by_suffix["d6plus"] == Decimal("760.00")

    def test_empty_body_returns_empty(self) -> None:
        assert tr._parse_design_multi_body("") == []


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
    def test_yields_full_schedule(self, patent_doc: L.HtmlElement) -> None:
        fees = tr._build_patent_fees(patent_doc)
        # 57 source rows minus header / CHF row → ~55 FeeItems.
        assert 50 <= len(fees) <= 60

    def test_filing_fee_uses_toplam_tutar(self, patent_doc: L.HtmlElement) -> None:
        # 01.01.01 Patent Başvuru Ücreti: ÜCRET 81,42 + KDV 16,28 +
        # HARÇ 522,3 = TOPLAM 620 — the FeeItem amount must be 620
        # (the all-in number), not the base ÜCRET.
        fees = tr._build_patent_fees(patent_doc)
        filing = next(f for f in fees if f.code == "tr-pat-01.01.01")
        assert filing.amount == Decimal("620")
        assert filing.category == FeeCategory.filing
        assert filing.notes is not None
        assert "base TRY 81.42" in filing.notes
        assert "stamp TRY 522.3" in filing.notes

    def test_year_3_annuity(self, patent_doc: L.HtmlElement) -> None:
        # 01.01.23 3.Yıl Sicil Kayıt Ücreti TOPLAM 3800.
        fees = tr._build_patent_fees(patent_doc)
        y3 = next(f for f in fees if f.code == "tr-pat-01.01.23")
        assert y3.category == FeeCategory.renewal
        assert y3.year == 3
        assert y3.amount == Decimal("3800")

    def test_year_20_annuity(self, patent_doc: L.HtmlElement) -> None:
        fees = tr._build_patent_fees(patent_doc)
        y20 = next(f for f in fees if f.code == "tr-pat-01.01.40")
        assert y20.category == FeeCategory.renewal
        assert y20.year == 20
        assert y20.amount == Decimal("26650")

    def test_all_annuity_years_3_to_20(self, patent_doc: L.HtmlElement) -> None:
        fees = tr._build_patent_fees(patent_doc)
        annuity_years = sorted(
            f.year for f in fees if f.category == FeeCategory.renewal and f.year is not None
        )
        assert annuity_years == list(range(3, 21))  # years 3-20 inclusive

    def test_force_majeure_formula_row(self, patent_doc: L.HtmlElement) -> None:
        # 01.01.20 Mücbir Sebep — formula row, amount=0, formula in notes.
        fees = tr._build_patent_fees(patent_doc)
        force_majeure = next(f for f in fees if f.code == "tr-pat-01.01.20")
        assert force_majeure.category == FeeCategory.late_fee
        assert force_majeure.amount == Decimal("0")
        assert force_majeure.notes is not None
        assert "Formula:" in force_majeure.notes
        assert "yıllık ücret" in force_majeure.notes

    def test_compensation_formula_row(self, patent_doc: L.HtmlElement) -> None:
        # 01.01.59 Yıllık Ücret İçin Telafi Ücreti — "Ödenmesi gereken
        # ücretin 1,5 katı" formula.
        fees = tr._build_patent_fees(patent_doc)
        comp = next(f for f in fees if f.code == "tr-pat-01.01.59")
        assert comp.category == FeeCategory.late_fee
        assert comp.amount == Decimal("0")
        assert comp.notes is not None
        assert "1,5 katı" in comp.notes

    def test_chf_row_skipped(self, patent_doc: L.HtmlElement) -> None:
        # 01.01.43 publishes "30 CHF" — multi-currency not supported in
        # the FeeItem model, so the row is skipped in v1.
        fees = tr._build_patent_fees(patent_doc)
        chf = [f for f in fees if f.code == "tr-pat-01.01.43"]
        assert chf == []

    def test_research_report_categorized_as_search(self, patent_doc: L.HtmlElement) -> None:
        # 01.01.48 + 01.01.49 + 01.01.64 + 01.01.65 — research report
        # fees → FeeCategory.search.
        fees = tr._build_patent_fees(patent_doc)
        search_rows = [f for f in fees if f.category == FeeCategory.search]
        assert len(search_rows) >= 4


class TestBuildTrademarkFees:
    def test_yields_schedule(self, trademark_doc: L.HtmlElement) -> None:
        fees = tr._build_trademark_fees(trademark_doc)
        assert len(fees) >= 25

    def test_first_class_filing_fee(self, trademark_doc: L.HtmlElement) -> None:
        # 02.01.01 Tek Sınıflı Marka Başvuru Ücreti: 2.820,00.
        fees = tr._build_trademark_fees(trademark_doc)
        filing = next(f for f in fees if f.code == "tr-tm-02.01.01")
        assert filing.category == FeeCategory.filing
        assert filing.amount == Decimal("2820.00")

    def test_2nd_class_surcharge(self, trademark_doc: L.HtmlElement) -> None:
        # 02.01.02 Ek Sınıf (2.sınıf): 2.820,00 — categorized as
        # excess_classes with threshold=1.
        fees = tr._build_trademark_fees(trademark_doc)
        ek = next(f for f in fees if f.code == "tr-tm-02.01.02")
        assert ek.category == FeeCategory.excess_classes
        assert ek.amount == Decimal("2820.00")
        assert ek.condition is not None
        assert ek.condition.trigger == ConditionalTrigger.classes_over
        assert ek.condition.threshold == 1
        assert ek.condition.per_unit is True

    def test_3rd_plus_class_surcharge(self, trademark_doc: L.HtmlElement) -> None:
        fees = tr._build_trademark_fees(trademark_doc)
        third = next(f for f in fees if f.code == "tr-tm-02.01.28")
        assert third.category == FeeCategory.excess_classes
        assert third.condition is not None
        assert third.condition.threshold == 2

    def test_renewal_carries_year_10(self, trademark_doc: L.HtmlElement) -> None:
        # 02.01.23 Marka Yenileme Ücreti (2 sınıfa kadar): 8.730,00.
        # TR TM term is 10 years (Law 6769 Art. 23).
        fees = tr._build_trademark_fees(trademark_doc)
        renewal = next(f for f in fees if f.code == "tr-tm-02.01.23")
        assert renewal.category == FeeCategory.renewal
        assert renewal.year == 10
        assert renewal.amount == Decimal("8730.00")


class TestBuildDesignFees:
    def test_yields_schedule(self, design_doc: L.HtmlElement) -> None:
        fees = tr._build_design_fees(design_doc)
        # 17 source rows; 04.01.02 expands to 3 sub-rows → ~19 FeeItems.
        assert len(fees) >= 18

    def test_filing_fee(self, design_doc: L.HtmlElement) -> None:
        fees = tr._build_design_fees(design_doc)
        filing = next(f for f in fees if f.code == "tr-des-04.01.01")
        assert filing.category == FeeCategory.filing
        assert filing.amount == Decimal("2070.00")

    def test_multi_design_d2_tier(self, design_doc: L.HtmlElement) -> None:
        fees = tr._build_design_fees(design_doc)
        d2 = next(f for f in fees if f.code == "tr-des-04.01.02-d2")
        assert d2.category == FeeCategory.filing
        assert d2.amount == Decimal("1674.90")

    def test_multi_design_d3to5_tier(self, design_doc: L.HtmlElement) -> None:
        fees = tr._build_design_fees(design_doc)
        d3to5 = next(f for f in fees if f.code == "tr-des-04.01.02-d3to5")
        assert d3to5.amount == Decimal("318.70")

    def test_multi_design_d6plus_tier(self, design_doc: L.HtmlElement) -> None:
        fees = tr._build_design_fees(design_doc)
        d6plus = next(f for f in fees if f.code == "tr-des-04.01.02-d6plus")
        assert d6plus.amount == Decimal("760.00")

    def test_renewal_carries_year_10(self, design_doc: L.HtmlElement) -> None:
        fees = tr._build_design_fees(design_doc)
        renewal = next(f for f in fees if f.code == "tr-des-04.01.05")
        assert renewal.category == FeeCategory.renewal
        assert renewal.year == 10
        assert renewal.amount == Decimal("6340.00")


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape test (network call mocked)
# ──────────────────────────────────────────────────────────────────────


_FIXTURE_BY_RIGHT = {
    "patent": PATENT_FIXTURE,
    "marka": TM_FIXTURE,
    "tasarim": DESIGN_FIXTURE,
}


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: tr.TurkpatentFeesClient, right: str) -> str:
        return _FIXTURE_BY_RIGHT[right].read_text()

    monkeypatch.setattr(tr.TurkpatentFeesClient, "fetch_html", fake_fetch)


@pytest.mark.asyncio
async def test_scrape_patents_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await tr.scrape_turkpatent_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "TR"
    assert schedule.office_code == "TURKPATENT"
    assert schedule.right == RightType.patent
    assert schedule.currency == "TRY"
    assert schedule.statutory_basis is not None
    assert "Law 6769" in schedule.statutory_basis
    assert schedule.effective_date.year == 2026
    assert len(schedule.fees) >= 50


@pytest.mark.asyncio
async def test_scrape_trademarks_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await tr.scrape_turkpatent_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "TRY"
    assert len(schedule.fees) >= 25


@pytest.mark.asyncio
async def test_scrape_designs_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await tr.scrape_turkpatent_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "TRY"
    assert len(schedule.fees) >= 18


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_registry_dispatches_all_three_tr_routes() -> None:
    from patent_client_agents.fees.registry import get_scraper

    p = get_scraper("TURKPATENT", RightType.patent)
    tm = get_scraper("TURKPATENT", RightType.trademark)
    d = get_scraper("TURKPATENT", RightType.design)
    assert p is tr.scrape_turkpatent_patents
    assert tm is tr.scrape_turkpatent_trademarks
    assert d is tr.scrape_turkpatent_designs
