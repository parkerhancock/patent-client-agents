"""Tests for the HK IPD Hong Kong fee scraper.

Two layers:

* **Unit tests** of internal helpers — amount parser, route classifier,
  fragmentary-row detector, label-context joiner, year-band expander,
  dedup guard, category classifier ordering.
* **Integration tests** that drive the per-right builders against
  the cached IPD HTML pages
  (``tests/fees/fixtures/hk_ipd_{patents,trademarks,designs}_2026-05-19.html``)
  so the schedule shape is exercised without a network call.

Refresh the fixtures by re-fetching the three URLs:

    https://www.ipd.gov.hk/en/patents/forms-and-fees/index.html
    https://www.ipd.gov.hk/en/trade-marks/forms-and-fees/index.html
    https://www.ipd.gov.hk/en/designs/forms-and-fees/index.html
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
from patent_client_agents.fees.scrapers import hk_ipd

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PATENT_FIXTURE = FIXTURE_DIR / "hk_ipd_patents_2026-05-19.html"
TM_FIXTURE = FIXTURE_DIR / "hk_ipd_trademarks_2026-05-19.html"
DESIGN_FIXTURE = FIXTURE_DIR / "hk_ipd_designs_2026-05-19.html"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseMoney:
    def test_plain_dollar_amount(self) -> None:
        assert hk_ipd._parse_money("$345") == Decimal("345")

    def test_thousands_separator(self) -> None:
        assert hk_ipd._parse_money("$4,413") == Decimal("4413")
        assert hk_ipd._parse_money("$1,080") == Decimal("1080")

    def test_nil_is_zero(self) -> None:
        # "Nil" cells map to Decimal('0') — model permits amount=0.
        assert hk_ipd._parse_money("Nil") == Decimal("0")
        assert hk_ipd._parse_money("nil") == Decimal("0")

    def test_per_page_extracts_first_amount(self) -> None:
        # "$6 per page" → 6 (the per-unit hint is encoded separately).
        assert hk_ipd._parse_money("$6 per page") == Decimal("6")

    def test_late_renewal_parenthetical(self) -> None:
        # TM renewal cell mashes the main fee + (Late renewal charge: $500).
        # We capture the FIRST dollar amount as the fee; late-charge moves
        # into FeeItem.notes via the parenthetical regex.
        assert hk_ipd._parse_money("$2,670(Late renewal charge: $500)") == Decimal("2670")

    def test_empty_returns_none(self) -> None:
        assert hk_ipd._parse_money("") is None

    def test_garbage_returns_none(self) -> None:
        assert hk_ipd._parse_money("not-an-amount") is None


class TestClassifyPatentRoute:
    def test_ogp_tag(self) -> None:
        assert hk_ipd._classify_patent_route("Request for grant of a standard patent (O)") == "ogp"

    def test_rr_tag(self) -> None:
        assert hk_ipd._classify_patent_route(
            "Request to record a designated patent application for a standard patent (R)"
        ) == "rr"

    def test_short_term_patent(self) -> None:
        assert hk_ipd._classify_patent_route("Request for grant of a short-term patent") == "stp"

    def test_no_tag_is_gen(self) -> None:
        assert hk_ipd._classify_patent_route("Advertisement fee") == "gen"

    def test_ogp_wins_over_short_term_when_both_appear(self) -> None:
        # Defensive: if both somehow appear in joined text, (O) takes
        # precedence because the row-level tag is more specific than
        # section-context.
        assert hk_ipd._classify_patent_route("(O) ... short-term patent") == "ogp"


class TestFragmentary:
    def test_year_band_is_fragmentary(self) -> None:
        assert hk_ipd._is_fragmentary("4th to 10th year of the 20-year term")

    def test_single_year_ordinal_is_fragmentary(self) -> None:
        assert hk_ipd._is_fragmentary("2nd 5-year extension")
        assert hk_ipd._is_fragmentary("4th 5-year extension")

    def test_for_the_first_is_fragmentary(self) -> None:
        assert hk_ipd._is_fragmentary(
            "For the first article to which the first design is to be applied"
        )

    def test_for_each_other_is_fragmentary(self) -> None:
        assert hk_ipd._is_fragmentary(
            "For each other article to which any of the designs is to be applied"
        )

    def test_complete_sentence_is_not_fragmentary(self) -> None:
        assert not hk_ipd._is_fragmentary("Renewal of a short-term patent")
        assert not hk_ipd._is_fragmentary("Additional fee for late payment of a renewal fee")
        assert not hk_ipd._is_fragmentary("Application for maintenance for a further year")


class TestLabelWithContext:
    def test_fragmentary_inherits_prefix(self) -> None:
        label = hk_ipd._label_with_context(
            "4th to 10th year of the 20-year term",
            "Request for renewal of a standard patent for a further year after the expiry of the 3rd year",
        )
        assert label.startswith("Request for renewal of a standard patent")
        assert "4th to 10th year" in label

    def test_self_contained_keeps_own_text(self) -> None:
        # "Renewal of a short-term patent" stands alone — must NOT inherit
        # the unrelated section prefix.
        label = hk_ipd._label_with_context(
            "Renewal of a short-term patent",
            "Request for renewal of a standard patent for a further year after the expiry of the 3rd year",
        )
        assert label == "Renewal of a short-term patent"

    def test_no_context_returns_description_unchanged(self) -> None:
        assert hk_ipd._label_with_context("Advertisement fee", None) == "Advertisement fee"


class TestRenewalYears:
    def test_year_band_expands(self) -> None:
        assert hk_ipd._renewal_years("4th to 10th year of the 20-year term") == [
            4, 5, 6, 7, 8, 9, 10
        ]

    def test_year_band_11_to_15(self) -> None:
        assert hk_ipd._renewal_years("11th to 15th year of the 20-year term") == [
            11, 12, 13, 14, 15
        ]

    def test_year_band_16_to_20(self) -> None:
        assert hk_ipd._renewal_years("16th to 20th year of the 20-year term") == [
            16, 17, 18, 19, 20
        ]

    def test_single_year_ordinal(self) -> None:
        assert hk_ipd._renewal_years(
            "Application for maintenance for a further year after the expiry of the 5th year"
        ) == [5]

    def test_no_year_returns_empty(self) -> None:
        assert hk_ipd._renewal_years("Renewal of a short-term patent") == []


class TestIsDuplicate:
    def test_first_call_records_and_returns_false(self) -> None:
        seen: set = set()
        assert not hk_ipd._is_duplicate(
            "Advertisement fee", Decimal("68"), FeeCategory.publication, None, seen
        )
        assert len(seen) == 1

    def test_identical_repeat_returns_true(self) -> None:
        seen: set = set()
        hk_ipd._is_duplicate(
            "Advertisement fee", Decimal("68"), FeeCategory.publication, None, seen
        )
        assert hk_ipd._is_duplicate(
            "Advertisement fee", Decimal("68"), FeeCategory.publication, None, seen
        )

    def test_different_year_is_not_duplicate(self) -> None:
        seen: set = set()
        hk_ipd._is_duplicate("Renewal", Decimal("450"), FeeCategory.renewal, 4, seen)
        # year=5 is a distinct FeeItem.
        assert not hk_ipd._is_duplicate(
            "Renewal", Decimal("450"), FeeCategory.renewal, 5, seen
        )


class TestCategorizers:
    """Each categorizer must check late_fee BEFORE renewal — otherwise
    rows like "Additional fee for late payment of a renewal fee" are
    miscategorized as renewal and fail the year-required validator.
    """

    def test_patent_late_fee_beats_renewal(self) -> None:
        assert hk_ipd._categorize_patent(
            "Additional fee for late payment of a renewal fee of a standard patent"
        ) == FeeCategory.late_fee

    def test_patent_renewal_fires_when_no_late_keyword(self) -> None:
        assert hk_ipd._categorize_patent(
            "Request for renewal of a standard patent for a further year after the expiry of the 3rd year"
        ) == FeeCategory.renewal

    def test_patent_substantive_examination(self) -> None:
        assert hk_ipd._categorize_patent(
            "Request for substantive examination of a standard patent (O) application"
        ) == FeeCategory.examination

    def test_patent_advertisement_is_publication(self) -> None:
        assert hk_ipd._categorize_patent("Advertisement fee") == FeeCategory.publication

    def test_patent_grant_route_o(self) -> None:
        assert hk_ipd._categorize_patent(
            "Request for grant of a standard patent (O)"
        ) == FeeCategory.grant

    def test_patent_grant_route_r(self) -> None:
        assert hk_ipd._categorize_patent(
            "Request for registration of a designated patent and grant of a standard patent (R)"
        ) == FeeCategory.grant

    def test_trademark_late_renewal_beats_renewal(self) -> None:
        assert hk_ipd._categorize_trademark(
            "Late renewal of a trade mark registration"
        ) == FeeCategory.late_fee

    def test_trademark_application_is_filing(self) -> None:
        assert hk_ipd._categorize_trademark(
            "Application for registration of a trade mark (including certification mark and collective mark)"
        ) == FeeCategory.filing

    def test_design_late_payment_beats_renewal(self) -> None:
        # Design row "Additional fee for late payment of renewal fee" must
        # not get pulled into the renewal branch.
        assert hk_ipd._categorize_design(
            "Additional fee for late payment of renewal fee"
        ) == FeeCategory.late_fee

    def test_design_5year_extension_is_renewal(self) -> None:
        assert hk_ipd._categorize_design("2nd 5-year extension") == FeeCategory.renewal


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
        fees = hk_ipd._build_patent_fees(patent_doc)
        # 32 source tables × dedup → ~75-80 FeeItems after expanding the
        # OGP renewal year-bands (years 4-20 across 3 bands) and the
        # short-term renewal pair (years 4 and 8).
        assert len(fees) >= 70

    def test_all_three_routes_present(self, patent_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_patent_fees(patent_doc)
        routes = {f.code.split("-")[2] for f in fees if f.code.startswith("hk-pat-")}
        # OGP + RR + STP + gen (procedural rows that apply across routes).
        assert "ogp" in routes
        assert "rr" in routes
        assert "stp" in routes
        assert "gen" in routes

    def test_ogp_grant_efiling_amount(self, patent_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_patent_fees(patent_doc)
        ogp_grant = [
            f for f in fees
            if f.code.startswith("hk-pat-ogp-request-for-grant-of-a-standard-patent")
            and f.category == FeeCategory.grant
            and f.condition is None
        ]
        assert len(ogp_grant) == 1
        # IPD page: "$345" e-filing rate on Request for grant of a
        # standard patent (O).
        assert ogp_grant[0].amount == Decimal("345")

    def test_ogp_grant_paper_amount(self, patent_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_patent_fees(patent_doc)
        paper = [
            f for f in fees
            if "request-for-grant-of-a-standard-patent" in f.code
            and f.code.startswith("hk-pat-ogp-")
            and f.condition is not None
            and f.condition.trigger == ConditionalTrigger.paper_filing
        ]
        assert len(paper) == 1
        # Paper-filing rate is $480 for OGP grant.
        assert paper[0].amount == Decimal("480")

    def test_rr_grant_amount(self, patent_doc: L.HtmlElement) -> None:
        # Re-registration grant ("Request for registration of a designated
        # patent and grant of a standard patent (R)") is $275 e-filing,
        # $380 paper.
        fees = hk_ipd._build_patent_fees(patent_doc)
        rr_grant_efiling = [
            f for f in fees
            if f.code.startswith("hk-pat-rr-request-for-registration-of-a-designated")
            and f.condition is None
        ]
        assert len(rr_grant_efiling) == 1
        assert rr_grant_efiling[0].amount == Decimal("275")

    def test_substantive_examination_amount(self, patent_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_patent_fees(patent_doc)
        exam = [
            f for f in fees
            if f.category == FeeCategory.examination
            and "substantive examination" in f.label.lower()
            and "short-term" not in f.label.lower()
        ]
        assert len(exam) >= 1
        # Substantive examination of an OGP standard patent: $4,000.
        assert any(f.amount == Decimal("4000") for f in exam)

    def test_ogp_renewal_year_band_complete(self, patent_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_patent_fees(patent_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal and f.year is not None]
        # Standard-patent renewals expand across years 4-20.
        years_at_450 = {f.year for f in renewals if f.amount == Decimal("450")}
        years_at_620 = {f.year for f in renewals if f.amount == Decimal("620")}
        years_at_850 = {f.year for f in renewals if f.amount == Decimal("850")}
        assert years_at_450 == {4, 5, 6, 7, 8, 9, 10}
        assert years_at_620 == {11, 12, 13, 14, 15}
        assert years_at_850 == {16, 17, 18, 19, 20}

    def test_short_term_renewal_only_at_y4_and_y8(self, patent_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_patent_fees(patent_doc)
        stp_renewals = [
            f for f in fees
            if f.category == FeeCategory.renewal
            and "short-term patent" in f.label.lower()
            and f.amount == Decimal("1080")
        ]
        years = sorted(f.year for f in stp_renewals if f.year is not None)
        assert years == [4, 8]

    def test_advertisement_fee_deduplicated(self, patent_doc: L.HtmlElement) -> None:
        # "Advertisement fee" $68 appears in tables 0, 12, 13, 14 (OGP /
        # RR-record / RR-grant / STP filing) but should collapse to one
        # FeeItem.
        fees = hk_ipd._build_patent_fees(patent_doc)
        adverts = [
            f for f in fees
            if f.label == "Advertisement fee" and f.amount == Decimal("68")
        ]
        assert len(adverts) == 1

    def test_zero_amount_rows_emit(self, patent_doc: L.HtmlElement) -> None:
        # "Nil" cells parse to amount=0; the FeeItem model permits this
        # (ge=Decimal('0')).
        fees = hk_ipd._build_patent_fees(patent_doc)
        nils = [f for f in fees if f.amount == Decimal("0")]
        assert len(nils) > 0


class TestBuildTrademarkFees:
    def test_yields_substantial_schedule(self, trademark_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_trademark_fees(trademark_doc)
        assert len(fees) >= 30

    def test_first_class_filing_fee(self, trademark_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_trademark_fees(trademark_doc)
        # Application for registration of a trade mark (1st class): $2,000.
        filings = [
            f for f in fees
            if f.category == FeeCategory.filing
            and "registration of a trade mark" in f.label.lower()
            and "additional class" not in f.label.lower()
        ]
        assert len(filings) >= 1
        assert any(f.amount == Decimal("2000") for f in filings)

    def test_per_additional_class_surcharge(self, trademark_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_trademark_fees(trademark_doc)
        addl = [
            f for f in fees
            if f.category == FeeCategory.excess_classes
            and "additional class" in f.label.lower()
        ]
        assert len(addl) >= 3
        # $1,000 per additional class on the canonical TM registration row.
        canonical = [f for f in addl if f.amount == Decimal("1000")]
        assert canonical, "expected at least one $1,000/class entry"
        cond = canonical[0].condition
        assert cond is not None
        assert cond.trigger == ConditionalTrigger.classes_over
        assert cond.threshold == 1
        assert cond.per_unit is True

    def test_renewal_carries_year_10(self, trademark_doc: L.HtmlElement) -> None:
        # HK TM term is 10 years (Cap. 559 s.49); the renewal FeeItem
        # must carry year=10 to satisfy the renewal validator.
        fees = hk_ipd._build_trademark_fees(trademark_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        assert renewals
        assert all(f.year == 10 for f in renewals)
        # "Request for renewal of a trade mark registration" base fee:
        # $2,670.
        base = [f for f in renewals if f.amount == Decimal("2670")]
        assert base, "expected $2,670 renewal row"

    def test_late_renewal_charge_in_notes(self, trademark_doc: L.HtmlElement) -> None:
        # The "(Late renewal charge: $500)" parenthetical lifts into notes
        # rather than emitting a standalone late_fee row.
        fees = hk_ipd._build_trademark_fees(trademark_doc)
        renewals_with_note = [
            f for f in fees
            if f.category == FeeCategory.renewal
            and f.notes is not None
            and "Late renewal" in f.notes
        ]
        assert renewals_with_note

    def test_no_design_or_patent_codes_leak(self, trademark_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_trademark_fees(trademark_doc)
        for f in fees:
            assert f.code.startswith("hk-tm-")
            assert RightType.trademark in f.rights


class TestBuildDesignFees:
    def test_yields_schedule(self, design_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_design_fees(design_doc)
        assert len(fees) >= 30

    def test_single_design_efiling_amount(self, design_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_design_fees(design_doc)
        # "1 design for articles not forming a set of articles": $235
        # e-filing, $315 paper.
        efiling = [
            f for f in fees
            if "1 design for articles not forming a set" in f.label
            and f.condition is None
            and f.category == FeeCategory.filing
        ]
        assert len(efiling) == 1
        assert efiling[0].amount == Decimal("235")

    def test_single_design_paper_filing_amount(self, design_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_design_fees(design_doc)
        paper = [
            f for f in fees
            if "1 design for articles not forming a set" in f.label
            and f.condition is not None
            and f.condition.trigger == ConditionalTrigger.paper_filing
        ]
        assert len(paper) == 1
        assert paper[0].amount == Decimal("315")

    def test_renewal_years_10_15_20_25(self, design_doc: L.HtmlElement) -> None:
        fees = hk_ipd._build_design_fees(design_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        years = sorted({f.year for f in renewals if f.year is not None})
        # 1st 5-year extension → year=10, 2nd → 15, 3rd → 20, 4th → 25.
        assert years == [10, 15, 20, 25]
        # Spot-check the 1st extension fee: $475.
        first_ext = [f for f in renewals if f.year == 10]
        assert any(f.amount == Decimal("475") for f in first_ext)


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
    async def fake_fetch(self: hk_ipd.HKIPDFeesClient, right: str) -> str:
        return _FIXTURE_BY_RIGHT[right].read_text()

    monkeypatch.setattr(hk_ipd.HKIPDFeesClient, "fetch_html", fake_fetch)


@pytest.mark.asyncio
async def test_scrape_hk_patents_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await hk_ipd.scrape_hk_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "HK"
    assert schedule.office_code == "HKIPD"
    assert schedule.right == RightType.patent
    assert schedule.currency == "HKD"
    assert schedule.source_url == hk_ipd.HK_IPD_PATENTS_URL
    assert schedule.statutory_basis is not None
    assert "Cap. 514C" in schedule.statutory_basis
    assert len(schedule.fees) >= 70
    assert schedule.key == "HK/HKIPD/patent"


@pytest.mark.asyncio
async def test_scrape_hk_trademarks_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await hk_ipd.scrape_hk_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "HKD"
    assert "Cap. 559A" in (schedule.statutory_basis or "")
    assert len(schedule.fees) >= 30


@pytest.mark.asyncio
async def test_scrape_hk_designs_returns_valid_schedule(patch_fetch: None) -> None:
    schedule = await hk_ipd.scrape_hk_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "HKD"
    assert "Cap. 522A" in (schedule.statutory_basis or "")
    assert len(schedule.fees) >= 30


@pytest.mark.asyncio
async def test_scrape_hk_patents_dedupes_advertisement_fee(patch_fetch: None) -> None:
    """End-to-end: the 4 identical "Advertisement fee" rows collapse to one."""
    schedule = await hk_ipd.scrape_hk_patents()
    adverts = [
        f for f in schedule.fees
        if f.label == "Advertisement fee" and f.amount == Decimal("68")
    ]
    assert len(adverts) == 1


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_registry_dispatches_all_three_hk_routes() -> None:
    from patent_client_agents.fees.registry import get_scraper

    p = get_scraper("HKIPD", RightType.patent)
    tm = get_scraper("HKIPD", RightType.trademark)
    d = get_scraper("HKIPD", RightType.design)
    assert p is hk_ipd.scrape_hk_patents
    assert tm is hk_ipd.scrape_hk_trademarks
    assert d is hk_ipd.scrape_hk_designs
