#!/usr/bin/env python3
"""Snapshot WIPO country IP profiles into research/wipo_profiles/{iso2}.md.

WIPO Country IP Profiles (https://www.wipo.int/en/web/country-profiles/) aggregate
per-jurisdiction reference data: WIPO membership year, treaty count, national IP
office names + location, GII ranking, plus links to WIPO Lex / statistical IP
profile PDFs / PCT eGuide / treaty filings. Useful as a starting point when we
research a new IP office to add to the canonical catalog under catalog/sources/.

The hub page (.../country-profiles/) is sat behind an AWS WAF JS challenge that
defeats plain HTTP. We use a headless Chromium via Playwright to pass the
challenge — same approach as the dev-browser skill. Each country profile is
server-rendered once the challenge is satisfied.

URL pattern: https://www.wipo.int/en/web/country-profiles/<iso2-lower>

Usage:
    # snapshot a few countries
    uv run python scripts/wipo_country_profile_snapshot.py JP US DE

    # snapshot every country (~195) — enumerated from the hub select
    uv run python scripts/wipo_country_profile_snapshot.py --all

    # overwrite existing snapshots
    uv run python scripts/wipo_country_profile_snapshot.py JP --refresh

    # tune concurrency (default 3) and output directory
    uv run python scripts/wipo_country_profile_snapshot.py --all --concurrency 5

Out of scope per CONNECTOR_STANDARDS §1: this is a research helper, not a
shipped MCP connector. It writes markdown to research/wipo_profiles/ for
grep-time use during connector research.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

HUB_URL = "https://www.wipo.int/en/web/country-profiles/"
PROFILE_URL_FMT = "https://www.wipo.int/en/web/country-profiles/{iso2_lower}"

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "research" / "wipo_profiles"

# Persistent user-data dir so the AWS WAF challenge cookie survives the run.
# WIPO sits behind a CloudFront WAF that JS-challenges new clients; once the
# cookie is set, subsequent country pages load without re-challenging.
PROFILE_DIR = REPO_ROOT / ".cache" / "wipo-playwright-profile"

STEALTH_INIT_JS = """
Object.defineProperty(navigator, 'webdriver', {
  configurable: true,
  get: () => undefined,
});
"""

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Page-level JS that runs in the browser to extract structured fields.
# Kept as plain JS because page.evaluate runs in browser context.
EXTRACT_JS = r"""
() => {
  // WIPO country pages don't always have a <main> tag — they use role="main"
  // on a wrapper <div>. Fall through to body only as last resort.
  const main =
    document.querySelector('[role="main"]') ||
    document.querySelector('main') ||
    document.body;
  const text = (el) => (el?.textContent || '').replace(/\s+/g, ' ').trim();
  const absUrl = (href) => {
    if (!href) return null;
    try { return new URL(href, location.href).href; } catch { return href; }
  };

  // Country name
  const h1 = main.querySelector('h1');
  const country = text(h1);

  // Paragraphs preceding the first <h2> — these carry the lead-summary
  // sentences ("X has been a member of WIPO since YEAR…").
  const firstH2 = main.querySelector('h2');
  const paragraphs = Array.from(main.querySelectorAll('p'))
    .filter(p => !firstH2 || p.compareDocumentPosition(firstH2) & Node.DOCUMENT_POSITION_FOLLOWING)
    .map(text).filter(Boolean);

  // Section h2/h3 outline
  const outline = Array.from(main.querySelectorAll('h2, h3'))
    .map(h => ({ tag: h.tagName.toLowerCase(), text: text(h) }))
    .filter(h => h.text);

  // All meaningful list items in main, with hrefs of first link
  const items = Array.from(main.querySelectorAll('li')).map(li => {
    const a = li.querySelector('a[href]');
    return { text: text(li), href: absUrl(a?.getAttribute('href')) };
  }).filter(x => x.text);

  // All links — used to detect canonical wipo lex / stats / GII URLs
  const links = Array.from(main.querySelectorAll('a[href]')).map(a => ({
    text: text(a),
    href: absUrl(a.getAttribute('href')),
  }));

  return { country, paragraphs, outline, items, links };
}
"""


def extract_membership_year(paragraphs: list[str]) -> str | None:
    """Pull 'has been a member of WIPO since YEAR'."""
    for p in paragraphs:
        m = re.search(r"member of WIPO since\s+(\d{4})", p)
        if m:
            return m.group(1)
    return None


def extract_treaty_count(paragraphs: list[str]) -> str | None:
    """Pull 'signatory to over N WIPO treaties'."""
    for p in paragraphs:
        m = re.search(r"(?:signatory to|party to)\s+(?:over\s+)?(\d+)\s+WIPO\s+treaties", p)
        if m:
            return m.group(1)
    return None


def extract_offices(paragraphs: list[str]) -> str | None:
    """Pull 'The national IP office[s] of X is/are Y. The office[s] is/are located in Z.'"""
    chunks = []
    for p in paragraphs:
        if re.search(r"national IP office", p, re.IGNORECASE):
            chunks.append(p)
        elif re.search(r"WIPO has an external office", p, re.IGNORECASE):
            chunks.append(p)
    return " ".join(chunks) if chunks else None


def extract_gii_rank(outline: list[dict]) -> str | None:
    """GII ranking is in an h3 like 'X ranks Nth among the M economies featured in the GII YEAR.'"""
    for h in outline:
        if h["tag"] == "h3" and re.search(r"ranks?\s+\d+", h["text"], re.IGNORECASE):
            return h["text"]
    return None


def pick_link(links: list[dict], pattern: str) -> str | None:
    """First link whose href matches the regex."""
    rx = re.compile(pattern, re.IGNORECASE)
    for ln in links:
        if ln["href"] and rx.search(ln["href"]):
            return ln["href"]
    return None


def render_markdown(iso2: str, data: dict, snapshot_url: str) -> str:
    """Render the extracted data into a focused research-time markdown file."""
    paragraphs = data["paragraphs"]
    outline = data["outline"]
    items = data["items"]
    links = data["links"]

    membership = extract_membership_year(paragraphs)
    treaties = extract_treaty_count(paragraphs)
    offices = extract_offices(paragraphs)
    gii = extract_gii_rank(outline)

    iso2_upper = iso2.upper()
    iso2_lower = iso2.lower()

    quick = [
        (
            "WIPO Lex profile",
            pick_link(links, rf"wipolex/en/members/profile/{iso2_upper}\b"),
        ),
        (
            "WIPO treaty memberships",
            pick_link(links, rf"wipolex/en/treaties/ShowResults\?code={iso2_upper}(?:&|$)"),
        ),
        (
            "Treaty notifications",
            pick_link(links, r"wipolex/en/treaties/ShowResults\?.*search_what=N"),
        ),
        (
            "Statistical IP profile (PDF)",
            pick_link(links, rf"edocs/statistics-country-profile/en/{iso2_lower}\.pdf"),
        ),
        (
            "GII 2024 ranking (PDF)",
            pick_link(links, rf"edocs/gii-ranking/2024/{iso2_lower}\.pdf"),
        ),
        (
            "PCT eGuide",
            pick_link(links, rf"pctlegal\.wipo\.int/eGuide.*doc-code={iso2_upper}\b"),
        ),
        (
            "ePCT office profile",
            pick_link(links, r"pct\.wipo\.int/ePCTExternal/pages/OfficeProfile\.xhtml"),
        ),
        (
            "Madrid System member profile",
            pick_link(links, r"madrid/memberprofiles"),
        ),
        (
            "National statements at WIPO assemblies",
            pick_link(links, rf"meetings/en/statements_country\.jsp\?country_code={iso2_upper}\b"),
        ),
        (
            "Contact information",
            pick_link(links, rf"country-profiles/contact\?code={iso2_lower}\b"),
        ),
    ]

    quick_rows = "\n".join(
        f"| {label} | {url} |" if url else f"| {label} | _(not present)_ |" for label, url in quick
    )

    # Outline items per h2 section — for grep-time use.
    # Build sections as: h2 → list of li texts (with hrefs)
    # Walk DOM order: we have outline (h2/h3 only) and items separately, so re-render
    # by scanning items and assigning under the nearest preceding h2. The browser
    # already produced both in document order.
    # For simplicity, just dump items grouped by which section heading they fall under.
    # We use the outline list to render headings and the items list flat afterwards.
    # The grep-usable bit is the flat link list below.

    items_md = []
    for it in items:
        if it["href"]:
            items_md.append(f"- [{it['text']}]({it['href']})")
        else:
            items_md.append(f"- {it['text']}")
    items_section = "\n".join(items_md) if items_md else "_(no list items extracted)_"

    outline_md = "\n".join(f"{'##' if h['tag'] == 'h2' else '###'} {h['text']}" for h in outline)

    lead_md = "\n\n".join(p for p in paragraphs if p) or "_(no lead paragraphs)_"

    timestamp = datetime.now(UTC).isoformat(timespec="seconds")

    return (
        f"# {data['country'] or iso2_upper} — WIPO Country IP Profile\n\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| ISO-2 code | `{iso2_upper}` |\n"
        f"| WIPO member since | {membership or '_(not present)_'} |\n"
        f"| WIPO treaty count | {treaties or '_(not present)_'} |\n"
        f"| GII ranking | {gii or '_(not present)_'} |\n"
        f"| National IP offices | {offices or '_(not present)_'} |\n\n"
        f"**Source:** {snapshot_url}  \n"
        f"**Snapshot:** {timestamp}\n\n"
        f"## Quick links\n\n"
        f"| Resource | URL |\n"
        f"|---|---|\n"
        f"{quick_rows}\n\n"
        f"## Lead summary (verbatim from WIPO page)\n\n"
        f"{lead_md}\n\n"
        f"## Page outline\n\n"
        f"{outline_md}\n\n"
        f"## All listed resources (grep-friendly)\n\n"
        f"{items_section}\n"
    )


async def list_all_country_codes(page: Page) -> list[str]:
    """Pull the 195 ISO-2 codes from the country-profiles hub <select>."""
    await page.goto(HUB_URL, wait_until="domcontentloaded", timeout=30_000)
    # Wait for the select to populate. Hub fully renders in ~3s in practice.
    # `state="attached"` — options inside a <select> aren't "visible" until
    # the dropdown is opened, which Playwright's default visibility check
    # would block on forever.
    await page.wait_for_selector(
        "#country_code option[value]:not([value=''])",
        timeout=15_000,
        state="attached",
    )
    codes: list[str] = await page.evaluate(
        """() => Array.from(document.querySelectorAll('#country_code option'))
                .map(o => o.value).filter(v => v && v.length === 2)"""
    )
    return [c.upper() for c in codes]


async def warm_up_waf(page: Page) -> None:
    """Visit the hub page to clear the AWS WAF JS challenge once per profile.

    The first request from a fresh profile gets HTTP 202 + a JS challenge
    page; Chromium executes the JS, sets the `aws-waf-token` cookie, then
    subsequent navigations in the same context bypass the challenge.
    """
    try:
        await page.goto(HUB_URL, wait_until="domcontentloaded", timeout=30_000)
        # Hub renders the <select id="country_code"> server-side after the
        # challenge clears. Wait for it as the readiness signal.
        await page.wait_for_selector("#country_code", timeout=20_000)
    except PlaywrightTimeoutError as exc:
        raise RuntimeError(f"WAF warm-up failed: {exc}") from exc


async def snapshot_one(
    ctx: BrowserContext, iso2: str, out_dir: Path, refresh: bool
) -> tuple[str, str]:
    """Snapshot a single country. Returns (iso2, status)."""
    iso2_upper = iso2.upper()
    iso2_lower = iso2.lower()
    out_path = out_dir / f"{iso2_lower}.md"
    if out_path.exists() and not refresh:
        return iso2_upper, "skipped (exists)"

    page = await ctx.new_page()
    url = PROFILE_URL_FMT.format(iso2_lower=iso2_lower)
    try:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        except PlaywrightTimeoutError:
            return iso2_upper, "FAIL (navigation timeout)"

        # H1 inside [role="main"] signals the country profile rendered.
        # (WIPO pages use role="main" on a wrapper <div>, not a <main> tag.)
        try:
            await page.wait_for_selector('[role="main"] h1, h1', timeout=20_000)
        except PlaywrightTimeoutError:
            return iso2_upper, "FAIL (no h1 — WAF challenge?)"

        data = await page.evaluate(EXTRACT_JS)
        if not data.get("country") and not data.get("paragraphs"):
            return iso2_upper, "FAIL (empty extraction)"

        md = render_markdown(iso2_upper, data, snapshot_url=url)
        out_path.write_text(md, encoding="utf-8")
        return iso2_upper, f"ok ({out_path.relative_to(REPO_ROOT)})"
    finally:
        await page.close()


async def _launch_context(pw: Playwright) -> BrowserContext:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ctx = await pw.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=True,
        user_agent=USER_AGENT,
        locale="en-US",
        viewport={"width": 1280, "height": 900},
    )
    await ctx.add_init_script(STEALTH_INIT_JS)
    return ctx


async def run(codes: list[str], out_dir: Path, refresh: bool, concurrency: int) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0

    async with async_playwright() as pw:
        ctx = await _launch_context(pw)
        try:
            # Warm up the WAF cookie on the hub page before fanning out.
            warmup_page = await ctx.new_page()
            try:
                print("Warming up WAF cookie via hub page…", flush=True)
                await warm_up_waf(warmup_page)
            finally:
                await warmup_page.close()

            sem = asyncio.Semaphore(concurrency)

            async def worker(c: str) -> None:
                nonlocal failed
                async with sem:
                    iso2, status = await snapshot_one(ctx, c, out_dir, refresh)
                    print(f"  {iso2}: {status}", flush=True)
                    if status.startswith("FAIL"):
                        failed += 1

            await asyncio.gather(*(worker(c) for c in codes))
        finally:
            await ctx.close()

    if failed:
        print(f"\n{failed} of {len(codes)} country profiles failed.", file=sys.stderr)
    return 1 if failed else 0


async def main_async(args: argparse.Namespace) -> int:
    if args.all:
        async with async_playwright() as pw:
            ctx = await _launch_context(pw)
            try:
                page = await ctx.new_page()
                print("Enumerating country codes from WIPO hub…", flush=True)
                codes = await list_all_country_codes(page)
                await page.close()
            finally:
                await ctx.close()
        print(f"Found {len(codes)} country codes.", flush=True)
    else:
        codes = [c.strip().upper() for c in args.codes if c.strip()]

    if not codes:
        print("No country codes specified. Pass ISO-2 codes or --all.", file=sys.stderr)
        return 2

    out_dir = (
        args.out_dir.resolve()
        if args.out_dir.is_absolute()
        else (REPO_ROOT / args.out_dir).resolve()
    )
    print(f"Writing snapshots to {out_dir.relative_to(REPO_ROOT)}/", flush=True)
    return await run(codes, out_dir, args.refresh, args.concurrency)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot WIPO Country IP Profiles into markdown for research-time use.",
    )
    parser.add_argument(
        "codes",
        nargs="*",
        help="ISO-2 country codes (e.g. JP US DE). Ignored when --all is given.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Snapshot every country code WIPO enumerates on the hub page.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Overwrite existing snapshots (default: skip).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Concurrent page fetches (default: 3).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("research/wipo_profiles"),
        help="Output directory relative to the patent-client-agents package root.",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
