"""Tests for the per-office fee parsers (pure functions; no network)."""

from __future__ import annotations

from decimal import Decimal

from patent_client_agents.fees.scrapers import cipo as cipo_mod
from patent_client_agents.fees.scrapers import cnipa as cnipa_mod
from patent_client_agents.fees.scrapers import epo as epo_mod
from patent_client_agents.fees.scrapers import euipo as euipo_mod
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
