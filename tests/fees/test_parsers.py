"""Tests for the per-office fee parsers (pure functions; no network)."""

from __future__ import annotations

from decimal import Decimal

from patent_client_agents.fees.models import FeeCategory
from patent_client_agents.fees.scrapers import cipo as cipo_mod
from patent_client_agents.fees.scrapers import cnipa as cnipa_mod
from patent_client_agents.fees.scrapers import dpma as dpma_mod
from patent_client_agents.fees.scrapers import epo as epo_mod
from patent_client_agents.fees.scrapers import euipo as euipo_mod
from patent_client_agents.fees.scrapers import inpi_br as inpi_br_mod
from patent_client_agents.fees.scrapers import tipo as tipo_mod
from patent_client_agents.fees.scrapers import uspto as uspto_mod


class TestUSPTOMoneyParser:
    def test_thousands_comma(self) -> None:
        assert uspto_mod._parse_money("2,150.00") == Decimal("2150.00")

    def test_plain_decimal(self) -> None:
        assert uspto_mod._parse_money("350.00") == Decimal("350.00")

    def test_na_returns_none(self) -> None:
        assert uspto_mod._parse_money("n/a") is None
        assert uspto_mod._parse_money("N/A") is None

    def test_dash_returns_none(self) -> None:
        assert uspto_mod._parse_money("—") is None

    def test_empty_returns_none(self) -> None:
        assert uspto_mod._parse_money("") is None


class TestUSPTOCodeSplit:
    def test_three_tier_codes(self) -> None:
        codes = uspto_mod._split_codes("1011/2011/3011")
        from patent_client_agents.fees.models import EntityTier

        assert codes[EntityTier.large] == "1011"
        assert codes[EntityTier.small] == "2011"
        assert codes[EntityTier.micro] == "3011"

    def test_single_code_falls_back_to_small(self) -> None:
        codes = uspto_mod._split_codes("4011†")
        from patent_client_agents.fees.models import EntityTier

        assert EntityTier.small in codes
        assert codes[EntityTier.small] == "4011"


class TestUSPTOMaintenanceYear:
    def test_3_5_rounds_to_4(self) -> None:
        assert uspto_mod._maintenance_year("due at 3.5 year") == 4

    def test_7_5_rounds_to_8(self) -> None:
        assert uspto_mod._maintenance_year("due at 7.5 year") == 8

    def test_11_5_rounds_to_12(self) -> None:
        assert uspto_mod._maintenance_year("due at 11.5 year") == 12

    def test_no_match_returns_none(self) -> None:
        assert uspto_mod._maintenance_year("Basic filing fee") is None


class TestUSPTOConditionDetection:
    def test_independent_claims_over(self) -> None:
        c = uspto_mod._detect_condition("each independent claim in excess of three")
        assert c is not None
        assert c.trigger == "independent_claims_over"
        assert c.per_unit is True

    def test_claims_in_excess_of_20(self) -> None:
        c = uspto_mod._detect_condition("for each claim in excess of 20")
        assert c is not None
        assert c.trigger == "claims_over"
        assert c.threshold == 20

    def test_no_condition_for_plain_filing(self) -> None:
        assert uspto_mod._detect_condition("Basic filing fee - Utility") is None


class TestEPOMoneyParser:
    def test_european_thousands(self) -> None:
        assert epo_mod._parse_eu_money("1.595,00") == Decimal("1595.00")

    def test_plain_two_decimals(self) -> None:
        assert epo_mod._parse_eu_money("285,00") == Decimal("285.00")

    def test_zero_amount(self) -> None:
        assert epo_mod._parse_eu_money("0,00") == Decimal("0")

    def test_none_input(self) -> None:
        assert epo_mod._parse_eu_money(None) is None

    def test_empty_input(self) -> None:
        assert epo_mod._parse_eu_money("") is None


class TestEPOYearExtraction:
    def test_third_year(self) -> None:
        assert epo_mod._extract_year("Renewal fee for the 3rd year") == 3

    def test_twentieth_year(self) -> None:
        assert epo_mod._extract_year("Renewal fee for the 20th year") == 20

    def test_no_year_returns_none(self) -> None:
        assert epo_mod._extract_year("Filing fee") is None


class TestEUIPOMoneyParser:
    def test_thousands_with_nbsp(self) -> None:
        # EUIPO uses NBSP between thousands
        assert euipo_mod._parse_euipo_money("€1 000") == Decimal("1000")

    def test_plain(self) -> None:
        assert euipo_mod._parse_euipo_money("€850") == Decimal("850")

    def test_footnote_marker_stripped(self) -> None:
        assert euipo_mod._parse_euipo_money("€60*") == Decimal("60")

    def test_takes_first_amount(self) -> None:
        # When there are parenthetical caps, take the headline
        assert euipo_mod._parse_euipo_money("€200\n(max. €1 000)") == Decimal("200")

    def test_non_numeric_returns_none(self) -> None:
        assert euipo_mod._parse_euipo_money("25%") is None
        assert euipo_mod._parse_euipo_money("see below") is None


class TestEUIPODesignYear:
    def test_first_period_is_year_5(self) -> None:
        assert euipo_mod._design_year("Fee for the first period of renewal") == 5

    def test_fourth_period_is_year_20(self) -> None:
        assert euipo_mod._design_year("Fee for the fourth period of renewal") == 20

    def test_no_period_returns_none(self) -> None:
        assert euipo_mod._design_year("Application fee") is None


class TestCIPOMoneyAndYearBand:
    def test_thousands_comma(self) -> None:
        assert cipo_mod._parse_money("1,027.00") == Decimal("1027.00")

    def test_plain_decimal(self) -> None:
        assert cipo_mod._parse_money("297.00") == Decimal("297.00")

    def test_see_description_skipped(self) -> None:
        assert cipo_mod._parse_money("See description") is None

    def test_band_2_3_4(self) -> None:
        years = cipo_mod._parse_year_band(
            "For the dates of each of the second, third and fourth anniversaries of the filing date"
        )
        assert years == [2, 3, 4]

    def test_band_5_to_9(self) -> None:
        years = cipo_mod._parse_year_band(
            "For the dates of each of the fifth, sixth, seventh, eighth and ninth"
        )
        assert years == [5, 6, 7, 8, 9]

    def test_band_10_to_14(self) -> None:
        years = cipo_mod._parse_year_band(
            "For the dates of each of the 10th, 11th, 12th, 13th and 14th"
        )
        assert years == [10, 11, 12, 13, 14]

    def test_band_20_plus(self) -> None:
        # "20th and each subsequent" — keep only 20; we don't expand past term
        years = cipo_mod._parse_year_band(
            "For the dates of the 20th and each subsequent anniversary"
        )
        assert years == [20]

    def test_non_band_returns_empty(self) -> None:
        assert cipo_mod._parse_year_band("Application fee") == []


class TestCNIPAMoneyAndYearRange:
    def test_plain(self) -> None:
        assert cnipa_mod._parse_money("900") == Decimal("900")

    def test_thousands(self) -> None:
        assert cnipa_mod._parse_money("2,500") == Decimal("2500")

    def test_invention_row_detected(self) -> None:
        from patent_client_agents.fees.models import RightType

        assert cnipa_mod._detect_row_right("1. Invention") == RightType.patent

    def test_utility_model_row_detected(self) -> None:
        from patent_client_agents.fees.models import RightType

        assert cnipa_mod._detect_row_right("2. Utility Model") == RightType.utility_model

    def test_design_row_detected(self) -> None:
        from patent_client_agents.fees.models import RightType

        assert cnipa_mod._detect_row_right("3. Design") == RightType.design

    def test_non_right_row(self) -> None:
        assert cnipa_mod._detect_row_right("1-3 Years (Each Year)") is None

    def test_year_range_regex(self) -> None:
        m = cnipa_mod._YEAR_RANGE_RE.search("1-3 Years (Each Year)")
        assert m is not None
        assert (int(m.group(1)), int(m.group(2))) == (1, 3)


class TestDPMAAmountAndYear:
    def test_plain_amount(self) -> None:
        assert dpma_mod._parse_amount("70") == Decimal("70")

    def test_thousands_with_space(self) -> None:
        # DPMA uses NBSP or regular space as thousands separator: "1 130"
        assert dpma_mod._parse_amount("1 130") == Decimal("1130")
        assert dpma_mod._parse_amount("2 030") == Decimal("2030")

    def test_empty(self) -> None:
        assert dpma_mod._parse_amount("") is None

    def test_year_3(self) -> None:
        assert dpma_mod._extract_year("for the 3rd year of the patent") == 3

    def test_year_20(self) -> None:
        assert dpma_mod._extract_year("for the 20th year of the patent") == 20

    def test_year_no_match(self) -> None:
        assert dpma_mod._extract_year("- surcharge for late payment (section 7)") is None

    def test_patent_code_310s_yes(self) -> None:
        assert dpma_mod._is_patent_code("311") is True
        assert dpma_mod._is_patent_code("312") is True
        assert dpma_mod._is_patent_code("318") is True

    def test_non_patent_code_no(self) -> None:
        assert dpma_mod._is_patent_code("330") is False  # trademark
        assert dpma_mod._is_patent_code("340") is False  # design


class TestTIPOMoneyAndAnnuity:
    def test_parse_nt_plain(self) -> None:
        assert tipo_mod._parse_nt("NT$3,500") == Decimal("3500")

    def test_parse_nt_with_space(self) -> None:
        # PDF extraction sometimes inserts whitespace between NT$ and the digits.
        assert tipo_mod._parse_nt("NT$ 7,000") == Decimal("7000")

    def test_parse_nt_zero(self) -> None:
        assert tipo_mod._parse_nt("NT$0") == Decimal("0")

    def test_parse_nt_no_match(self) -> None:
        assert tipo_mod._parse_nt("3,500 yen") is None

    def test_annuity_invention_band_1_3(self) -> None:
        rows = tipo_mod._emit_annuity_rows(
            17,
            "Annuity for a granted invention patent or a granted utility model patent (1st-3rd year)",
            Decimal("2500"),
        )
        # Two right-types × 3 years = 6 large-tier rows
        assert len(rows) == 6
        years = sorted({r.year for r in rows})
        assert years == [1, 2, 3]
        assert {r.amount for r in rows} == {Decimal("2500")}

    def test_annuity_invention_open_band_caps_at_term(self) -> None:
        rows = tipo_mod._emit_annuity_rows(
            22,
            "Annuity for a granted invention patent (10th year and beyond)",
            Decimal("16000"),
        )
        # Years 10..20 for invention (20-year term)
        assert {r.year for r in rows} == set(range(10, 21))

    def test_annuity_design_open_band_caps_at_15(self) -> None:
        rows = tipo_mod._emit_annuity_rows(
            30,
            "Annuity for a granted design patent (7th year and beyond)",
            Decimal("3000"),
        )
        # Years 7..15 for design (15-year term)
        assert {r.year for r in rows} == set(range(7, 16))

    def test_annuity_with_sme_emits_both_tiers(self) -> None:
        rows = tipo_mod._emit_annuity_rows(
            17,
            "Annuity for a granted invention patent or a granted utility model patent (1st-3rd year)",
            Decimal("2500"),
            sme_amount=Decimal("1700"),
        )
        # 2 right-types × 3 years × 2 tiers = 12 rows
        assert len(rows) == 12
        from patent_client_agents.fees.models import EntityTier

        tiers = {r.tier for r in rows}
        assert tiers == {EntityTier.large, EntityTier.small}

    def test_annuity_non_match_returns_empty(self) -> None:
        # Filing fee description should not parse as annuity
        rows = tipo_mod._emit_annuity_rows(
            1,
            "(1) Filing of an invention application",
            Decimal("3500"),
        )
        assert rows == []

    def test_categorize_patent_renewal(self) -> None:
        from patent_client_agents.fees.models import FeeCategory

        cat, cond = tipo_mod._categorize_patent(
            "Annuity for a granted invention patent (1st-3rd year)"
        )
        assert cat == FeeCategory.renewal
        assert cond is None

    def test_categorize_patent_excess_claims(self) -> None:
        from patent_client_agents.fees.models import FeeCategory

        cat, cond = tipo_mod._categorize_patent(
            "(1) Additional fee for substantive examination of an invention application "
            "whose total number of claims exceed 10 (a fee of NT$800 is required for each additional claim)"
        )
        assert cat == FeeCategory.excess_claims
        assert cond is not None
        assert cond.threshold == 10
        assert cond.per_unit is True

    def test_normalize_for_match_strips_whitespace_and_case(self) -> None:
        # pypdf often breaks words mid-token; normalization should collapse
        # both pieces back to a single alphanumeric stream
        assert tipo_mod._normalize_for_match("designate d good") == "designatedgood"
        assert tipo_mod._normalize_for_match("NT$ 7,000") == "nt7000"


class TestINPIBrazilAmountAndBands:
    def test_parse_amount_plain(self) -> None:
        assert inpi_br_mod._parse_br_amount("780,00") == Decimal("780.00")

    def test_parse_amount_thousands(self) -> None:
        # Brazilian format: 1.595,00 means 1595.00 (. is thousands sep)
        assert inpi_br_mod._parse_br_amount("1.595,00") == Decimal("1595.00")
        assert inpi_br_mod._parse_br_amount("3.295,00") == Decimal("3295.00")

    def test_parse_amount_small(self) -> None:
        assert inpi_br_mod._parse_br_amount("2,80") == Decimal("2.80")

    def test_parse_amount_empty(self) -> None:
        assert inpi_br_mod._parse_br_amount("") is None

    def test_years_for_code_invention_3_to_6(self) -> None:
        assert inpi_br_mod._years_for_code("222") == [3, 4, 5, 6]

    def test_years_for_code_invention_open_band(self) -> None:
        # Code 228: "16th year and on" for invention (cap at 20)
        assert inpi_br_mod._years_for_code("228") == [16, 17, 18, 19, 20]

    def test_years_for_code_utility_model_open_band(self) -> None:
        # Code 246: "11th year and on" for utility model (cap at 15)
        assert inpi_br_mod._years_for_code("246") == [11, 12, 13, 14, 15]

    def test_years_for_code_non_annuity_empty(self) -> None:
        # Code 202 is publication-in-advance, not an annuity
        assert inpi_br_mod._years_for_code("202") == []

    def test_is_year_excludes_real_years(self) -> None:
        assert inpi_br_mod._is_year("2019") is True
        assert inpi_br_mod._is_year("2025") is True
        assert inpi_br_mod._is_year("1996") is True
        assert inpi_br_mod._is_year("222") is False  # real code
        assert inpi_br_mod._is_year("3018") is False  # code, not year (out of range)

    def test_categorize_patent_renewal(self) -> None:
        cat, cond = inpi_br_mod._categorize_patent("222", "from the 3rd to the 6th year")
        assert cat == FeeCategory.renewal
        assert cond is None

    def test_categorize_patent_grant(self) -> None:
        cat, _ = inpi_br_mod._categorize_patent("212", "within the regular term")
        assert cat == FeeCategory.grant

    def test_categorize_patent_appeal(self) -> None:
        cat, _ = inpi_br_mod._categorize_patent("214", "Appeal for a patent of invention")
        assert cat == FeeCategory.appeal

    def test_detect_per_class_trademark(self) -> None:
        cond = inpi_br_mod._detect_per_class("Opposition – amount per class")
        assert cond is not None
        assert cond.threshold == 1
        assert cond.per_unit is True

    def test_detect_per_class_no_match(self) -> None:
        assert inpi_br_mod._detect_per_class("Submission of documents") is None
