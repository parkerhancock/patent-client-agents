"""Exact ordinary patent-renewal ladders for UKIPO and IP Australia."""

from __future__ import annotations

from decimal import Decimal

import pytest

from patent_client_agents.fees.models import (
    FeeCategory,
    RecurringFeeCoverageStatus,
)
from patent_client_agents.fees.scrapers import ipaustralia, ukipo


def test_ukipo_2026_patent_renewal_ladder_is_complete() -> None:
    fees = ukipo._patent_renewal_fees()

    assert {fee.year: fee.amount for fee in fees} == {
        5: Decimal("90"),
        6: Decimal("120"),
        7: Decimal("150"),
        8: Decimal("170"),
        9: Decimal("200"),
        10: Decimal("230"),
        11: Decimal("250"),
        12: Decimal("290"),
        13: Decimal("340"),
        14: Decimal("400"),
        15: Decimal("480"),
        16: Decimal("560"),
        17: Decimal("620"),
        18: Decimal("690"),
        19: Decimal("760"),
        20: Decimal("810"),
    }
    assert all(fee.category == FeeCategory.maintenance for fee in fees)
    assert all(fee.source_url == ukipo.UKIPO_PATENT_FEES_2026 for fee in fees)


@pytest.mark.asyncio
async def test_ukipo_schedule_replaces_published_range_with_exact_ladder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_html = """
    <html><body>
      <h2>Renew, reinstate or restore a patent</h2>
      <table><tr>
        <td>12</td>
        <td><a href="/publications/payment-of-renewal-fee">Payment of renewal fee</a></td>
      </tr><tr>
        <td>1</td>
        <td><a href="/publications/apply-for-a-patent">Apply for a patent</a></td>
      </tr></table>
    </body></html>
    """
    detail_url = "https://www.gov.uk/publications/payment-of-renewal-fee"

    async def fake_fetch(self: ukipo.UKIPOFeesClient, path: str) -> str:
        assert "patent-forms-and-fees" in path
        return index_html

    async def fake_form_pages(
        client: ukipo.UKIPOFeesClient,
        rows: list[tuple[str, str, str, str]],
        concurrency: int = 5,
    ) -> dict[str, str]:
        del client, rows, concurrency
        return {
            detail_url: '<h3 id="cost">Cost</h3><p>£90 - £810 dependent on year</p>',
            "https://www.gov.uk/publications/apply-for-a-patent": (
                '<h3 id="cost">Cost</h3><p>£100</p>'
            ),
        }

    monkeypatch.setattr(ukipo.UKIPOFeesClient, "fetch", fake_fetch)
    monkeypatch.setattr(ukipo, "_fetch_form_pages", fake_form_pages)

    schedule = await ukipo.scrape_ukipo_patents()

    recurring = [fee for fee in schedule.fees if fee.category == FeeCategory.maintenance]
    assert [fee.year for fee in recurring] == list(range(5, 21))
    assert schedule.recurring_fee_coverage.status == RecurringFeeCoverageStatus.complete
    assert "ordinary patent renewal ladder" in (schedule.recurring_fee_coverage.notes or "")


def test_australia_standard_patent_online_ordinary_ladder() -> None:
    fees = ipaustralia._standard_patent_online_renewal_fees()

    assert {fee.year: fee.amount for fee in fees} == {
        4: Decimal("300"),
        5: Decimal("315"),
        6: Decimal("345"),
        7: Decimal("380"),
        8: Decimal("420"),
        9: Decimal("465"),
        10: Decimal("540"),
        11: Decimal("645"),
        12: Decimal("780"),
        13: Decimal("945"),
        14: Decimal("1140"),
        15: Decimal("1385"),
        16: Decimal("1675"),
        17: Decimal("2010"),
        18: Decimal("2390"),
        19: Decimal("2815"),
    }
    assert all(fee.category == FeeCategory.renewal for fee in fees)
    assert all(fee.source_url == ipaustralia.IPA_RENEWAL_FEES_URL for fee in fees)


@pytest.mark.asyncio
async def test_australia_schedule_qualifies_conditional_renewal_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_html(self: ipaustralia.IPAustraliaFeesClient) -> str:
        return """
        <html><body><h3>Patent application</h3><table><tr>
          <td>Patent application</td><td>$400</td>
        </tr></table></body></html>
        """

    monkeypatch.setattr(ipaustralia.IPAustraliaFeesClient, "fetch_html", fake_fetch_html)

    schedule = await ipaustralia.scrape_ipaustralia_patents()

    renewals = [fee for fee in schedule.fees if fee.category == FeeCategory.renewal]
    assert [fee.year for fee in renewals] == list(range(4, 20))
    assert schedule.recurring_fee_coverage.status == RecurringFeeCoverageStatus.partial
    assert schedule.recurring_fee_coverage.missing_years == [20, 21, 22, 23, 24]
    coverage_notes = schedule.recurring_fee_coverage.notes or ""
    assert "Other payment channels" in coverage_notes
    assert "years 20-24" in coverage_notes
