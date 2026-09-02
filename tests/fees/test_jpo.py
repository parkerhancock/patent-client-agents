"""Tests for the JPO Japan fee scraper.

Two layers:

* **Unit tests** of helpers — yen parser, base+per-claim splitter,
  base+per-class splitter, year-band extractors, categorizers.
* **Integration tests** that drive the per-right builders against
  the cached JPO HTML fixture
  (``tests/fees/fixtures/jp_jpo_all_2026-05-20.html``).

Refresh the fixture by re-fetching:

    https://www.jpo.go.jp/e/system/process/tesuryo/hyou.html

The JPO server is sometimes slow to respond from non-Japanese
networks; the live :class:`JPOFeesClient` uses HTTP/2 and a 60s
timeout. For test-only flows, prefer the fixture.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from lxml import html as L

from patent_client_agents.fees.models import (
    ConditionalTrigger,
    FeeCategory,
    FeeSchedule,
    RightType,
)
from patent_client_agents.fees.scrapers import jpo

FIXTURE_DIR = Path(__file__).parent / "fixtures"
JPO_FIXTURE = FIXTURE_DIR / "jp_jpo_all_2026-05-20.html"


# ──────────────────────────────────────────────────────────────────────
# Unit tests
# ──────────────────────────────────────────────────────────────────────


class TestParseYen:
    def test_simple(self) -> None:
        assert jpo._parse_yen("¥14,000") == Decimal("14000")

    def test_thousands(self) -> None:
        assert jpo._parse_yen("¥138,000 + ¥4,000 per claim") == Decimal("138000")

    def test_no_amount(self) -> None:
        assert jpo._parse_yen("free") is None


class TestSplitBaseAndPerClass:
    def test_application_with_per_class(self) -> None:
        base, per = jpo._split_base_and_per_class("¥3,400 + ¥8,600 per classification")
        assert base == Decimal("3400")
        assert per == Decimal("8600")

    def test_pure_per_class(self) -> None:
        # "¥32,900 per classification" → no base, all per-class
        base, per = jpo._split_base_and_per_class("¥32,900 per classification")
        assert base is None
        assert per == Decimal("32900")

    def test_flat_fee(self) -> None:
        base, per = jpo._split_base_and_per_class("¥55,000")
        assert base == Decimal("55000")
        assert per is None

    def test_empty(self) -> None:
        base, per = jpo._split_base_and_per_class("")
        assert base is None
        assert per is None


class TestSplitBaseAndPerClaim:
    def test_examination_request(self) -> None:
        base, per = jpo._split_base_and_per_claim("¥138,000 + ¥4,000 per claim")
        assert base == Decimal("138000")
        assert per == Decimal("4000")

    def test_no_per_claim(self) -> None:
        base, per = jpo._split_base_and_per_claim("¥14,000")
        assert base == Decimal("14000")
        assert per is None


class TestDesignYearBand:
    def test_1_3_band(self) -> None:
        assert jpo._design_year_band("1-3rd year: annually,") == (1, 3)

    def test_4_15_band(self) -> None:
        assert jpo._design_year_band("4-15th year: annually,") == (4, 15)

    def test_4_20_cohort_marker(self) -> None:
        assert jpo._design_year_band("4-20th year: annually,※1") == (4, 20)

    def test_4_25_cohort_marker(self) -> None:
        assert jpo._design_year_band("4-25th year: annually,※2") == (4, 25)

    def test_no_band(self) -> None:
        assert jpo._design_year_band("Design application") is None


class TestHeadingMatches:
    def test_no_space(self) -> None:
        assert jpo._heading_matches("(3)Designs", "(3)Design")

    def test_with_space(self) -> None:
        assert jpo._heading_matches("(3) Designs", "(3) Design")

    def test_trademark(self) -> None:
        assert jpo._heading_matches("(4)Trademarks", "Trademarks")

    def test_no_match(self) -> None:
        assert not jpo._heading_matches("(1)Patents", "Trademarks")


class TestCategorizeTrademark:
    def test_filing(self) -> None:
        assert (
            jpo._categorize_trademark("1. Application", "Trademark application")
            == FeeCategory.filing
        )

    def test_registration_is_grant(self) -> None:
        assert (
            jpo._categorize_trademark("3. Annual fee / Registration fee", "Registration fee:")
            == FeeCategory.grant
        )

    def test_renewal(self) -> None:
        assert (
            jpo._categorize_trademark("3. Annual fee / Registration fee", "Renewal fee:")
            == FeeCategory.renewal
        )

    def test_opposition(self) -> None:
        assert (
            jpo._categorize_trademark("4. Opposition/ Appeal / Trial", "Opposition")
            == FeeCategory.opposition
        )

    def test_appeal(self) -> None:
        assert (
            jpo._categorize_trademark("4. Opposition/ Appeal / Trial", "Appeal")
            == FeeCategory.appeal
        )


class TestCategorizeDesign:
    def test_filing(self) -> None:
        assert jpo._categorize_design("1. Application", "Design application") == FeeCategory.filing

    def test_secret_design_is_other(self) -> None:
        assert (
            jpo._categorize_design("1. Application", "Request for secret design")
            == FeeCategory.other
        )

    def test_annuity_is_renewal(self) -> None:
        assert (
            jpo._categorize_design("3. Annual fee / Registration fee", "1-3rd year: annually,")
            == FeeCategory.renewal
        )

    def test_appeal(self) -> None:
        assert (
            jpo._categorize_design("4. Opposition/ Appeal / Trial", "Appeal") == FeeCategory.appeal
        )


# ──────────────────────────────────────────────────────────────────────
# Integration tests against the cached HTML fixture
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def jpo_doc() -> L.HtmlElement:
    return L.fromstring(JPO_FIXTURE.read_bytes())


class TestBuildPatentFees:
    def test_per_claim_component_counts_every_claim(self, jpo_doc) -> None:
        fees = jpo._build_patent_fees(jpo_doc)
        per_claim = [
            fee
            for fee in fees
            if fee.category == FeeCategory.excess_claims and fee.condition is not None
        ]

        assert per_claim
        assert all(fee.condition.threshold == 0 for fee in per_claim if fee.condition)


class TestBuildTrademarkFees:
    def test_yields_substantial_schedule(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        # Application (TM + defensive), registration (regular + defensive,
        # full + installment), renewal (regular + defensive, full +
        # installment), opposition, appeal, trial, transfer.
        assert len(fees) >= 15

    def test_trademark_application_base_and_per_class(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        base = next(f for f in fees if f.code == "jp-tm-trademark-application")
        per_class = next(f for f in fees if f.code == "jp-tm-trademark-application-per-class")
        assert base.amount == Decimal("3400")
        assert base.category == FeeCategory.filing
        assert per_class.amount == Decimal("8600")
        assert per_class.category == FeeCategory.excess_classes
        assert per_class.condition is not None
        assert per_class.condition.trigger == ConditionalTrigger.classes_over
        assert per_class.condition.threshold == 0
        assert per_class.condition.per_unit is True

    def test_registration_fee_per_class(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        reg = next(f for f in fees if f.code == "jp-tm-registration-fee")
        # "¥32,900 per classification" — per-class amount becomes the fee
        assert reg.amount == Decimal("32900")
        assert reg.category == FeeCategory.grant
        assert reg.condition is not None
        assert reg.condition.trigger == ConditionalTrigger.classes_over

    def test_renewal_fee_carries_year_10(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        renewals = [f for f in fees if f.category == FeeCategory.renewal]
        # Regular renewal + installment renewal + defensive renewal
        assert len(renewals) >= 3
        assert all(f.year == 10 for f in renewals)

    def test_renewal_full_rate(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        renewal = next(f for f in fees if f.code == "jp-tm-renewal-fee")
        assert renewal.amount == Decimal("43600")

    def test_installment_rate_exists(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        installments = [f for f in fees if "installment" in f.code]
        assert len(installments) >= 2  # registration + renewal installment
        # Registration installment is ¥17,200/class
        reg_inst = next(f for f in installments if "registration" in f.code)
        assert reg_inst.amount == Decimal("17200")

    def test_defensive_mark_application(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        defensive = [f for f in fees if "defensive" in f.code]
        # Defensive application base + per-class, registration, renewal
        assert len(defensive) >= 4
        app_base = next(
            f
            for f in defensive
            if "defensive-mark-application" in f.code and "per-class" not in f.code
        )
        assert app_base.amount == Decimal("6800")

    def test_opposition_with_per_class(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        opp = next(f for f in fees if f.code == "jp-tm-opposition")
        opp_pc = next(f for f in fees if f.code == "jp-tm-opposition-per-class")
        assert opp.amount == Decimal("3000")
        assert opp.category == FeeCategory.opposition
        assert opp_pc.amount == Decimal("8000")
        assert opp_pc.category == FeeCategory.excess_classes

    def test_transfer_of_right(self, jpo_doc) -> None:
        # The TM-specific transfer fee (¥30,000) comes from section 6
        # via the curated walker.
        fees = jpo._build_trademark_fees(jpo_doc)
        transfer = next(f for f in fees if f.code == "jp-tm-transfer-of-right")
        assert transfer.amount == Decimal("30000")
        assert transfer.category == FeeCategory.transfer

    def test_no_design_or_patent_fees_leak(self, jpo_doc) -> None:
        fees = jpo._build_trademark_fees(jpo_doc)
        for f in fees:
            assert RightType.trademark in f.rights
            # No section-5 "over the counter" fees should leak in
            assert "over the counter" not in (f.label or "").lower()
            # No patent / UM / design transfer rows should leak in
            assert f.label != "-Patents"
            assert f.label != "-Designs"
            assert f.label != "-Utility models"


class TestBuildDesignFees:
    def test_yields_schedule(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        # Application + secret design + years 1-3 + years 4-15 +
        # extension years 16-25 + appeal + trial + transfer
        # = 2 + 3 + 12 + 10 + 2 + 1 = 30
        assert len(fees) >= 25

    def test_design_application(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        app = next(f for f in fees if f.code.startswith("jp-des-design-application"))
        assert app.amount == Decimal("16000")
        assert app.category == FeeCategory.filing

    def test_secret_design_request(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        secret = next(f for f in fees if "secret-design" in f.code)
        assert secret.amount == Decimal("5100")
        assert secret.category == FeeCategory.other

    def test_year_1_3_band(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        years = sorted(
            {
                f.year
                for f in fees
                if f.category == FeeCategory.renewal and f.amount == Decimal("8500")
            }
        )
        assert 1 in years
        assert 2 in years
        assert 3 in years

    def test_year_4_15_band(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        years = sorted(
            {
                f.year
                for f in fees
                if f.category == FeeCategory.renewal
                and f.amount == Decimal("16900")
                and f.year is not None
                and f.year <= 15
            }
        )
        assert years == list(range(4, 16))

    def test_extension_to_year_25(self, jpo_doc) -> None:
        # The ※2 cohort marker (4-25th year) must expand to years 16-25
        # at the same ¥16,900 rate.
        fees = jpo._build_design_fees(jpo_doc)
        ext = sorted(
            {
                f.year
                for f in fees
                if f.category == FeeCategory.renewal
                and f.amount == Decimal("16900")
                and f.year is not None
                and f.year >= 16
            }
        )
        assert ext == list(range(16, 26))

    def test_appeal_and_trial(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        appeal = next(f for f in fees if f.code == "jp-des-appeal")
        trial = next(f for f in fees if f.code == "jp-des-trial-retrial")
        assert appeal.amount == Decimal("55000")
        assert trial.amount == Decimal("55000")

    def test_transfer_of_right(self, jpo_doc) -> None:
        # Design-specific transfer fee (¥9,000) — not the TM ¥30,000.
        fees = jpo._build_design_fees(jpo_doc)
        transfer = next(f for f in fees if f.code == "jp-des-transfer-of-right")
        assert transfer.amount == Decimal("9000")
        assert transfer.category == FeeCategory.transfer

    def test_no_trademark_or_patent_fees_leak(self, jpo_doc) -> None:
        fees = jpo._build_design_fees(jpo_doc)
        for f in fees:
            assert RightType.design in f.rights
            # No section-5 procedural rows should leak in
            assert "over the counter" not in (f.label or "").lower()


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape tests (network call patched)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    html_bytes = JPO_FIXTURE.read_bytes()

    async def fake_fetch(self: jpo.JPOFeesClient) -> bytes:
        return html_bytes

    monkeypatch.setattr(jpo.JPOFeesClient, "fetch_html", fake_fetch)


@pytest.mark.asyncio
async def test_live_xhtml_encoding_declaration_is_parsed_as_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_request(self: jpo.JPOFeesClient, *args, **kwargs) -> httpx.Response:
        content = JPO_FIXTURE.read_bytes().removeprefix(b"\xef\xbb\xbf")
        return httpx.Response(200, content=content)

    monkeypatch.setattr(jpo.JPOFeesClient, "_request", fake_request)

    schedule = await jpo.scrape_jpo_trademarks()

    assert schedule.fees


@pytest.mark.asyncio
async def test_jpo_trademarks_schedule_has_filing_and_renewal(patch_fetch: None) -> None:
    schedule = await jpo.scrape_jpo_trademarks()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "JP"
    assert schedule.office_code == "JPO"
    assert schedule.right == RightType.trademark
    assert schedule.currency == "JPY"
    assert schedule.effective_date.year == 2022
    assert schedule.source_url == jpo.JPO_FEES_URL
    assert schedule.statutory_basis is not None
    assert "Trademark Act" in schedule.statutory_basis

    # At least one filing fee and one renewal fee present
    categories = {f.category for f in schedule.fees}
    assert FeeCategory.filing in categories
    assert FeeCategory.renewal in categories
    # Sanity: real ¥ amounts
    assert all(f.amount > Decimal("0") for f in schedule.fees)
    assert all(f.currency == "JPY" for f in schedule.fees)


@pytest.mark.asyncio
async def test_jpo_designs_schedule_has_filing_and_renewal(patch_fetch: None) -> None:
    schedule = await jpo.scrape_jpo_designs()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "JP"
    assert schedule.office_code == "JPO"
    assert schedule.right == RightType.design
    assert schedule.currency == "JPY"
    assert schedule.effective_date.year == 2022
    assert schedule.source_url == jpo.JPO_FEES_URL
    assert schedule.statutory_basis is not None
    assert "Design Act" in schedule.statutory_basis

    categories = {f.category for f in schedule.fees}
    assert FeeCategory.filing in categories
    assert FeeCategory.renewal in categories
    # Renewal coverage spans years 1-25 (statutory max term).
    renewal_years = sorted(
        {f.year for f in schedule.fees if f.category == FeeCategory.renewal and f.year is not None}
    )
    assert renewal_years[0] == 1
    assert renewal_years[-1] == 25
    assert all(f.amount > Decimal("0") for f in schedule.fees)
    assert all(f.currency == "JPY" for f in schedule.fees)


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_registry_dispatches_all_three_jp_routes() -> None:
    from patent_client_agents.fees.registry import get_scraper

    p = get_scraper("JPO", RightType.patent)
    tm = get_scraper("JPO", RightType.trademark)
    d = get_scraper("JPO", RightType.design)
    assert p is jpo.scrape_jpo_patents
    assert tm is jpo.scrape_jpo_trademarks
    assert d is jpo.scrape_jpo_designs
