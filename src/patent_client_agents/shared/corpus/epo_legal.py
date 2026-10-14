"""Client and crawler pieces shared by the corpora scraped from epo.org/en/legal.

Five packages read books published under ``www.epo.org/en/legal/<book>/<year>/``:
``epc`` (book ``epc``), ``epo_guidelines`` (``guidelines-epc``),
``epo_pct_guidelines`` (``guidelines-pct``), ``epo_up_guidelines``
(``guidelines-up``), and ``epo_case_law`` (``case-law``). They differ in
citation syntax, slug shape, and how pages are discovered; the rest is here.

- :class:`EpoLegalClient` is the outline client configured by book: href
  normalization, result URLs, the edition meta key, and the citation-first
  ``get_section`` lookup chain.
- The Guidelines for Examination (EPC) and the PCT-EPO Guidelines share a
  slug scheme (``g_ii_3_1``), citation syntax (``G-II, 3.1``), and crawl.
  :class:`EpoGuidelinesClient` and :func:`build_guidelines_corpus` take the
  book as a parameter.
- :func:`build_book_corpus` crawls a known list of slugs (EPC, UP Guidelines,
  Case Law); :func:`build_guidelines_corpus` crawls breadth-first from the
  index page.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sqlite3
from collections import deque
from collections.abc import Awaitable, Callable, Coroutine, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from lxml import html

from mcp_data_core.corpus_compression import finalize_outline_corpus
from mcp_data_core.corpus_db import OutlineCorpusDB

from .build import atomic_output, fetch_text, run_build_cli
from .outline.build import init_outline_corpus, insert_outline_section
from .outline.client import OutlineCorpusClient, ResponseT, SectionT, VersionT
from .outline.schema import OUTLINE_SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.epo.org"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)


# -- Read side -----------------------------------------------------------------


def normalize_epo_href(value: str, book: str) -> str:
    """Reduce a slug, ``/en/legal/<book>/<year>/<slug>.html`` path, or URL to the slug."""
    h = value.strip()
    if h.startswith("http"):
        h = h.split("://", 1)[1].split("/", 1)[1]
    h = h.lstrip("/")
    # Strip the date-versioned URL prefix in any of the common shapes.
    h = re.sub(rf"^(?:en/)?legal/{re.escape(book)}/\d{{4}}/", "", h)
    h = h.removesuffix(".html")
    return h.lower()


class EpoLegalClient(OutlineCorpusClient[ResponseT, SectionT, VersionT]):
    """Outline client for one epo.org/en/legal book.

    ``get_section`` first maps a citation to its slug (``_citation_to_slug``)
    and looks that up as an href, then, if ``_section_number_for_slug`` names
    one, as a ``section_number``; it falls back to the normalized href.
    """

    BOOK: str
    # Hit URLs end in ``.html`` except in the UP Guidelines.
    RESULT_SUFFIX: str = ".html"
    DEFAULT_VERSION: str
    EDITION_META_KEY: str
    VERSION_LABEL: str = "{edition} edition (snapshot {snapshot})"

    def _citation_to_slug(self, section: str) -> str | None:
        raise NotImplementedError

    def _section_number_for_slug(self, slug: str) -> str | None:
        del slug
        return None

    def _normalize_href(self, value: str) -> str:
        return normalize_epo_href(value, self.BOOK)

    def _result_url(self, href: str, edition: str | None) -> str:
        return f"{self.base_url}/en/legal/{self.BOOK}/{edition}/{href}{self.RESULT_SUFFIX}"

    def _edition(self, db: OutlineCorpusDB) -> str | None:
        return db.meta().get(self.EDITION_META_KEY, self.DEFAULT_VERSION)

    def _lookups(self, section: str) -> Iterator[tuple[str, str]]:
        slug = self._citation_to_slug(section)
        if slug:
            yield "href", slug
            section_number = self._section_number_for_slug(slug)
            if section_number:
                yield "section_number", section_number
        yield "href", self._normalize_href(section)

    def _not_found_message(self, section: str) -> str:
        return f"Could not find {self.NOT_FOUND_LABEL} section '{section}'"


# Guidelines citation forms, all mapping to the slug ``g_ii_3_1``:
#   G-II, 3.1 / G-II 3.1 / G.II.3.1 / g_ii_3_1 / G II 3.1
GUIDELINES_CITATION_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<part>[A-H])                          # Part letter
    (?:                                       # Optional chapter+section block
        [-_\s.,]+
        (?P<chapter>[IVX]+)                  # Chapter roman numeral
        (?:
            [-_\s.,]+
            (?P<section>\d+(?:[._-]\d+)*)    # Section numbers (any common separator)
        )?
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Bare slugs like ``g_ii_3_1`` or ``g_ii_3_1.html``:
GUIDELINES_SLUG_PATTERN = re.compile(
    r"^([a-h](_[ivx]+(_\d+)*)?(\.html)?|index\.html|general_part\.html)$",
    re.IGNORECASE,
)


def guidelines_citation_to_slug(text: str) -> str | None:
    """Map a citation like 'G-II, 3.1' to slug 'g_ii_3_1'.

    Returns None when the input doesn't look like a citation we can
    decode. Bare slugs (``g_ii_3_1`` etc.) round-trip through this
    function unchanged via ``_normalize_href``.
    """
    m = GUIDELINES_CITATION_PATTERN.match(text)
    if not m:
        return None
    part = m.group("part").lower()
    chapter = m.group("chapter")
    section = m.group("section")
    slug = part
    if chapter:
        slug += f"_{chapter.lower()}"
    if section:
        # Section numbers can be ``3``, ``3.1``, ``3-1``, ``3.1.4`` etc.
        normalized = re.sub(r"[.,\-]", "_", section)
        slug += "_" + normalized
    return slug


class EpoGuidelinesClient(EpoLegalClient[ResponseT, SectionT, VersionT]):
    """Client for a Guidelines book (``guidelines-epc`` or ``guidelines-pct``)."""

    EDITION_META_KEY = "guidelines_year"

    def _citation_to_slug(self, section: str) -> str | None:
        return guidelines_citation_to_slug(section)

    def _section_number_for_slug(self, slug: str) -> str | None:
        # Maybe the corpus indexed the slug as a section_number too.
        return slug


# -- Build side ----------------------------------------------------------------


def http_client(base_url: str, user_agent: str) -> httpx.AsyncClient:
    """The HTTP client the epo.org crawls use."""
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"User-Agent": user_agent, "Accept": "text/html"},
        timeout=httpx.Timeout(30.0, connect=10.0),
    )


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


MAIN_CHROME = (".//nav", ".//script", ".//style", ".//footer")


def extract_main_content(
    page_html: str, *, strip: Sequence[str] = MAIN_CHROME
) -> tuple[str, str, str | None]:
    """Return (``<main>`` HTML fragment, plain text, first H1) with ``strip`` removed."""
    tree = html.fromstring(page_html)
    mains = tree.xpath("//main")
    if not mains:
        return "", "", None
    main = mains[0]
    for sel in strip:
        for node in main.xpath(sel):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    fragment = html.tostring(main, encoding="unicode")
    text = normalize_whitespace(main.text_content())
    title = None
    h1s = main.xpath(".//h1")
    if h1s:
        title = normalize_whitespace(h1s[0].text_content()) or None
    return fragment, text, title


@dataclass(frozen=True)
class BookPages:
    """How one book's slugs map to stored rows."""

    section_number_for: Callable[[str], str | None]
    chapter_for: Callable[[str], str | None]
    extract: Callable[[str], tuple[str, str, str | None]] = extract_main_content
    # Page URLs are ``<base_path>/<slug><page_suffix>``.
    page_suffix: str = ".html"


def _book_meta(base_url: str, base_path: str, year_key: str, year: str) -> list[tuple[str, str]]:
    return [
        ("schema_version", str(OUTLINE_SCHEMA_VERSION)),
        ("source", f"{base_url}{base_path}"),
        ("snapshot_date", datetime.now(UTC).strftime("%Y-%m-%d")),
        (year_key, year),
    ]


async def _fetch_page(client: httpx.AsyncClient, path: str) -> str | None:
    try:
        return await fetch_text(client, path)
    except Exception as exc:
        logger.warning("Skipping %s: %s", path, exc)
        return None


def _insert_page(
    conn: sqlite3.Connection, pages: BookPages, slug: str, path: str, page_html: str
) -> bool:
    fragment, text, page_title = pages.extract(page_html)
    if not text:
        logger.warning("Empty body for %s — skipping", path)
        return False
    section_number = pages.section_number_for(slug)
    insert_outline_section(
        conn,
        href=slug,
        section_number=section_number,
        title=page_title or section_number or slug,
        breadcrumb=None,
        chapter=pages.chapter_for(slug),
        html=fragment,
        text=text,
    )
    return True


async def build_book_corpus(
    output_path: Path,
    *,
    book: str,
    year_key: str,
    year: str,
    pages: BookPages,
    discover: Callable[[httpx.AsyncClient, str], Awaitable[list[str]]],
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
    log_every: int = 25,
) -> int:
    """Crawl the slugs ``discover(client, base_path)`` returns; return rows written.

    ``limit`` keeps the first N discovered slugs. A page that fails to fetch
    or has no body is logged and skipped.
    """
    with atomic_output(output_path) as tmp_path:
        async with http_client(base_url, user_agent) as client:
            base_path = f"/en/legal/{book}/{year}"
            slugs = await discover(client, base_path)
            if limit:
                slugs = slugs[:limit]

            conn = sqlite3.connect(tmp_path)
            try:
                init_outline_corpus(conn, _book_meta(base_url, base_path, year_key, year))
                rows = 0
                for i, slug in enumerate(slugs, 1):
                    path = f"{base_path}/{slug}{pages.page_suffix}"
                    page_html = await _fetch_page(client, path)
                    if page_html is None or not _insert_page(conn, pages, slug, path, page_html):
                        continue
                    rows += 1
                    if i % log_every == 0 or i == len(slugs):
                        logger.info("  %d/%d  %s", i, len(slugs), slug)
                    if pause:
                        await asyncio.sleep(pause)
                finalize_outline_corpus(conn, logger=logger)
            finally:
                conn.close()

    logger.info("Wrote %d sections to %s", rows, output_path)
    return rows


# -- Guidelines crawl ----------------------------------------------------------

# A slug like ``g_ii_3_1`` (no .html). The leading letter is the Part
# (A-H), the roman numeral is the Chapter, and the trailing digits
# are the section / subsection numbers.
GUIDELINES_PAGE_SLUG_RE = re.compile(r"^[a-h](?:_[ivx]+(?:_\d+)*)?$", re.IGNORECASE)


def _guidelines_link_re(book: str) -> re.Pattern[str]:
    # Links to other Guidelines pages (relative or absolute), to BFS the tree.
    return re.compile(
        rf'href="(?:https?://[^/"]+)?(?:/en/legal/{re.escape(book)}/\d{{4}}/)?'
        r'([a-h](?:_[ivx]+(?:_\d+)*)?\.html)"',
        re.IGNORECASE,
    )


def guidelines_slug_from_path(path: str) -> str | None:
    """Extract slug ``g_ii_3_1`` from ``g_ii_3_1.html`` or full path."""
    name = path.rsplit("/", 1)[-1].removesuffix(".html").lower()
    return name if GUIDELINES_PAGE_SLUG_RE.match(name) else None


def guidelines_section_number(slug: str) -> str | None:
    """Map slug to citation form: ``g_ii_3_1`` → ``G-II, 3.1``."""
    parts = slug.split("_")
    if not parts:
        return None
    part = parts[0].upper()
    if len(parts) == 1:
        return part
    chapter = parts[1].upper()
    head = f"{part}-{chapter}"
    if len(parts) == 2:
        return head
    section_chain = ".".join(parts[2:])
    return f"{head}, {section_chain}"


def guidelines_part(slug: str) -> str | None:
    return slug[0].upper() if slug else None


def guidelines_section_paths(page_html: str, book: str) -> set[str]:
    """Pull every ``X_Y_Z.html`` link off one page (returns filenames)."""
    return {m.group(1).lower() for m in _guidelines_link_re(book).finditer(page_html)}


def extract_guidelines_content(page_html: str) -> tuple[str, str, str | None]:
    """:func:`extract_main_content` that also drops the breadcrumb trail."""
    return extract_main_content(
        page_html, strip=(*MAIN_CHROME, './/div[contains(@class, "breadcrumb")]')
    )


GUIDELINES_PAGES = BookPages(
    section_number_for=guidelines_section_number,
    chapter_for=guidelines_part,
    extract=extract_guidelines_content,
)


async def build_guidelines_corpus(
    output_path: Path,
    *,
    book: str,
    guidelines_year: str,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
) -> int:
    """Breadth-first crawl of a Guidelines book from its ``index.html``.

    Each page links to its siblings and parent, so the crawl reaches the
    whole tree. ``limit`` stops after N rows are written.
    """
    with atomic_output(output_path) as tmp_path:
        async with http_client(base_url, user_agent) as client:
            base_path = f"/en/legal/{book}/{guidelines_year}"
            logger.info("Fetching Guidelines index: %s%s/index.html", base_url, base_path)
            index_html = await fetch_text(client, f"{base_path}/index.html")
            seeds = guidelines_section_paths(index_html, book)
            logger.info("Index page links to %d chapter/section files", len(seeds))

            conn = sqlite3.connect(tmp_path)
            try:
                meta = _book_meta(base_url, base_path, "guidelines_year", guidelines_year)
                init_outline_corpus(conn, meta)
                queue: deque[str] = deque(sorted(seeds))
                seen: set[str] = set()
                rows = 0
                while queue:
                    if limit and rows >= limit:
                        break
                    name = queue.popleft()
                    if name in seen:
                        continue
                    seen.add(name)
                    slug = name.removesuffix(".html")
                    if not GUIDELINES_PAGE_SLUG_RE.match(slug):
                        continue
                    path = f"{base_path}/{name}"
                    page_html = await _fetch_page(client, path)
                    if page_html is None:
                        continue
                    for link in guidelines_section_paths(page_html, book):
                        if link not in seen:
                            queue.append(link)
                    if not _insert_page(conn, GUIDELINES_PAGES, slug, path, page_html):
                        continue
                    rows += 1
                    if rows % 25 == 0:
                        logger.info("  %d crawled (%d queued)", rows, len(queue))
                    if pause:
                        await asyncio.sleep(pause)
                finalize_outline_corpus(conn, logger=logger)
            finally:
                conn.close()

    logger.info("Wrote %d sections to %s", rows, output_path)
    return rows


def run_book_cli(
    argv: list[str] | None,
    *,
    description: str,
    default_output: str,
    default_year: str,
    year_help: str,
    build: Callable[..., Coroutine[Any, Any, int]],
    year_kwarg: str,
) -> int:
    """Console-script body shared by the epo.org builds (same flags for all)."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / default_output,
    )
    parser.add_argument(
        "--year", default=default_year, help=f"{year_help} (default: {default_year})"
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--limit", type=int, default=None, help="For testing only.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    kwargs: dict[str, Any] = {
        year_kwarg: args.year,
        "base_url": args.base_url,
        "user_agent": args.user_agent,
        "pause": args.pause,
        "limit": args.limit,
    }
    return run_build_cli(
        lambda: build(args.output, **kwargs),
        verbose=args.verbose,
        done=lambda count, _elapsed: f"Wrote {count} sections to {args.output}",
    )


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_USER_AGENT",
    "GUIDELINES_CITATION_PATTERN",
    "GUIDELINES_PAGES",
    "GUIDELINES_SLUG_PATTERN",
    "BookPages",
    "EpoGuidelinesClient",
    "EpoLegalClient",
    "build_book_corpus",
    "build_guidelines_corpus",
    "extract_guidelines_content",
    "extract_main_content",
    "guidelines_citation_to_slug",
    "guidelines_part",
    "guidelines_section_number",
    "guidelines_section_paths",
    "guidelines_slug_from_path",
    "http_client",
    "normalize_epo_href",
    "normalize_whitespace",
    "run_book_cli",
]
