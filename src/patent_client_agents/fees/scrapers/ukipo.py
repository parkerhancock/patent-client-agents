"""UKIPO fee-schedule scrapers (patents + trademarks).

UKIPO doesn't publish a single consolidated fee schedule page. Instead
each individual form has its own gov.uk publication page that lists
the fee amount (£) in a ``<h3 id="cost">Cost</h3>`` section.

* **Patents** — https://www.gov.uk/government/publications/patent-forms-and-fees
  A table on the main page lists every form (number, title, revision
  date). The form title is a link to the per-form sub-page (e.g.,
  ``/publications/payment-of-renewal-fee``). The scraper fetches every
  sub-page in parallel (bounded concurrency) and extracts the £-amount.

* **Trademarks** — https://www.gov.uk/government/publications/trade-mark-forms-and-fees
  The "/trade-mark-forms-and-fees/trade-mark-forms-and-fees" detail
  page has 17 inline fee tables (Form | Title | Cost), so no fan-out
  is needed for TM.

Fees revised 2026-04-01 (UKIPO's first fee increase in years; ~25%
average rise). All amounts in GBP.

v1 GAP for patents: the renewal-fee sub-page publishes a *range*
("£90 - £810 dependent how long since patent was granted") rather than
the per-year breakdown. The per-year schedule lives in The Patents
(Fees) Rules 2007 (statutory instrument). The scraper emits a single
renewal row with the range as a label; per-year expansion ships as a
follow-up against legislation.gov.uk.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from decimal import Decimal

from lxml import html as L

from law_tools_core import BaseAsyncClient
from patent_client_agents.fees.models import (
    EntityTier,
    FeeCategory,
    FeeItem,
    FeeSchedule,
    RightType,
)

logger = logging.getLogger(__name__)

UKIPO_PATENTS_INDEX = "https://www.gov.uk/government/publications/patent-forms-and-fees"
UKIPO_PATENTS_DETAIL = (
    "https://www.gov.uk/government/publications/patent-forms-and-fees/patent-forms-and-fees"
)
UKIPO_TM_DETAIL = (
    "https://www.gov.uk/government/publications/trade-mark-forms-and-fees/trade-mark-forms-and-fees"
)


class UKIPOFeesClient(BaseAsyncClient):
    """HTTP client for gov.uk UKIPO fee pages."""

    DEFAULT_BASE_URL = "https://www.gov.uk"
    CACHE_NAME = "ukipo_fees"
    DEFAULT_TIMEOUT = 30.0
    DEFAULT_TTL_SECONDS = 7 * 24 * 3600
    HTTP2 = True

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("ttl_seconds", self.DEFAULT_TTL_SECONDS)
        kwargs.setdefault(
            "headers",
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,*/*",
            },
        )
        super().__init__(**kwargs)  # type: ignore[arg-type]

    async def fetch(self, path: str) -> str:
        r = await self._request("GET", path, context=f"ukipo {path[:40]}")
        return r.text


# ──────────────────────────────────────────────────────────────────────
# Amount parsing
# ──────────────────────────────────────────────────────────────────────

_GBP_RE = re.compile(r"£\s*(\d[\d,]*(?:\.\d+)?)")
_RANGE_RE = re.compile(r"£\s*(\d[\d,]*)\s*[-–]\s*£\s*(\d[\d,]*)")


def _parse_gbp(raw: str) -> Decimal | None:
    """Pull the first £-amount out of a text blob."""
    m = _GBP_RE.search(raw)
    if not m:
        return None
    cleaned = m.group(1).replace(",", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _parse_gbp_range(raw: str) -> tuple[Decimal, Decimal] | None:
    """Pull a '£N - £M' range; returns (low, high) or None."""
    m = _RANGE_RE.search(raw)
    if not m:
        return None
    try:
        return (
            Decimal(m.group(1).replace(",", "")),
            Decimal(m.group(2).replace(",", "")),
        )
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────
# Patent scraper
# ──────────────────────────────────────────────────────────────────────


_PATENT_TABLE_HEADINGS = [
    "Apply for a UK patent and manage patent applications",
    "Request late additions and declarations of priority",
    "Update details of the owner or the representative",
    "Renew, reinstate or restore a patent",
    "Request documents or information",
    "Request an extension of time",
    "Oppose a patent",
    "Request opinion as to the validity or infringement of a patent",
    "Apply or cancel a licence of right",
]


def _categorize_patent(heading: str, title: str) -> FeeCategory:
    """Map gov.uk patent-form context to our closed FeeCategory vocab."""
    h = (heading or "").lower()
    t = (title or "").lower()
    if "apply for" in h and "manage" in h:
        if "search and examination" in t:
            return FeeCategory.filing
        if "search" in t:
            return FeeCategory.search
        if "examination" in t:
            return FeeCategory.examination
        if "grant fee" in t:
            return FeeCategory.grant
        if "annual fee" in t or "renewal" in t:
            return FeeCategory.maintenance
        return FeeCategory.filing
    if "late additions" in h or "priority" in t:
        return FeeCategory.late_fee
    if "owner" in h or "representative" in h or "transfer" in t or "name or address" in t:
        return FeeCategory.transfer
    if "renew" in h:
        if "renewal" in t or "annual" in t:
            return FeeCategory.maintenance
        if "reinstate" in t or "restore" in t:
            return FeeCategory.petition
        return FeeCategory.maintenance
    if "documents or information" in h or "certified" in t or "uncertified" in t:
        return FeeCategory.other
    if "extension of time" in h or "extend" in t:
        return FeeCategory.extension
    if "oppose" in h or "opposition" in t:
        return FeeCategory.opposition
    if "opinion" in h or "opinion" in t:
        return FeeCategory.petition
    if "licence" in h or "licence" in t:
        return FeeCategory.transfer
    return FeeCategory.other


def _row_link_text(td: L.HtmlElement) -> tuple[str, str | None]:
    """Return (text, href) for a table cell that may contain an <a>."""
    text = re.sub(r"\s+", " ", td.text_content().strip())
    links = td.cssselect("a[href]")
    if links:
        href = links[0].get("href")
        if href and href.startswith("/"):
            href = "https://www.gov.uk" + href
        return text, href
    return text, None


def _table_section_heading(table: L.HtmlElement) -> str:
    """Walk back through siblings to find the nearest h2/h3 heading."""
    cur = table
    for _ in range(20):
        prev = cur.getprevious()
        while prev is not None:
            if prev.tag in ("h2", "h3"):
                return prev.text_content().strip()
            inner = prev.cssselect("h2, h3")
            if inner:
                return inner[-1].text_content().strip()
            prev = prev.getprevious()
        parent = cur.getparent()
        if parent is None:
            break
        cur = parent
    return ""


async def _fetch_form_pages(
    client: UKIPOFeesClient,
    rows: list[tuple[str, str, str, str]],
    concurrency: int = 5,
) -> dict[str, str]:
    """Fan out and fetch each form sub-page; return ``{path: html_text}``.

    ``rows`` are ``(heading, form_number, title, sub_url)`` tuples; we
    only need the sub_url here. Hishel handles caching so subsequent
    runs are cheap.
    """
    sem = asyncio.Semaphore(concurrency)
    out: dict[str, str] = {}

    async def fetch_one(url: str) -> None:
        if url in out:
            return
        path = url.replace("https://www.gov.uk", "")
        async with sem:
            try:
                out[url] = await client.fetch(path)
            except Exception as exc:
                logger.warning("UKIPO patent sub-page fetch failed for %s: %r", url, exc)
                out[url] = ""

    await asyncio.gather(*[fetch_one(r[3]) for r in rows if r[3]])
    return out


async def scrape_ukipo_patents() -> FeeSchedule:
    """Scrape UKIPO patent fees from the gov.uk per-form sub-pages."""
    async with UKIPOFeesClient() as client:
        index_html = await client.fetch(
            "/government/publications/patent-forms-and-fees/patent-forms-and-fees"
        )
        doc = L.fromstring(index_html)

        rows: list[tuple[str, str, str, str]] = []
        for t in doc.cssselect("table"):
            heading = _table_section_heading(t)
            for tr in t.cssselect("tr"):
                tds = tr.cssselect("td")
                if len(tds) < 2:
                    continue
                form_text, _ = _row_link_text(tds[0])
                title, sub_url = _row_link_text(tds[1])
                if not title or not sub_url:
                    continue
                rows.append((heading, form_text, title, sub_url))

        sub_pages = await _fetch_form_pages(client, rows)

    fees: list[FeeItem] = []
    seen: set[str] = set()
    for heading, form_number, title, sub_url in rows:
        html_text = sub_pages.get(sub_url, "")
        if not html_text:
            continue
        # Pull the Cost block specifically when present; falls back to first £.
        cost_block = ""
        for m in re.finditer(
            r'<h3[^>]*id=["\']cost["\'][^>]*>.*?</h3>\s*(?:<p[^>]*>(.*?)</p>)',
            html_text,
            re.DOTALL,
        ):
            cost_block = m.group(1)
            break
        cost_source = cost_block or html_text
        rng = _parse_gbp_range(cost_source)
        amount = _parse_gbp(cost_source) if rng is None else rng[1]  # use high end for ranges
        if amount is None:
            continue
        category = _categorize_patent(heading, title)
        key = f"{form_number}|{title[:60]}|{amount}"
        if key in seen:
            continue
        seen.add(key)

        label = title
        notes = (
            f"UKIPO form {form_number}; section: {heading}"
            if heading
            else f"UKIPO form {form_number}"
        )
        if rng is not None:
            notes += (
                f". Published as a range £{rng[0]}-£{rng[1]}; year-by-year "
                "schedule lives in The Patents (Fees) Rules 2007 — high end "
                "stored as the fee amount."
            )
        fees.append(
            FeeItem(
                code=f"uk-patent-form-{re.sub(r'[^A-Za-z0-9]+', '-', form_number).strip('-').lower() or 'misc'}",
                label=label[:200],
                category=category,
                rights=[RightType.patent],
                amount=amount,
                currency="GBP",
                tier=EntityTier.none,
                # For maintenance rows we need a year. Renewal range rows
                # (rng != None) store the high end (year 20) per UKIPO's
                # 5→20 year curve. Non-range maintenance rows that slip
                # through the categorizer get year=20 as a fallback;
                # ideally those rows are downgraded to `other` upstream.
                year=20 if category == FeeCategory.maintenance else None,
                condition=None,
                source_url=sub_url,
                notes=notes,
            )
        )

    if not fees:
        raise RuntimeError(
            "UKIPO patent scraper parsed zero rows — page structure may have changed"
        )

    return FeeSchedule(
        jurisdiction="GB",
        issuing_body="UK Intellectual Property Office",
        office_code="UKIPO",
        right=RightType.patent,
        currency="GBP",
        effective_date=date(2026, 4, 1),  # 2026 fee revision per UKIPO notice
        source_url=UKIPO_PATENTS_INDEX,
        statutory_basis=("Patents Act 1977; The Patents (Fees) Rules 2007 (as amended)."),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "Per-form fees scraped from gov.uk patent-forms-and-fees "
            "sub-pages. ~30 sub-pages fetched concurrently (bounded "
            "to 5). Effective 2026-04-01 (UKIPO's first major rise in "
            "years; ~25% average across patent/TM/design). "
            "v1 GAP: renewal fees are published on the form sub-page as "
            "a range (£90-£810) rather than per-year; the high end is "
            "stored. The per-year schedule lives in The Patents (Fees) "
            "Rules 2007 statutory instrument — a follow-up scraper can "
            "pull it from legislation.gov.uk."
        ),
    )


# ──────────────────────────────────────────────────────────────────────
# Trademark scraper
# ──────────────────────────────────────────────────────────────────────


def _categorize_tm(heading: str, title: str) -> FeeCategory:
    h = (heading or "").lower()
    t = (title or "").lower()
    if "apply" in h or "apply" in t:
        if "additional class" in t:
            return FeeCategory.excess_classes
        return FeeCategory.filing
    if "renew" in h or "renew" in t:
        return FeeCategory.renewal
    if "oppose" in h or "opposition" in t:
        return FeeCategory.opposition
    if "appeal" in h or "appeal" in t:
        return FeeCategory.appeal
    if "invalidat" in h or "revoke" in h or "invalidat" in t or "revoke" in t:
        return FeeCategory.cancellation
    if "rectify" in h or "rectify" in t:
        return FeeCategory.other
    if "register" in h and ("licence" in t or "assignment" in t or "transfer" in t):
        return FeeCategory.transfer
    if "name or address" in t or "owner" in t or "representative" in t:
        return FeeCategory.transfer
    if "extend" in t or "extension" in t:
        return FeeCategory.extension
    if "restore" in t or "reinstate" in t:
        return FeeCategory.petition
    if "international" in t or "madrid" in t:
        return FeeCategory.madrid
    if "fast track" in t:
        return FeeCategory.examination
    return FeeCategory.other


async def scrape_ukipo_trademarks() -> FeeSchedule:
    """Scrape UKIPO trademark fees from the gov.uk detail page (inline tables)."""
    async with UKIPOFeesClient() as client:
        html_text = await client.fetch(
            "/government/publications/trade-mark-forms-and-fees/trade-mark-forms-and-fees"
        )
    doc = L.fromstring(html_text)

    fees: list[FeeItem] = []
    seen: set[str] = set()
    for table in doc.cssselect("table"):
        heading = _table_section_heading(table)
        for tr in table.cssselect("tr"):
            cells = tr.cssselect("td")
            if len(cells) < 3:
                continue
            # The TM tables are typically: [form_number, title, cost]
            form_text = re.sub(r"\s+", " ", cells[0].text_content().strip())
            title = re.sub(r"\s+", " ", cells[1].text_content().strip())
            cost_raw = re.sub(r"\s+", " ", cells[2].text_content().strip())
            if not form_text or not title or not cost_raw:
                continue
            amount = _parse_gbp(cost_raw)
            if amount is None:
                # Some TM rows have non-£ values like "£100 per month" — capture base
                continue
            category = _categorize_tm(heading, title)
            key = f"{form_text}|{title[:60]}|{amount}"
            if key in seen:
                continue
            seen.add(key)
            fees.append(
                FeeItem(
                    code=f"uk-tm-form-{re.sub(r'[^A-Za-z0-9]+', '-', form_text).strip('-').lower() or 'misc'}",
                    label=title[:200],
                    category=category,
                    rights=[RightType.trademark],
                    amount=amount,
                    currency="GBP",
                    tier=EntityTier.none,
                    year=10 if category == FeeCategory.renewal else None,
                    condition=None,
                    source_url=UKIPO_TM_DETAIL,
                    notes=f"UKIPO TM form {form_text}; section: {heading}"
                    if heading
                    else f"UKIPO TM form {form_text}",
                )
            )

    if not fees:
        raise RuntimeError(
            "UKIPO trademark scraper parsed zero rows — page structure may have changed"
        )

    return FeeSchedule(
        jurisdiction="GB",
        issuing_body="UK Intellectual Property Office",
        office_code="UKIPO",
        right=RightType.trademark,
        currency="GBP",
        effective_date=date(2026, 4, 1),
        source_url=UKIPO_TM_DETAIL,
        statutory_basis=("Trade Marks Act 1994; Trade Marks (Fees) Rules 2008 (as amended)."),
        retrieved_at=date.today(),
        fees=fees,
        notes=(
            "UKIPO TM fees scraped from the gov.uk trade-mark-forms-and-fees "
            "detail page (17 inline tables). Effective 2026-04-01. Renewals "
            "use year=10 (UKIPO TM is a 10-year renewal cycle)."
        ),
    )


__all__ = [
    "UKIPO_PATENTS_INDEX",
    "UKIPO_TM_DETAIL",
    "UKIPOFeesClient",
    "scrape_ukipo_patents",
    "scrape_ukipo_trademarks",
]
