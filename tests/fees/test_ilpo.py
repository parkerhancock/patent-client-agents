"""Tests for the ILPO Israel fee scraper.

The connector sources from the Hebrew PDF published by the Israeli
Patent Office at ``gov.il/he/pages/ilpo-fees``. The PDF is pinned at
``tests/fees/fixtures/il_ilpo_2026.pdf`` (gazetted 2025-12-22,
effective 2026-01-01) because live re-fetching requires a
Cloudflare-clearing transport on ``gov.il`` that's outside the
standard ``httpx`` path.

Refresh the fixture by re-downloading
``https://www.gov.il/BlobFolder/news/ilpo-fees/he/news_fees-2026.pdf``
through a Cloudflare-clearing browser (Playwright + persistent
Chromium profile is the canonical pattern in this repo); update
``IL_ILPO_FEES_PDF_URL`` and ``IL_ILPO_FEES_EFFECTIVE_DATE`` in
``scrapers/ilpo.py`` if a newer schedule has been gazetted.
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
from patent_client_agents.fees.scrapers import ilpo

FIXTURE = Path(__file__).parent / "fixtures" / "il_ilpo_2026.pdf"


# ──────────────────────────────────────────────────────────────────────
# Fixture loader
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def pdf_bytes() -> bytes:
    return FIXTURE.read_bytes()


@pytest.fixture(scope="module")
def patent_schedule(pdf_bytes: bytes) -> FeeSchedule:
    return ilpo._build_patent_schedule_from_pdf(pdf_bytes)


@pytest.fixture(scope="module")
def trademark_schedule(pdf_bytes: bytes) -> FeeSchedule:
    return ilpo._build_trademark_schedule_from_pdf(pdf_bytes)


@pytest.fixture(scope="module")
def design_schedule(pdf_bytes: bytes) -> FeeSchedule:
    return ilpo._build_design_schedule_from_pdf(pdf_bytes)


# ──────────────────────────────────────────────────────────────────────
# Patent schedule
# ──────────────────────────────────────────────────────────────────────


def test_ilpo_patents_schedule_has_filing_renewal(
    patent_schedule: FeeSchedule,
) -> None:
    """The patent schedule must include filing AND multi-period renewal coverage.

    Israel's renewal model is cumulative-coverage at four checkpoints
    (years 6, 10, 14, 18) plus an optional 20-year terminal payment;
    the connector emits one FeeItem per checkpoint with the terminal
    year of coverage in ``year``.
    """
    assert patent_schedule.jurisdiction == "IL"
    assert patent_schedule.office_code == "ILPO"
    assert patent_schedule.currency == "ILS"
    assert patent_schedule.right == RightType.patent
    assert patent_schedule.key == "IL/ILPO/patent"
    assert patent_schedule.effective_date.year == 2026

    # Filing fee — Item 1 — NIS 2,402 (current 2026 amount).
    filings = [f for f in patent_schedule.fees if f.category == FeeCategory.filing]
    assert filings, "expected at least one filing FeeItem"
    full_filing = [f for f in filings if f.code == "il-pat-1" and f.tier == EntityTier.none]
    assert len(full_filing) == 1
    assert full_filing[0].amount == Decimal("2402")

    # Small-entity variant: 60% of 2,402 = 1,441.20 → rounded to 1,441.
    small_filing = [f for f in filings if f.code == "il-pat-1-small" and f.tier == EntityTier.small]
    assert len(small_filing) == 1
    assert small_filing[0].amount == Decimal("1441")
    assert small_filing[0].notes is not None
    assert "small-entity" in small_filing[0].notes.lower()

    # Renewals span the cumulative-coverage checkpoints.
    renewals = [f for f in patent_schedule.fees if f.category == FeeCategory.renewal]
    years = sorted({r.year for r in renewals if r.year is not None})
    # Years 6, 10, 14, 18, 20 from the standard schedule + PTE years 1, 2, 3.
    assert 6 in years
    assert 10 in years
    assert 14 in years
    assert 18 in years
    assert 20 in years

    # Spot-check the year-6 renewal — NIS 961 per Item 12(1).
    y6 = [r for r in renewals if r.year == 6 and r.code.startswith("il-pat-12")]
    assert y6, "expected the year-6 (cumulative years 1-6) renewal row"
    assert y6[0].amount == Decimal("961")

    # Spot-check the whole-period renewal: NIS 14,410 per Item 12(6).
    whole = [r for r in renewals if r.amount == Decimal("14410")]
    assert whole, "expected the whole-period renewal of NIS 14,410"
    assert whole[0].year == 20


def test_ilpo_patents_excess_claims_and_pages(patent_schedule: FeeSchedule) -> None:
    """Excess-claims and excess-pages thresholds match the regs.

    * Per claim from the 51st onward: NIS 616 (Item 2, national;
      Item 4, PCT-national-phase — both at the same rate).
    * Per 50 pages from the 101st onward: NIS 300 (Item 3 / Item 5).
    """
    claims = [f for f in patent_schedule.fees if f.category == FeeCategory.excess_claims]
    assert len(claims) >= 2  # national + PCT
    for c in claims:
        assert c.amount == Decimal("616")
        assert c.condition is not None
        assert c.condition.trigger == ConditionalTrigger.claims_over
        assert c.condition.threshold == 50
        assert c.condition.per_unit is True

    pages = [f for f in patent_schedule.fees if f.category == FeeCategory.excess_pages]
    assert len(pages) >= 2
    for p in pages:
        assert p.amount == Decimal("300")
        assert p.condition is not None
        assert p.condition.trigger == ConditionalTrigger.pages_over
        assert p.condition.threshold == 100


def test_ilpo_patents_isa_ipea_fees_present(patent_schedule: FeeSchedule) -> None:
    """Israel is an ISA/IPEA since 2012-06-01; the schedule includes the
    ISA search/transmittal/preliminary-examination fees (Items 14-19)."""
    isa_search = [
        f
        for f in patent_schedule.fees
        if f.code in {"il-pat-14", "il-pat-16"} and f.category == FeeCategory.search
    ]
    assert isa_search
    # ISA search fee per Reg. 6(d) is NIS 4,203.
    assert any(f.amount == Decimal("4203") for f in isa_search)


def test_ilpo_patents_statutory_basis(patent_schedule: FeeSchedule) -> None:
    sb = patent_schedule.statutory_basis or ""
    assert "Patents Law" in sb
    assert "5727-1967" in sb
    # Should also reference the regulations carrying the fee schedule.
    assert "5728-1968" in sb


def test_ilpo_patents_language_note(patent_schedule: FeeSchedule) -> None:
    """The schedule notes must call out that the source is Hebrew-only —
    English readers need to know what they're getting."""
    notes = patent_schedule.notes or ""
    assert "Hebrew" in notes


# ──────────────────────────────────────────────────────────────────────
# Trademark schedule
# ──────────────────────────────────────────────────────────────────────


def test_ilpo_trademarks_schedule_has_filing_renewal(
    trademark_schedule: FeeSchedule,
) -> None:
    """TM schedule covers filing per first class, additional class, and the
    10-year renewal cycle (Trade Marks Ordinance §32)."""
    assert trademark_schedule.right == RightType.trademark
    assert trademark_schedule.currency == "ILS"
    assert trademark_schedule.key == "IL/ILPO/trademark"

    # Filing (first class): NIS 1,904 (Item 1(a)).
    filings = [f for f in trademark_schedule.fees if f.category == FeeCategory.filing]
    assert filings
    assert any(f.amount == Decimal("1904") for f in filings)

    # Additional-class surcharge on filing: NIS 1,432 with classes_over
    # condition (Item 1(b)).
    filing_addl = [
        f
        for f in trademark_schedule.fees
        if f.category == FeeCategory.excess_classes and f.amount == Decimal("1432")
    ]
    assert filing_addl, "expected NIS 1,432 additional-class filing surcharge"
    cond = filing_addl[0].condition
    assert cond is not None
    assert cond.trigger == ConditionalTrigger.classes_over
    assert cond.threshold == 1
    assert cond.per_unit is True

    # Renewal: NIS 3,393 first class for 10-year renewal (Item 4(a)).
    renewals = [f for f in trademark_schedule.fees if f.category == FeeCategory.renewal]
    assert renewals
    base_renewal = [r for r in renewals if r.amount == Decimal("3393")]
    assert base_renewal, "expected NIS 3,393 first-class renewal row"
    assert base_renewal[0].year == 10


def test_ilpo_trademarks_madrid_fees(trademark_schedule: FeeSchedule) -> None:
    """Israel has been a Madrid Protocol member since 2010; the schedule
    publishes three Madrid handling fees, all at NIS 626 in 2026."""
    madrid = [f for f in trademark_schedule.fees if f.category == FeeCategory.madrid]
    assert len(madrid) == 3
    for m in madrid:
        assert m.amount == Decimal("626")
        assert RightType.trademark in m.rights


def test_ilpo_trademarks_statutory_basis(trademark_schedule: FeeSchedule) -> None:
    sb = trademark_schedule.statutory_basis or ""
    assert "Trade Marks Ordinance" in sb
    assert "5732-1972" in sb


# ──────────────────────────────────────────────────────────────────────
# Design schedule (modern Designs Law 5777-2017)
# ──────────────────────────────────────────────────────────────────────


def test_ilpo_designs_schedule_has_filing_renewal(
    design_schedule: FeeSchedule,
) -> None:
    """Design schedule reflects the modern Designs Law 5777-2017, which
    introduced 5-year renewal periods up to a 25-year maximum."""
    assert design_schedule.right == RightType.design
    assert design_schedule.currency == "ILS"
    assert design_schedule.key == "IL/ILPO/design"

    # Filing per design: NIS 471 (Item 1).
    full_filing = [
        f for f in design_schedule.fees if f.code == "il-des-1" and f.tier == EntityTier.none
    ]
    assert len(full_filing) == 1
    assert full_filing[0].amount == Decimal("471")

    # Small-entity (60% = NIS 283 after rounding).
    small_filing = [
        f for f in design_schedule.fees if f.code == "il-des-1-small" and f.tier == EntityTier.small
    ]
    assert len(small_filing) == 1
    assert small_filing[0].amount == Decimal("283")

    # Renewal periods at terminal years 10, 15, 20, 25 plus the
    # "all-periods" bundled option.
    renewals = [f for f in design_schedule.fees if f.category == FeeCategory.renewal]
    years = sorted({r.year for r in renewals if r.year is not None})
    assert 10 in years
    assert 15 in years
    assert 20 in years
    assert 25 in years
    # Spot-check the year-10 (first renewal period 6-10) amount: NIS 589.
    y10 = [r for r in renewals if r.year == 10]
    assert any(r.amount == Decimal("589") for r in y10)


def test_ilpo_designs_statutory_basis(design_schedule: FeeSchedule) -> None:
    """Design statute is the modern Designs Law 5777-2017, NOT the
    legacy Patents and Designs Ordinance (1924)."""
    sb = design_schedule.statutory_basis or ""
    assert "Designs Law" in sb
    assert "5777-2017" in sb
    # Make sure we're not mistakenly citing the old 1924 ordinance.
    assert "1924" not in sb


# ──────────────────────────────────────────────────────────────────────
# End-to-end scrape (network call mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_fetch(pdf_bytes: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(self: ilpo.ILPOFeesClient) -> bytes:
        return pdf_bytes

    monkeypatch.setattr(ilpo.ILPOFeesClient, "fetch_pdf", fake_fetch)


@pytest.mark.asyncio
async def test_scrape_ilpo_patents_returns_valid_schedule(
    patch_fetch: None,
) -> None:
    schedule = await ilpo.scrape_ilpo_patents()
    assert isinstance(schedule, FeeSchedule)
    assert schedule.jurisdiction == "IL"
    assert schedule.office_code == "ILPO"
    assert schedule.right == RightType.patent
    assert schedule.currency == "ILS"
    assert schedule.source_url == ilpo.IL_ILPO_FEES_PDF_URL
    assert schedule.effective_date == ilpo.IL_ILPO_FEES_EFFECTIVE_DATE
    assert len(schedule.fees) >= 30


@pytest.mark.asyncio
async def test_scrape_ilpo_trademarks_returns_valid_schedule(
    patch_fetch: None,
) -> None:
    schedule = await ilpo.scrape_ilpo_trademarks()
    assert schedule.right == RightType.trademark
    assert schedule.currency == "ILS"
    assert len(schedule.fees) >= 15


@pytest.mark.asyncio
async def test_scrape_ilpo_designs_returns_valid_schedule(
    patch_fetch: None,
) -> None:
    schedule = await ilpo.scrape_ilpo_designs()
    assert schedule.right == RightType.design
    assert schedule.currency == "ILS"
    assert len(schedule.fees) >= 15


# ──────────────────────────────────────────────────────────────────────
# Registry wiring
# ──────────────────────────────────────────────────────────────────────


def test_ilpo_all_routes_registered_in_registry() -> None:
    """All three ILPO routes (patent / TM / design) must be discoverable
    via the registry's ``get_scraper`` dispatch."""
    from patent_client_agents.fees.registry import OFFICES, get_scraper

    assert "ILPO" in OFFICES

    p = get_scraper("ILPO", RightType.patent)
    tm = get_scraper("ILPO", RightType.trademark)
    d = get_scraper("ILPO", RightType.design)
    assert p is ilpo.scrape_ilpo_patents
    assert tm is ilpo.scrape_ilpo_trademarks
    assert d is ilpo.scrape_ilpo_designs


# ──────────────────────────────────────────────────────────────────────
# Helper unit tests
# ──────────────────────────────────────────────────────────────────────


class TestIsItemStart:
    def test_top_level_item(self) -> None:
        assert ilpo._is_item_start("1. עם הגשת בקשה") == ("1", "עם הגשת בקשה")
        assert ilpo._is_item_start("12. אגרת חידוש לפי") == ("12", "אגרת חידוש לפי")

    def test_sub_letter_with_close_paren(self) -> None:
        # The PDF uses inconsistent paren closure (often "(א" not "(א)")
        # but always opens with "("; the regex permits both shapes.
        label, rest = ilpo._is_item_start("(א) לפני תום")
        assert label == "(א)"

    def test_sub_letter_no_close_paren(self) -> None:
        label, rest = ilpo._is_item_start("(ב לכל סוג טובין")
        assert label == "(ב)"

    def test_sub_number(self) -> None:
        label, rest = ilpo._is_item_start("(1) עם הגשת בקשת חידוש")
        assert label == "(1)"

    def test_continuation_line(self) -> None:
        label, rest = ilpo._is_item_start("בשקלים חדשים")
        assert label is None


class TestSliceSections:
    def test_finds_all_sections(self, pdf_bytes: bytes) -> None:
        text = ilpo._extract_pdf_text(pdf_bytes)
        sections = ilpo._slice_sections(text)
        # Must find the three sections we emit FeeSchedules for, plus
        # the cross-cutting sections (PTE / Madrid).
        for required in ("PATENT", "PAT_EXT", "TM", "MADRID", "DESIGN_NEW"):
            assert required in sections, f"missing section: {required}"
            assert len(sections[required]) > 50, f"section {required} too short"


class TestRoundNIS:
    def test_rounds_to_nearest_shekel(self) -> None:
        # 60% of 2402 = 1441.20 → rounds to 1441.
        assert ilpo._round_nis(Decimal("2402") * Decimal("0.6")) == Decimal("1441")
        # 60% of 841 = 504.60 → rounds to 505.
        assert ilpo._round_nis(Decimal("841") * Decimal("0.6")) == Decimal("505")
