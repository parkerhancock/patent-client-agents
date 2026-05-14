"""Scrape UKIPO's Manual of Patent Practice (MoPP) and emit a queryable
SQLite/FTS5 corpus.

Console-script entry point for ``patent-client-agents-build-mopp-corpus``.
Fetches the gov.uk MoPP index, enumerates all section pages (~190 across
PA 1977 sections + appendices + glossary), and writes each page as one
row in the corpus.

Run manually for an interactive refresh::

    patent-client-agents-build-mopp-corpus \\
        --output ~/.cache/patent_client_agents/mopp.db

For cloud deploys, build in the image and point ``MOPP_CORPUS_PATH``
at the output path. UKIPO refreshes MoPP quarterly; rebuild on the
same cadence.

Source: ``https://www.gov.uk/guidance/manual-of-patent-practice-mopp``.
OGL v3.0 (Open Government Licence). No auth.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lxml import html

from law_tools_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.gov.uk"
INDEX_PATH = "/guidance/manual-of-patent-practice-mopp"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

# Slug examples we need to recognize a section number from:
#   /guidance/manual-of-patent-practice-mopp/section-1-patentability     -> 1
#   /guidance/manual-of-patent-practice-mopp/section-14-the-application  -> 14
#   /guidance/manual-of-patent-practice-mopp/section-100-burden-of-proof -> 100
#   /guidance/manual-of-patent-practice-mopp/-section-4a-methods-...     -> 4A
# Non-section slugs ("table-of-cases", "glossary-of-terms-...") yield None.
_SECTION_SLUG_RE = re.compile(
    r"-?section-(?P<num>\d+[a-z]?)(?:-|$)",
    re.IGNORECASE,
)


def _slug_to_section_number(slug: str) -> str | None:
    m = _SECTION_SLUG_RE.search(slug)
    return m.group("num").upper() if m else None


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    retryer = default_retryer()
    async for attempt in retryer:
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    raise RuntimeError("unreachable: default_retryer reraises")


def _enumerate_section_paths(index_html: str) -> list[str]:
    """Pull every per-section href off the MoPP landing page.

    Returns a sorted, de-duplicated list of paths relative to the
    gov.uk root (e.g. ``/guidance/manual-of-patent-practice-mopp/section-1-patentability``).
    """
    pattern = re.compile(r'href="(/guidance/manual-of-patent-practice-mopp/[^"#?]+)"')
    found = pattern.findall(index_html)
    # Exclude the landing page itself.
    return sorted({p for p in found if p != INDEX_PATH})


def _extract_main_content(page_html: str) -> tuple[str, str, str | None]:
    """Pull the rendered MoPP section body out of a gov.uk page.

    Returns (html_fragment, plain_text, page_title). gov.uk wraps the
    section body in a ``<main>`` element; the page-specific title sits
    at the start of the body text (the H1 on every MoPP page is the
    constant "Manual of Patent Practice", which isn't useful).
    """
    tree = html.fromstring(page_html)
    mains = tree.xpath("//main")
    if not mains:
        return "", "", None
    main = mains[0]
    # Strip page-level chrome that bleeds into <main> on gov.uk
    # (search forms, contact-us boxes, footer navigation).
    for sel in (
        ".//form",
        './/div[contains(@class, "gem-c-contextual-sidebar")]',
        './/div[contains(@class, "gem-c-feedback")]',
        './/div[contains(@class, "gem-c-share-links")]',
    ):
        for node in main.xpath(sel):
            node.getparent().remove(node)
    html_fragment = html.tostring(main, encoding="unicode")
    text = _normalize_whitespace(main.text_content())
    # The page-specific title is the first H2 (e.g. "Section 1: Patentability"),
    # because every MoPP page reuses the same H1.
    title = None
    h2 = main.xpath(".//h2")
    if h2:
        title = _normalize_whitespace(h2[0].text_content()) or None
    return html_fragment, text, title


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _slug_to_title(slug: str) -> str:
    """Best-effort title from the URL slug when the page has no H2.

    ``section-14-the-application`` -> "Section 14: The application"
    ``glossary-of-terms-and-abbreviations`` -> "Glossary of terms and abbreviations"
    """
    cleaned = slug.lstrip("-").replace("-", " ")
    m = re.match(r"section\s+(\S+)\s+(.+)", cleaned, re.IGNORECASE)
    if m:
        return f"Section {m.group(1).upper()}: {m.group(2).strip()}"
    return cleaned[:1].upper() + cleaned[1:]


async def build_corpus(
    output_path: Path,
    *,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.5,
    limit: int | None = None,
) -> int:
    """Scrape MoPP into ``output_path`` and return the row count.

    ``pause`` is the inter-request delay in seconds (default 0.5 s);
    keep it polite — UKIPO doesn't publish a rate limit but the rest
    of gov.uk does cap automated traffic. ``limit`` (if set) processes
    only the first N pages — useful for testing the wiring.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Build into a temp path first so a half-finished crawl doesn't
    # corrupt an existing corpus.
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    headers = {"User-Agent": user_agent, "Accept": "text/html"}
    async with httpx.AsyncClient(
        base_url=base_url, headers=headers, timeout=httpx.Timeout(30.0, connect=10.0)
    ) as client:
        logger.info("Fetching MoPP index from %s%s", base_url, INDEX_PATH)
        index_html = await _fetch(client, INDEX_PATH)
        paths = _enumerate_section_paths(index_html)
        if limit:
            paths = paths[:limit]
        logger.info("Found %d section pages", len(paths))

        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("source", f"{base_url}{INDEX_PATH}"),
            )
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("snapshot_date", datetime.now(UTC).strftime("%Y-%m-%d")),
            )

            rows = 0
            for i, path in enumerate(paths, 1):
                page_html = await _fetch(client, path)
                html_fragment, text, page_title = _extract_main_content(page_html)
                if not text:
                    logger.warning("Empty body for %s — skipping", path)
                    continue
                slug = path.rsplit("/", 1)[-1]
                section_number = _slug_to_section_number(slug)
                title = page_title or _slug_to_title(slug)
                conn.execute(
                    "INSERT OR REPLACE INTO sections "
                    "(href, section_number, title, breadcrumb, chapter, html, text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        slug,
                        section_number,
                        title,
                        None,
                        None,
                        html_fragment,
                        text,
                    ),
                )
                rows += 1
                if i % 10 == 0 or i == len(paths):
                    logger.info("  %d/%d  %s", i, len(paths), slug)
                if pause:
                    await asyncio.sleep(pause)
            conn.commit()
        finally:
            conn.close()

    if output_path.exists():
        output_path.unlink()
    tmp_path.rename(output_path)
    logger.info("Wrote %d sections to %s", rows, output_path)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a UKIPO MoPP SQLite/FTS5 corpus from gov.uk."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "mopp.db",
        help="Path to write the corpus to (default: ~/.cache/patent_client_agents/mopp.db)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Override gov.uk base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent to send.",
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=0.5,
        help="Inter-request delay in seconds (default 0.5).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N section pages (for testing).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable INFO logging.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        count = asyncio.run(
            build_corpus(
                args.output,
                base_url=args.base_url,
                user_agent=args.user_agent,
                pause=args.pause,
                limit=args.limit,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 — CLI top-level boundary
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {count} sections to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
