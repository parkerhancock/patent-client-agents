"""Tests for the OEPM Spain fee scraper.

Two layers:

* **Unit tests** of internal parsers (no PDF) — amount parser, code
  classifier, catalog-key normalization, SPC year extraction.
* **Integration tests** that run the per-right builders against a
  stored copy of the consolidated TASAS PDF
  (``tests/fees/fixtures/oepm_tasas_2026-04-01.pdf``) so the schedule
  shape is exercised without a network call.

The fixture is the canonical "Actualizado a fecha: 1 de abril de
2026" snapshot fetched on 2026-05-19. Refresh by re-downloading from
``OEPM_FEES_PDF_URL`` and replacing the file.
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
from patent_client_agents.fees.scrapers import oepm

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "oepm_tasas_2026-04-01.pdf"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseEsAmount:
    def test_plain_two_decimals(self) -> None:
        assert oepm._parse_es_amount("150,45") == Decimal("150.45")

    def test_thousands_separator(self) -> None:
        assert oepm._parse_es_amount("7.329,17") == Decimal("7329.17")

    def test_large_amount(self) -> None:
        assert oepm._parse_es_amount("2.448,24") == Decimal("2448.24")

    def test_single_digit_euros(self) -> None:
        assert oepm._parse_es_amount("3,64") == Decimal("3.64")

    def test_empty_returns_none(self) -> None:
        assert oepm._parse_es_amount("") is None

    def test_bare_integer_returns_none(self) -> None:
        # Bare integers aren't a valid OEPM amount (the schedule always
        # carries ,NN cents); we expect this to parse as Decimal but the
        # row regex never produces them in the first place.
        assert oepm._parse_es_amount("100") == Decimal("100")

    def test_garbage_returns_none(self) -> None:
        assert oepm._parse_es_amount("not-an-amount") is None


class TestClassifyCode:
    """Code → ``(right_bucket, tier, channel)`` mapping."""

    def test_patent_full_rate_paper(self) -> None:
        assert oepm._classify_code("IT01") == ("patent", EntityTier.large, "paper")

    def test_patent_full_rate_electronic(self) -> None:
        assert oepm._classify_code("IE01") == ("patent", EntityTier.large, "electronic")

    def test_patent_pyme_paper(self) -> None:
        assert oepm._classify_code("YT01") == ("patent", EntityTier.small, "paper")

    def test_patent_pyme_electronic(self) -> None:
        assert oepm._classify_code("YE22") == ("patent", EntityTier.small, "electronic")

    def test_patent_university_paper(self) -> None:
        assert oepm._classify_code("UT01") == ("patent", EntityTier.small, "paper")

    def test_patent_university_electronic(self) -> None:
        assert oepm._classify_code("UE04") == ("patent", EntityTier.small, "electronic")

    def test_trademark_paper(self) -> None:
        assert oepm._classify_code("MT17") == ("trademark", EntityTier.large, "paper")

    def test_trademark_electronic(self) -> None:
        assert oepm._classify_code("ME17") == ("trademark", EntityTier.large, "electronic")

    def test_trademark_max_payment_paper(self) -> None:
        assert oepm._classify_code("MX15") == ("trademark", EntityTier.large, "paper")

    def test_trademark_max_payment_electronic(self) -> None:
        assert oepm._classify_code("XM10") == ("trademark", EntityTier.large, "electronic")

    def test_design_paper(self) -> None:
        assert oepm._classify_code("DT25") == ("design", EntityTier.large, "paper")

    def test_design_electronic(self) -> None:
        assert oepm._classify_code("DE26") == ("design", EntityTier.large, "electronic")

    def test_design_max_payment_paper(self) -> None:
        assert oepm._classify_code("DX36") == ("design", EntityTier.large, "paper")

    def test_common_full_rate_paper(self) -> None:
        assert oepm._classify_code("CM01") == ("common", EntityTier.large, "paper")

    def test_common_full_rate_electronic(self) -> None:
        assert oepm._classify_code("CI01") == ("common", EntityTier.large, "electronic")

    def test_common_in_patent_section_paper(self) -> None:
        assert oepm._classify_code("I301") == ("common", EntityTier.large, "paper")

    def test_common_in_patent_section_electronic(self) -> None:
        assert oepm._classify_code("I501") == ("common", EntityTier.large, "electronic")

    def test_common_universities_paper(self) -> None:
        assert oepm._classify_code("I701") == ("common", EntityTier.small, "paper")

    def test_common_universities_electronic(self) -> None:
        assert oepm._classify_code("I801") == ("common", EntityTier.small, "electronic")

    def test_ep_validation_paper(self) -> None:
        assert oepm._classify_code("ET01") == ("patent", EntityTier.large, "paper")

    def test_ep_validation_electronic(self) -> None:
        assert oepm._classify_code("ET02") == ("patent", EntityTier.large, "electronic")

    def test_spc_annuity_single_channel(self) -> None:
        assert oepm._classify_code("CP01") == ("patent", EntityTier.large, "n/a")

    def test_agent_register_single_channel(self) -> None:
        assert oepm._classify_code("BB01") == ("common", EntityTier.large, "n/a")


class TestCatalogKey:
    """``Y[TE]nn`` / ``U[TE]nn`` codes share semantics with ``I[TE]nn``."""

    def test_pyme_paper_maps_to_full_rate(self) -> None:
        assert oepm._catalog_key("YT01") == "IT01"

    def test_pyme_electronic_maps_to_full_rate(self) -> None:
        assert oepm._catalog_key("YE22") == "IE22"

    def test_university_paper_maps_to_full_rate(self) -> None:
        assert oepm._catalog_key("UT01") == "IT01"

    def test_university_electronic_maps_to_full_rate(self) -> None:
        assert oepm._catalog_key("UE04") == "IE04"

    def test_university_proc_paper_maps_to_full_rate(self) -> None:
        assert oepm._catalog_key("I701") == "I301"

    def test_university_proc_electronic_maps_to_full_rate(self) -> None:
        assert oepm._catalog_key("I801") == "I501"

    def test_unrelated_code_passes_through(self) -> None:
        assert oepm._catalog_key("MT17") == "MT17"
        assert oepm._catalog_key("CP01") == "CP01"


class TestSpcAnnuityYearExtraction:
    """SPC annuity codes encode (year × recargo band) in the suffix."""

    def test_no_surcharge_years(self) -> None:
        assert oepm._spc_year_for_code("CP01") == 1
        assert oepm._spc_year_for_code("CP05") == 5

    def test_25_percent_surcharge_years(self) -> None:
        assert oepm._spc_year_for_code("CP21") == 1
        assert oepm._spc_year_for_code("CP25") == 5

    def test_50_percent_surcharge_years(self) -> None:
        assert oepm._spc_year_for_code("CP51") == 1
        assert oepm._spc_year_for_code("CP55") == 5

    def test_cp00_is_transitional(self) -> None:
        # CP00 is the transitional grant fee (pre-1.4.17), not an annuity.
        assert oepm._spc_year_for_code("CP00") is None

    def test_non_cp_code_returns_none(self) -> None:
        assert oepm._spc_year_for_code("IT01") is None
        assert oepm._spc_year_for_code("CPR0") is None

    def test_recargo_label_no_surcharge(self) -> None:
        assert oepm._spc_recargo_label("CP01") == "without surcharge"

    def test_recargo_label_25_pct(self) -> None:
        assert oepm._spc_recargo_label("CP21") == "25% surcharge"

    def test_recargo_label_50_pct(self) -> None:
        assert oepm._spc_recargo_label("CP51") == "50% surcharge"


class TestSpcAnnuityLabel:
    def test_year_1_no_surcharge(self) -> None:
        assert oepm._spc_annuity_label("CP01") == "SPC annuity — year 1 (without surcharge)"

    def test_year_5_50_pct(self) -> None:
        assert oepm._spc_annuity_label("CP55") == "SPC annuity — year 5 (50% surcharge)"

    def test_unrelated_code_returns_none(self) -> None:
        assert oepm._spc_annuity_label("IT01") is None


# ──────────────────────────────────────────────────────────────────────
# Integration tests against the cached PDF fixture
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def oepm_pdf_text() -> str:
    pdf_bytes = FIXTURE_PDF.read_bytes()
    return oepm._extract_pdf_text(pdf_bytes)


class TestBuildPatentFees:
    def test_yields_a_substantial_schedule(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        assert len(fees) >= 120

    def test_includes_filing_search_and_examination(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        cats = {f.category for f in fees}
        assert FeeCategory.filing in cats
        assert FeeCategory.search in cats
        assert FeeCategory.examination in cats
        assert FeeCategory.translation in cats  # EP-validation
        assert FeeCategory.renewal in cats  # SPC annuities

    def test_it01_paper_amount(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        it01 = next(f for f in fees if f.code == "oepm-IT01")
        # €102.39 per the research-note synopsis (§4) for the 2026-04-01 PDF.
        assert it01.amount == Decimal("102.39")
        assert it01.tier == EntityTier.large
        # paper channel ships with the paper_filing FeeCondition.
        assert it01.condition is not None
        assert it01.condition.trigger.value == "paper_filing"

    def test_ie01_electronic_amount(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        ie01 = next(f for f in fees if f.code == "oepm-IE01")
        assert ie01.amount == Decimal("87.03")
        assert ie01.tier == EntityTier.large
        # Electronic channel does NOT carry a paper_filing condition.
        assert ie01.condition is None

    def test_yt01_is_50_pct_of_it01(self, oepm_pdf_text: str) -> None:
        """PYMES tier is published at 50% of the full rate per Ley 24/2015 art. 186."""
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        yt01 = next(f for f in fees if f.code == "oepm-YT01")
        assert yt01.amount == Decimal("51.20")  # half of 102.39, rounded
        assert yt01.tier == EntityTier.small

    def test_spc_annuity_years_complete(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        spc_renewals = [
            f for f in fees if f.category == FeeCategory.renewal and f.code.startswith("oepm-CP")
        ]
        # 5 years × 3 recargo bands (no surcharge / 25% / 50%) = 15 rows.
        assert len(spc_renewals) == 15
        # Year coverage 1-5.
        years = {f.year for f in spc_renewals}
        assert years == {1, 2, 3, 4, 5}

    def test_full_schedule_constructs(self, oepm_pdf_text: str) -> None:
        from datetime import date

        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.patent,
            accept_buckets={"patent", "common"},
        )
        schedule = FeeSchedule(
            jurisdiction="ES",
            issuing_body="Oficina Española de Patentes y Marcas (OEPM)",
            office_code="OEPM",
            right=RightType.patent,
            currency="EUR",
            effective_date=oepm.OEPM_EFFECTIVE_DATE,
            source_url=oepm.OEPM_FEES_PDF_URL,
            retrieved_at=date(2026, 5, 19),
            fees=fees,
        )
        assert schedule.key == "ES/OEPM/patent"
        assert schedule.currency == "EUR"
        # The effective_date is the PDF stamp.
        assert schedule.effective_date == date(2026, 4, 1)


class TestBuildTrademarkFees:
    def test_yields_dual_channel_schedule(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.trademark,
            accept_buckets={"trademark", "common"},
        )
        # MT/ME pairs + CM/CI common procedural.
        assert len(fees) >= 30

    def test_mt17_paper_amount(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.trademark,
            accept_buckets={"trademark", "common"},
        )
        mt17 = next(f for f in fees if f.code == "oepm-MT17")
        # MT17 is the 1st-class TM filing fee on the paper channel.
        # On the 2026-04-01 PDF this is €97,48 (the displayed paired-row
        # value); the research note's €150.45 sits on the higher TM
        # subset (collective / certification — MT18 row).
        assert mt17.amount == Decimal("97.48")
        assert mt17.category == FeeCategory.filing

    def test_me17_electronic_is_present(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.trademark,
            accept_buckets={"trademark", "common"},
        )
        me17 = next(f for f in fees if f.code == "oepm-ME17")
        assert me17.condition is None  # electronic
        assert me17.amount == Decimal("82.84")

    def test_per_class_surcharge_category(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.trademark,
            accept_buckets={"trademark", "common"},
        )
        # MT18 / ME18 = 2nd and each subsequent class
        mt18 = next(f for f in fees if f.code == "oepm-MT18")
        assert mt18.category == FeeCategory.excess_classes

    def test_excludes_patent_only_codes(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.trademark,
            accept_buckets={"trademark", "common"},
        )
        # IT/IE/YT/UE codes are patent-specific and must not appear here.
        codes = {f.code for f in fees}
        assert "oepm-IT01" not in codes
        assert "oepm-YT01" not in codes
        # MT/ME/CM/CI codes are TM-relevant and must appear.
        assert "oepm-MT17" in codes
        assert "oepm-CM01" in codes


class TestBuildDesignFees:
    def test_yields_dual_channel_schedule(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.design,
            accept_buckets={"design", "common"},
        )
        assert len(fees) >= 20

    def test_design_filing_is_present(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.design,
            accept_buckets={"design", "common"},
        )
        # DT25 = design divisional; DE26 = its electronic pair.
        codes = {f.code for f in fees}
        assert "oepm-DT25" in codes
        assert "oepm-DE26" in codes

    def test_excludes_patent_and_tm_codes(self, oepm_pdf_text: str) -> None:
        fees = oepm._build_fees_for_right(
            oepm_pdf_text,
            RightType.design,
            accept_buckets={"design", "common"},
        )
        codes = {f.code for f in fees}
        assert "oepm-IT01" not in codes
        assert "oepm-MT17" not in codes


class TestEffectiveDateConstant:
    def test_matches_pdf_stamp(self) -> None:
        from datetime import date

        # The cached fixture is the 2026-04-01 revision; the constant
        # must track it so consumers see the right effective_date.
        assert oepm.OEPM_EFFECTIVE_DATE == date(2026, 4, 1)
