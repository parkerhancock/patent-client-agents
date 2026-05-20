"""Tests for the IMPI Mexico fee scraper.

Two layers:

* **Unit tests** of helpers — code-base-letter parser, Cuarta-
  eligibility, article-to-right routing, row parser, annuity year
  mapping.
* **Integration tests** that drive the per-right builders against
  the cached *Acuerdo* PDF
  (``tests/fees/fixtures/mx_impi_acuerdo_2023-05-12.pdf``) so the
  schedule shape is exercised without a network call.

Refresh the fixture by re-downloading from ``IMPI_FEES_PDF_URL``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeSchedule,
    RightType,
)
from patent_client_agents.fees.scrapers import impi

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "mx_impi_acuerdo_2023-05-12.pdf"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestCodeBaseLetter:
    def test_plain_number(self) -> None:
        assert impi._code_base_letter("2") == (2, None, False)

    def test_with_letter(self) -> None:
        assert impi._code_base_letter("1 a") == (1, "a", False)

    def test_with_letter_and_bis(self) -> None:
        assert impi._code_base_letter("1 a bis") == (1, "a", True)

    def test_with_uppercase_bis(self) -> None:
        assert impi._code_base_letter("26 BIS") == (26, None, True)

    def test_with_ter(self) -> None:
        assert impi._code_base_letter("16 ter") == (16, None, True)

    def test_garbage(self) -> None:
        assert impi._code_base_letter("not-a-code") == (0, None, False)


class TestCuartaEligibility:
    """Disposición Cuarta 50% reduction applies to Arts. 1a-1f, 2-13, 19-23, 26 BIS."""

    def test_1a_eligible(self) -> None:
        assert impi._is_cuarta_eligible("1 a")

    def test_1f_eligible(self) -> None:
        assert impi._is_cuarta_eligible("1 f")

    def test_1g_not_eligible(self) -> None:
        # Article 1g (Certificado Complementario) is excluded.
        assert not impi._is_cuarta_eligible("1 g")

    def test_2_eligible(self) -> None:
        assert impi._is_cuarta_eligible("2 a")

    def test_13_eligible(self) -> None:
        assert impi._is_cuarta_eligible("13")

    def test_14_not_eligible(self) -> None:
        # Article 14 (trademarks) is NOT eligible for the 50% reduction.
        assert not impi._is_cuarta_eligible("14 a")
        assert not impi._is_cuarta_eligible("14 c")

    def test_15_not_eligible(self) -> None:
        # Article 15 (GIs) is NOT eligible.
        assert not impi._is_cuarta_eligible("15 a")

    def test_26_bis_eligible(self) -> None:
        # Only 26 BIS qualifies under the Cuarta list (26 + BIS).
        assert impi._is_cuarta_eligible("26 BIS")

    def test_27_not_eligible(self) -> None:
        # Article 27 (certified copies) is NOT in the Cuarta list.
        assert not impi._is_cuarta_eligible("27 a")


class TestRouteForCode:
    def test_patent_arts_1_to_5(self) -> None:
        assert impi._route_for_code("1 a") == "patent"
        assert impi._route_for_code("2 b") == "patent"
        assert impi._route_for_code("5") == "patent"

    def test_um_rows_bundle_into_patent(self) -> None:
        assert impi._route_for_code("9 a") == "patent"
        assert impi._route_for_code("9 d") == "patent"
        assert impi._route_for_code("10 a") == "patent"

    def test_design_rows(self) -> None:
        assert impi._route_for_code("9 f") == "design"
        assert impi._route_for_code("9 g") == "design"
        assert impi._route_for_code("11") == "design"
        assert impi._route_for_code("12 b") == "design"

    def test_trademark_rows(self) -> None:
        assert impi._route_for_code("14 a") == "trademark"
        assert impi._route_for_code("14 c") == "trademark"

    def test_general_rows(self) -> None:
        assert impi._route_for_code("27 a") == "general"
        assert impi._route_for_code("13") == "general"

    def test_pct_madrid_hague_skipped(self) -> None:
        assert impi._route_for_code("35") == "intl"
        assert impi._route_for_code("36") == "intl"
        assert impi._route_for_code("37") == "intl"


class TestParseRows:
    @pytest.fixture(scope="class")
    def parsed_rows(self) -> list[tuple[str, str, Decimal]]:
        text = impi._extract_pdf_text(FIXTURE_PDF.read_bytes())
        return impi._parse_rows(text)

    def test_parses_many_rows(
        self, parsed_rows: list[tuple[str, str, Decimal]]
    ) -> None:
        assert len(parsed_rows) >= 70

    def test_filing_fee_1a(self, parsed_rows: list[tuple[str, str, Decimal]]) -> None:
        # Art 1a: patent filing $4,550.00.
        matches = [r for r in parsed_rows if r[0] == "1 a"]
        assert len(matches) == 1
        assert matches[0][2] == Decimal("4550.00")

    def test_per_additional_page_1a_bis(
        self, parsed_rows: list[tuple[str, str, Decimal]]
    ) -> None:
        # Art 1a bis: $61.00 per additional page.
        matches = [r for r in parsed_rows if r[0] == "1 a bis"]
        assert len(matches) == 1
        assert matches[0][2] == Decimal("61.00")

    def test_annuity_year_band_2a(
        self, parsed_rows: list[tuple[str, str, Decimal]]
    ) -> None:
        # Art 2a: annuity years 1-5 = $1,161.90 per year.
        matches = [r for r in parsed_rows if r[0] == "2 a"]
        assert len(matches) == 1
        assert matches[0][2] == Decimal("1161.90")

    def test_design_renewal_11(self, parsed_rows: list[tuple[str, str, Decimal]]) -> None:
        # Art 11: design renewal $5,926.75 per 5-year period.
        matches = [r for r in parsed_rows if r[0] == "11"]
        assert len(matches) == 1
        assert matches[0][2] == Decimal("5926.75")

    def test_tm_filing_14a(self, parsed_rows: list[tuple[str, str, Decimal]]) -> None:
        # Art 14a: TM filing $2,695.18.
        matches = [r for r in parsed_rows if r[0] == "14 a"]
        assert len(matches) == 1
        assert matches[0][2] == Decimal("2695.18")

    def test_tm_renewal_14c(self, parsed_rows: list[tuple[str, str, Decimal]]) -> None:
        # Art 14c: TM renewal $2,597.77.
        matches = [r for r in parsed_rows if r[0] == "14 c"]
        assert len(matches) == 1
        assert matches[0][2] == Decimal("2597.77")

    def test_no_footer_artifacts(
        self, parsed_rows: list[tuple[str, str, Decimal]]
    ) -> None:
        # Page-footer + phone-number fragments must not leak into the
        # parsed rows.
        for _, desc, _ in parsed_rows:
            assert "Periférico Sur" not in desc
            assert "gob.mx/impi" not in desc

    def test_no_section_opener_rows(
        self, parsed_rows: list[tuple[str, str, Decimal]]
    ) -> None:
        # Rows whose description ends with "siguientes tarifas" are
        # group headers, not per-row fees — must be filtered.
        for _, desc, _ in parsed_rows:
            assert "siguientes tarifas" not in desc.lower()


# ──────────────────────────────────────────────────────────────────────
# Integration tests — per-right builders against the cached PDF
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def parsed_rows() -> list[tuple[str, str, Decimal]]:
    text = impi._extract_pdf_text(FIXTURE_PDF.read_bytes())
    return impi._parse_rows(text)


class TestBuildPatentFees:
    def test_yields_substantial_schedule(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "patent", RightType.patent)
        # Patent + UM + IC rows + general procedural rows + Cuarta
        # small-tier duplicates → ~100 FeeItems.
        assert len(fees) >= 80

    def test_filing_fee_emits_both_tiers(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "patent", RightType.patent)
        # Art 1a should emit twice: large at $4,550 + small at $2,275.
        large = [f for f in fees if f.code == "impi-1-a" and f.tier == EntityTier.large]
        small = [f for f in fees if f.code == "impi-1-a-small" and f.tier == EntityTier.small]
        assert len(large) == 1
        assert large[0].amount == Decimal("4550.00")
        assert large[0].category == FeeCategory.filing
        assert len(small) == 1
        assert small[0].amount == Decimal("2275.00")  # 50% of 4,550
        assert small[0].notes is not None
        assert "Disposición Cuarta" in small[0].notes

    def test_certificado_complementario_no_small_tier(self, parsed_rows) -> None:
        # Art 1g is not Cuarta-eligible — no small-tier duplicate.
        fees = impi._emit_fees_for_rights(parsed_rows, "patent", RightType.patent)
        small = [f for f in fees if f.code == "impi-1-g-small"]
        assert small == []

    def test_patent_annuities_emit_with_year(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "patent", RightType.patent)
        annuities = [f for f in fees if f.category == FeeCategory.maintenance]
        # 2a / 2b / 2c × 2 tiers = 6 annuity FeeItems (large + small for each band).
        assert len(annuities) >= 6
        years = {f.year for f in annuities}
        assert 1 in years
        assert 6 in years
        assert 11 in years

    def test_um_rows_bundled_in(self, parsed_rows) -> None:
        # Article 9a is utility-model filing — bundled into the patent
        # schedule, not a separate one.
        fees = impi._emit_fees_for_rights(parsed_rows, "patent", RightType.patent)
        um_filing = [f for f in fees if f.code == "impi-9-a"]
        assert um_filing, "expected Art 9a (utility model filing) under patent schedule"


class TestBuildTrademarkFees:
    def test_yields_schedule(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "trademark", RightType.trademark)
        # Art 14 sub-letters + general procedural rows → ~35-40 FeeItems.
        assert 30 <= len(fees) <= 50

    def test_tm_renewal_carries_year_10(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "trademark", RightType.trademark)
        renewal = next(f for f in fees if f.code == "impi-14-c")
        assert renewal.category == FeeCategory.renewal
        assert renewal.year == 10
        assert renewal.amount == Decimal("2597.77")

    def test_no_cuarta_small_tier_on_14a(self, parsed_rows) -> None:
        # Trademark filings (Art 14a) are NOT eligible for the Cuarta
        # 50% reduction — no small-tier duplicate should emit.
        fees = impi._emit_fees_for_rights(parsed_rows, "trademark", RightType.trademark)
        large = [f for f in fees if f.code == "impi-14-a" and f.tier == EntityTier.large]
        small = [f for f in fees if f.code == "impi-14-a-small"]
        assert len(large) == 1
        assert small == []

    def test_no_patent_or_design_codes_leak(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "trademark", RightType.trademark)
        for f in fees:
            assert RightType.trademark in f.rights
            assert "1-a" != f.code.removeprefix("impi-").split("-small")[0]


class TestBuildDesignFees:
    def test_yields_schedule(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "design", RightType.design)
        # Design-specific rows (9f, 9g, 11, 12b) + general → ~40-50.
        assert len(fees) >= 30

    def test_design_grant_9g(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "design", RightType.design)
        grant = next(f for f in fees if f.code == "impi-9-g")
        assert grant.category == FeeCategory.grant
        assert grant.amount == Decimal("5770.45")

    def test_design_renewal_11_year_5(self, parsed_rows) -> None:
        fees = impi._emit_fees_for_rights(parsed_rows, "design", RightType.design)
        renewal = next(f for f in fees if f.code == "impi-11")
        assert renewal.category == FeeCategory.renewal
        assert renewal.year == 5
        assert renewal.amount == Decimal("5926.75")

    def test_design_cuarta_duplicates(self, parsed_rows) -> None:
        # Design rows are Cuarta-eligible (not in the Art 14 carve-out).
        fees = impi._emit_fees_for_rights(parsed_rows, "design", RightType.design)
        small = [f for f in fees if f.tier == EntityTier.small]
        assert len(small) > 0


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape test (network call mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_bytes = FIXTURE_PDF.read_bytes()

    async def fake_fetch(self: impi.IMPIFeesClient) -> bytes:
        return pdf_bytes

    monkeypatch.setattr(impi.IMPIFeesClient, "fetch_pdf", fake_fetch)


@pytest.mark.asyncio
async def test_scrape_patents_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await impi.scrape_impi_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "MX"
    assert schedule.office_code == "IMPI"
    assert schedule.right == RightType.patent
    assert schedule.currency == "MXN"
    assert schedule.effective_date == impi.IMPI_LAST_REFORM_DATE
    assert schedule.statutory_basis is not None
    assert "LFPPI" in schedule.statutory_basis
    assert len(schedule.fees) >= 80


@pytest.mark.asyncio
async def test_scrape_trademarks_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await impi.scrape_impi_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "MXN"
    assert len(schedule.fees) >= 30


@pytest.mark.asyncio
async def test_scrape_designs_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await impi.scrape_impi_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "MXN"
    assert len(schedule.fees) >= 30


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_registry_dispatches_all_three_impi_routes() -> None:
    from patent_client_agents.fees.registry import get_scraper

    p = get_scraper("IMPI", RightType.patent)
    tm = get_scraper("IMPI", RightType.trademark)
    d = get_scraper("IMPI", RightType.design)
    assert p is impi.scrape_impi_patents
    assert tm is impi.scrape_impi_trademarks
    assert d is impi.scrape_impi_designs
