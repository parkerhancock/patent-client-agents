"""Scrape eTMEP and emit a queryable SQLite/FTS5 corpus.

Console-script entry point for ``patent-client-agents-build-tmep-corpus``.
Sister script to :mod:`patent_client_agents.mpep.corpus.build` — same
crawl/parse/write structure, with three differences:

- Base URL is ``tmep.uspto.gov``.
- Section anchor ids carry the ``TMEP-NNNNdNeNNN`` prefix instead of
  MPEP's ``d0eNNN`` (subsection ids ``chNNNN_…`` are the same).
- Default seed is a chapter-root href (``TMEP-1200d1e1.html``) — eTMEP
  ``/content`` returns one full chapter per chapter-root fetch, so a
  single seed converges fast via cross-chapter ``<a>`` links.

Run manually::

    patent-client-agents-build-tmep-corpus \\
        --output ~/.cache/patent_client_agents/tmep.db
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sqlite3
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lxml import html

from law_tools_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://tmep.uspto.gov"
DEFAULT_SEED_HREF = "TMEP-1200d1e1.html"  # Chapter 1200 root (Substantive Examination)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

# Section heading: "1209.03(u) Punctuation [R-MMYYYY]" etc. Same shape
# as MPEP's regex — TMEP uses identical numbering for subsections.
_SECTION_NUMBER_RE = re.compile(
    r"""
    ^\s*
    (?P<num>
        \d{1,4}                # base number
        (?:\.\d+)?             # optional .NN subsection
        (?:\([a-z]\))?         # optional (a)
        (?:\(\d+\))?           # optional (1)
    )
    \s+
    (?P<title>.+?)
    (?:\s*\[R-[\d.]+\])?       # optional revision marker
    \s*$
    """,
    re.VERBOSE | re.DOTALL,
)
_CHAPTER_HEADING_RE = re.compile(r"^\s*Chapter\s+(\d+)\b", re.IGNORECASE)

# Anchor-id formats observed in eTMEP that mark section boundaries.
# Top-level sections use ``TMEP-NNNNdNeNNN``; subsections introduced
# later use the same ``chNNNN_…`` pattern as MPEP.
_SECTION_ID_RE = re.compile(r"^(?:TMEP-\d+d\d+e\d+|ch\d+_[\w]+)$")


@dataclass(frozen=True)
class ParsedSection:
    href: str
    section_number: str | None
    title: str | None
    chapter: str | None
    breadcrumb: str | None
    html: str
    text: str


@dataclass(frozen=True)
class ParsedPage:
    fetched_href: str
    chapter: str | None
    sections: list[ParsedSection]
    discovered_hrefs: set[str]


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _extract_chapter(tree: html.HtmlElement) -> str | None:
    for h2 in tree.xpath("//h2"):
        match = _CHAPTER_HEADING_RE.match(h2.text_content() or "")
        if match:
            return match.group(1)
    return None


def _chapter_for_section_number(section_number: str) -> str | None:
    """Derive the TMEP chapter (e.g. '1200') from a section number.

    eTMEP serves single-section ``/content`` responses without the
    chapter ``<h2>`` heading. Fall back to the leading digits, which
    are unambiguous for TMEP body content (chapters 100–1900).
    """
    head = re.match(r"^(\d+)", section_number)
    if not head:
        return None
    value = int(head.group(1))
    if value < 100 or value > 1999:
        return None
    return f"{(value // 100) * 100}"


def _find_section_container(h1: html.HtmlElement) -> html.HtmlElement | None:
    for ancestor in h1.iterancestors():
        node_id = ancestor.get("id") or ""
        if _SECTION_ID_RE.match(node_id):
            return ancestor
    return None


def _href_from_element(element: html.HtmlElement) -> str:
    node_id = element.get("id") or ""
    return f"{node_id}.html"


def _harvest_cross_links(tree: html.HtmlElement) -> set[str]:
    """Collect bare and hash-form section hrefs to feed back into the crawl.

    TMEP hrefs include hyphens (``TMEP-1200d1e8145.html``) so the
    character class admits ``-`` in addition to ``\\w``.
    """
    hrefs: set[str] = set()
    for a in tree.xpath("//a[@href]"):
        raw = a.get("href", "")
        m = re.match(r"^#?/current/([\w-]+\.html)$", raw)
        if m:
            hrefs.add(m.group(1))
            continue
        m = re.match(r"^([\w-]+\.html)$", raw)
        if m and _SECTION_ID_RE.match(m.group(1).removesuffix(".html")):
            hrefs.add(m.group(1))
    return hrefs


def parse_chapter_html(fetched_href: str, html_text: str) -> ParsedPage:
    """Split a chapter content page into per-section records."""
    tree = html.fromstring(html_text)
    chapter = _extract_chapter(tree)
    sections: list[ParsedSection] = []
    seen_hrefs: set[str] = set()

    for h1 in tree.xpath("//h1"):
        heading_text = _normalize_whitespace(h1.text_content() or "")
        match = _SECTION_NUMBER_RE.match(heading_text)
        if not match:
            continue
        container = _find_section_container(h1)
        if container is None:
            continue
        href = _href_from_element(container)
        if href in seen_hrefs:
            continue
        section_number = match.group("num")
        title = _normalize_whitespace(match.group("title"))
        resolved_chapter = chapter or _chapter_for_section_number(section_number)
        breadcrumb = (
            f"Chapter {resolved_chapter} > {section_number}" if resolved_chapter else section_number
        )
        section_html = html.tostring(container, encoding="unicode")
        section_text = _normalize_whitespace(container.text_content() or "")
        sections.append(
            ParsedSection(
                href=href,
                section_number=section_number,
                title=title,
                chapter=resolved_chapter,
                breadcrumb=breadcrumb,
                html=section_html,
                text=section_text,
            )
        )
        seen_hrefs.add(href)

    discovered = _harvest_cross_links(tree) - seen_hrefs - {fetched_href}
    return ParsedPage(
        fetched_href=fetched_href,
        chapter=chapter,
        sections=sections,
        discovered_hrefs=discovered,
    )


class TmepScraper:
    """Async crawler that fetches eTMEP chapter content pages."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        version: str = "current",
        timeout: float = 60.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._version = version
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"User-Agent": user_agent},
            timeout=httpx.Timeout(timeout, connect=10.0, read=timeout, write=timeout),
            follow_redirects=True,
        )

    async def __aenter__(self) -> TmepScraper:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def fetch(self, href: str) -> str:
        retryer = default_retryer()
        async for attempt in retryer:
            with attempt:
                response = await self._client.get(
                    "/RDMS/TMEP/content",
                    params={"version": self._version, "href": href},
                )
                response.raise_for_status()
                return response.text
        raise RuntimeError("unreachable: default_retryer reraises")

    async def crawl(
        self,
        *,
        seed_hrefs: Iterable[str],
        max_pages: int | None = None,
    ) -> list[ParsedPage]:
        """BFS-crawl from seeds, dedupping by section href.

        Same dedup discipline as the MPEP crawler — once a section's
        href has been extracted, future references to that href are
        skipped so we don't re-request the chapter that yielded it.
        """
        queue: list[str] = list(dict.fromkeys(seed_hrefs))
        fetched_inputs: set[str] = set(queue)
        extracted_outputs: set[str] = set()
        pages: list[ParsedPage] = []

        while queue:
            href = queue.pop(0)
            if max_pages is not None and len(pages) >= max_pages:
                break
            if href in extracted_outputs:
                continue
            t0 = time.monotonic()
            try:
                doc = await self.fetch(href)
            except Exception as exc:
                logger.warning("Skipping %s: %s", href, exc)
                continue
            page = parse_chapter_html(href, doc)
            elapsed = time.monotonic() - t0
            for section in page.sections:
                extracted_outputs.add(section.href)
            if page.sections:
                pages.append(page)
                logger.info(
                    "Fetched %s (chapter=%s) — %d new candidate sections, %.2fs",
                    href,
                    page.chapter or "?",
                    len(page.sections),
                    elapsed,
                )
            else:
                logger.info("Fetched %s — no sections found, %.2fs", href, elapsed)
            for new_href in page.discovered_hrefs:
                if new_href in fetched_inputs or new_href in extracted_outputs:
                    continue
                queue.append(new_href)
                fetched_inputs.add(new_href)
        return pages


def write_corpus(pages: Iterable[ParsedPage], output: Path) -> int:
    """Initialize the schema and insert section rows. Returns row count."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    try:
        conn.executescript(DDL)
        seen: set[str] = set()
        inserted = 0
        for page in pages:
            for section in page.sections:
                if section.href in seen:
                    continue
                seen.add(section.href)
                conn.execute(
                    """
                    INSERT INTO sections
                        (href, section_number, title, breadcrumb, chapter, html, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        section.href,
                        section.section_number,
                        section.title,
                        section.breadcrumb,
                        section.chapter,
                        section.html,
                        section.text,
                    ),
                )
                inserted += 1
        snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
        meta_rows = [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", snapshot_date),
            ("source_version", "current"),
            ("section_count", str(inserted)),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            meta_rows,
        )
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.close()
    return inserted


async def build_corpus(
    output: Path,
    *,
    seed_hrefs: Iterable[str],
    max_pages: int | None,
    base_url: str,
) -> int:
    async with TmepScraper(base_url=base_url) as scraper:
        pages = await scraper.crawl(seed_hrefs=seed_hrefs, max_pages=max_pages)
    return write_corpus(pages, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-build-tmep-corpus",
        description=(
            "Scrape eTMEP and emit a SQLite/FTS5 corpus consumable by the "
            "patent-client-agents TmepClient. Run periodically — output is "
            "deterministic for a given eTMEP snapshot."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to write the corpus SQLite file. Parent dirs created on demand.",
    )
    parser.add_argument(
        "--seed",
        action="append",
        default=[],
        metavar="HREF",
        help=(
            f"Seed href to begin the crawl. Defaults to {DEFAULT_SEED_HREF!r} "
            f"(Chapter 1200 root) — usually a single seed is enough because "
            f"cross-chapter links converge the BFS."
        ),
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Cap on distinct chapters fetched. Useful for smoke tests.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Override eTMEP base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log per-chapter progress to stderr.",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    seeds = args.seed or [DEFAULT_SEED_HREF]
    started = time.monotonic()
    try:
        count = asyncio.run(
            build_corpus(
                args.output,
                seed_hrefs=seeds,
                max_pages=args.max_pages,
                base_url=args.base_url,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    elapsed = time.monotonic() - started
    print(
        f"Wrote {count} sections to {args.output} in {elapsed:.1f}s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
