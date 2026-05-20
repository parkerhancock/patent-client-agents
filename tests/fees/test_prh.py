"""Tests for the PRH Finland fee scraper.

Two layers:

* **Unit tests** of helpers — Finnish amount parser (EU thousands-as-
  space / comma-decimal convention), section header detection,
  annuity-year extraction, channel detection.
* **Integration tests** that drive the per-right builders against the
  cached Maksuasetus PDF
  (``tests/fees/fixtures/fi_prh_maksuasetus_171-2026.pdf``) so the
  schedule shape is exercised without a network call.

Refresh the fixture by re-downloading from PRH:

    https://www.prh.fi/material/sites/prh/attachments/tietoaprhsta/
    maksuasetusl-llehikoinen/5o12dsujn/Maksuasetus_171_2026.pdf
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from patent_client_agents.fees.models import (
    ConditionalTrigger,
    EntityTier,
    FeeCategory,
    FeeSchedule,
    RightType,
)
from patent_client_agents.fees.scrapers import prh_fi

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "fi_prh_maksuasetus_171-2026.pdf"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseAmount:
    """EU number convention: ``1 010`` = 1010, ``2,50`` = 2.50."""

    def test_integer_no_separator(self) -> None:
        assert prh_fi._parse_amount("450") == Decimal("450")

    def test_thousands_with_space(self) -> None:
        assert prh_fi._parse_amount("1 010") == Decimal("1010")
        assert prh_fi._parse_amount("1 560") == Decimal("1560")

    def test_decimal_with_comma(self) -> None:
        assert prh_fi._parse_amount("2,50") == Decimal("2.50")

    def test_thousands_with_nbsp(self) -> None:
        # Non-breaking space is normalized to regular space by the
        # extract-lines helper before reaching this parser.
        assert prh_fi._parse_amount("1 010") == Decimal("1010")


class TestSectionHeader:
    def test_section_1_patentit(self) -> None:
        assert prh_fi._is_section_header("1. Kansalliset patenttiasiat") == (
            1,
            "Kansalliset patenttiasiat",
        )

    def test_section_8_tavaramerkki(self) -> None:
        assert prh_fi._is_section_header("8. Tavaramerkkiasiat") == (8, "Tavaramerkkiasiat")

    def test_section_9_mallioikeus(self) -> None:
        assert prh_fi._is_section_header("9. Mallioikeusasiat") == (9, "Mallioikeusasiat")

    def test_section_3_pct(self) -> None:
        result = prh_fi._is_section_header(
            "3. Patenttiyhteistyösopimuksen (SopS 58/1980, PCT) mukaiset asiat"
        )
        assert result is not None
        assert result[0] == 3

    def test_year_row_is_not_section_header(self) -> None:
        # "3. vuosi" is an annuity row, NOT a section header.
        assert prh_fi._is_section_header("3. vuosi") is None
        assert prh_fi._is_section_header("20. vuosi") is None

    def test_amount_line_is_not_section_header(self) -> None:
        assert (
            prh_fi._is_section_header("Hakemusmaksu sähköistä järjestelmää käyttäen 450 €") is None
        )


class TestAnnuityYear:
    def test_patent_year_1(self) -> None:
        assert prh_fi._patent_annuity_year("1. vuosi") == 1

    def test_patent_year_20(self) -> None:
        assert prh_fi._patent_annuity_year("20. vuosi") == 20

    def test_spc_year(self) -> None:
        assert prh_fi._patent_annuity_year("Lisäsuojatodistuksen vuosimaksu 3. vuosi") == 3

    def test_non_annuity_returns_none(self) -> None:
        assert prh_fi._patent_annuity_year("Hakemusmaksu sähköistä järjestelmää käyttäen") is None


class TestLabelChannel:
    def test_electronic(self) -> None:
        assert prh_fi._label_channel("Hakemusmaksu sähköistä järjestelmää käyttäen") == "electronic"

    def test_paper(self) -> None:
        assert (
            prh_fi._label_channel("Hakemusmaksu muuta kuin sähköistä järjestelmää käyttäen")
            == "paper"
        )

    def test_default(self) -> None:
        assert prh_fi._label_channel("Käännösmaksu") == "default"


# ──────────────────────────────────────────────────────────────────────
# Integration tests against the cached PDF fixture
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def parsed_rows() -> list[tuple[int, str, str, Decimal, str]]:
    pdf = FIXTURE_PDF.read_bytes()
    lines = prh_fi._extract_pdf_lines(pdf)
    return prh_fi._walk_sections(lines)


class TestParsedRows:
    """The PDF parser produces sane row counts per section."""

    def test_section_1_has_many_rows(self, parsed_rows: list) -> None:
        s1 = [r for r in parsed_rows if r[0] == 1]
        # §1 covers filing, claims, search/exam, publication, 20 annuity
        # years, opposition, transfer — comfortably above 35.
        assert len(s1) >= 35

    def test_section_5_spc_has_6_annuities(self, parsed_rows: list) -> None:
        # SPC publishes 6 years.
        spc_annuities = [
            r
            for r in parsed_rows
            if r[0] == 5 and "vuosimaksu" in r[2].lower() and "vuosi" in r[2].lower()
        ]
        assert len(spc_annuities) == 6

    def test_section_8_has_both_channels(self, parsed_rows: list) -> None:
        s8 = [r for r in parsed_rows if r[0] == 8]
        channels = {r[1] for r in s8}
        assert channels == {"electronic", "paper"}

    def test_section_9_present(self, parsed_rows: list) -> None:
        s9 = [r for r in parsed_rows if r[0] == 9]
        assert len(s9) >= 10


class TestBuildPatentFees:
    def test_yields_substantial_schedule(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        # §1 alone has ~40 rows, §2 ~20, §3 ~14, §4 ~7, §5 ~16 → ~95+.
        assert len(fees) >= 90

    def test_includes_filing_and_renewal(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        cats = {f.category for f in fees}
        assert FeeCategory.filing in cats
        assert FeeCategory.renewal in cats
        assert FeeCategory.examination in cats or FeeCategory.search in cats

    def test_all_amounts_are_decimal_positive(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        for f in fees:
            assert isinstance(f.amount, Decimal)
            assert f.amount >= Decimal("0")

    def test_currency_eur(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        assert all(f.currency == "EUR" for f in fees)

    def test_no_entity_tier_discounts(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        # Finland has no small/micro entity discounts.
        assert all(f.tier == EntityTier.none for f in fees)

    def test_patent_filing_fee_amount(self, parsed_rows: list) -> None:
        """§1 'Hakemusmaksu sähköistä järjestelmää käyttäen' is €450 per 171/2026."""
        fees = prh_fi._build_patent_fees(parsed_rows)
        electronic_filing = [
            f
            for f in fees
            if f.category == FeeCategory.filing
            and "sähköistä" in f.label.lower()
            and "hakemusmaksu" in f.label.lower()
        ]
        assert any(f.amount == Decimal("450") for f in electronic_filing)

    def test_annuity_year_20(self, parsed_rows: list) -> None:
        """20-year annuity is €1,010 per 171/2026."""
        fees = prh_fi._build_patent_fees(parsed_rows)
        y20 = [
            f
            for f in fees
            if f.category == FeeCategory.renewal
            and f.year == 20
            and f.code.startswith("fi-prh-pat")
        ]
        assert len(y20) >= 1
        assert y20[0].amount == Decimal("1010")

    def test_patent_annuities_years_1_to_20_present(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        pat_annuity_years = sorted(
            {
                f.year
                for f in fees
                if f.category == FeeCategory.renewal
                and f.code.startswith("fi-prh-pat")
                and f.year is not None
            }
        )
        # All 20 years should appear at least once.
        assert pat_annuity_years == list(range(1, 21))

    def test_claims_over_15_surcharge(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        excess = [f for f in fees if f.category == FeeCategory.excess_claims]
        # §1 has a 15-claim threshold; §2 (UM) has a 5-claim threshold.
        assert len(excess) >= 2
        thresholds = {
            f.condition.threshold
            for f in excess
            if f.condition is not None and f.condition.threshold is not None
        }
        assert 15 in thresholds
        assert 5 in thresholds

    def test_spc_annuity_full_ladder(self, parsed_rows: list) -> None:
        fees = prh_fi._build_patent_fees(parsed_rows)
        spc_annuities = [
            f for f in fees if f.code.startswith("fi-prh-spc") and f.category == FeeCategory.renewal
        ]
        years = sorted(f.year for f in spc_annuities if f.year is not None)
        assert years == [1, 2, 3, 4, 5, 6]

    def test_full_schedule_constructs(self, parsed_rows: list) -> None:
        """End-to-end FeeSchedule construction with parsed rows."""
        from datetime import date

        fees = prh_fi._build_patent_fees(parsed_rows)
        schedule = FeeSchedule(
            jurisdiction="FI",
            issuing_body="Patentti- ja rekisterihallitus (PRH)",
            office_code="PRH",
            right=RightType.patent,
            currency="EUR",
            effective_date=prh_fi.PRH_EFFECTIVE_DATE,
            source_url=prh_fi.PRH_PATENTS_URL,
            statutory_basis="Patenttilaki (550/1967)",
            retrieved_at=date.today(),
            fees=fees,
        )
        assert schedule.key == "FI/PRH/patent"


class TestBuildTrademarkFees:
    def test_yields_schedule(self, parsed_rows: list) -> None:
        fees = prh_fi._build_trademark_fees(parsed_rows)
        # 15 electronic + 20 paper rows = 35.
        assert len(fees) >= 30

    def test_renewal_carries_year_10(self, parsed_rows: list) -> None:
        fees = prh_fi._build_trademark_fees(parsed_rows)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert len(renewals) >= 2  # at least electronic + paper
        assert all(f.year == 10 for f in renewals)

    def test_electronic_filing_fee(self, parsed_rows: list) -> None:
        # Electronic TM filing is €250.
        fees = prh_fi._build_trademark_fees(parsed_rows)
        electronic_filing = [
            f
            for f in fees
            if f.category == FeeCategory.filing
            and "electronic" in f.code
            and "tavaramerkin-rekisteroinnin" in f.code
        ]
        assert any(f.amount == Decimal("250") for f in electronic_filing)

    def test_paper_filing_fee_higher(self, parsed_rows: list) -> None:
        # Paper TM filing is €300 — 50€ more than electronic.
        fees = prh_fi._build_trademark_fees(parsed_rows)
        paper_filing = [
            f
            for f in fees
            if f.category == FeeCategory.filing
            and "paper" in f.code
            and "tavaramerkin-rekisteroinnin" in f.code
        ]
        assert any(f.amount == Decimal("300") for f in paper_filing)

    def test_paper_rows_carry_paper_filing_condition(self, parsed_rows: list) -> None:
        fees = prh_fi._build_trademark_fees(parsed_rows)
        paper_rows = [f for f in fees if "paper" in f.code]
        # Class-surcharge rows have a class condition; pure paper rows
        # have the paper_filing condition. At least the registration
        # rows should carry paper_filing.
        paper_filing_rows = [
            f
            for f in paper_rows
            if f.condition is not None and f.condition.trigger == ConditionalTrigger.paper_filing
        ]
        assert len(paper_filing_rows) >= 5

    def test_excess_classes_condition(self, parsed_rows: list) -> None:
        fees = prh_fi._build_trademark_fees(parsed_rows)
        excess = [f for f in fees if f.category == FeeCategory.excess_classes]
        assert len(excess) >= 2  # at least one electronic + one paper
        # Per-class surcharge is €100/class.
        assert all(f.amount == Decimal("100") for f in excess)
        # All carry classes_over with threshold=1.
        for f in excess:
            assert f.condition is not None
            assert f.condition.trigger == ConditionalTrigger.classes_over
            assert f.condition.threshold == 1


class TestBuildDesignFees:
    def test_yields_schedule(self, parsed_rows: list) -> None:
        fees = prh_fi._build_design_fees(parsed_rows)
        assert len(fees) >= 15

    def test_includes_filing_and_renewal(self, parsed_rows: list) -> None:
        fees = prh_fi._build_design_fees(parsed_rows)
        cats = {f.category for f in fees}
        assert FeeCategory.filing in cats
        assert FeeCategory.renewal in cats

    def test_design_electronic_filing_fee(self, parsed_rows: list) -> None:
        # §9 electronic filing is €250.
        fees = prh_fi._build_design_fees(parsed_rows)
        electronic_filings = [
            f for f in fees if f.category == FeeCategory.filing and "sähköistä" in f.label.lower()
        ]
        assert any(f.amount == Decimal("250") for f in electronic_filings)

    def test_renewal_carries_year_10(self, parsed_rows: list) -> None:
        fees = prh_fi._build_design_fees(parsed_rows)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert len(renewals) >= 1
        assert all(f.year == 10 for f in renewals)

    def test_renewal_amount(self, parsed_rows: list) -> None:
        # §9 "Uudistamismaksu" is €380.
        fees = prh_fi._build_design_fees(parsed_rows)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert any(f.amount == Decimal("380") for f in renewals)


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape test (network call mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_bytes = FIXTURE_PDF.read_bytes()

    async def fake_fetch(self: prh_fi.PRHFeesClient) -> bytes:
        return pdf_bytes

    monkeypatch.setattr(prh_fi.PRHFeesClient, "fetch_pdf", fake_fetch)


@pytest.mark.asyncio
async def test_prh_patents_schedule_has_filing_renewal(patch_fetch: None) -> None:
    schedule = await prh_fi.scrape_prh_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "FI"
    assert schedule.office_code == "PRH"
    assert schedule.right == RightType.patent
    assert schedule.currency == "EUR"
    assert schedule.statutory_basis is not None
    assert "Patenttilaki" in schedule.statutory_basis
    assert schedule.effective_date.year == 2026
    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats
    assert len(schedule.fees) >= 90


@pytest.mark.asyncio
async def test_prh_trademarks_schedule_has_filing_renewal(patch_fetch: None) -> None:
    schedule = await prh_fi.scrape_prh_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "EUR"
    assert "Tavaramerkkilaki" in (schedule.statutory_basis or "")
    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats
    assert len(schedule.fees) >= 30


@pytest.mark.asyncio
async def test_prh_designs_schedule_has_filing_renewal(patch_fetch: None) -> None:
    schedule = await prh_fi.scrape_prh_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "EUR"
    assert "Mallioikeuslaki" in (schedule.statutory_basis or "")
    cats = {f.category for f in schedule.fees}
    assert FeeCategory.filing in cats
    assert FeeCategory.renewal in cats
    assert len(schedule.fees) >= 15


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_prh_all_routes_registered_in_registry() -> None:
    from patent_client_agents.fees.registry import OFFICES, get_scraper

    p = get_scraper("PRH", RightType.patent)
    tm = get_scraper("PRH", RightType.trademark)
    d = get_scraper("PRH", RightType.design)
    assert p is prh_fi.scrape_prh_patents
    assert tm is prh_fi.scrape_prh_trademarks
    assert d is prh_fi.scrape_prh_designs
    assert "PRH" in OFFICES
