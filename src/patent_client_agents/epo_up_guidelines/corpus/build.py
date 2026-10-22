"""Scrape the EPO Unitary Patent (UP) Guidelines into a SQLite/FTS5 corpus.

Console-script entry point for ``patent-client-agents-build-up-guidelines-corpus``.

The UP Guidelines are published at
``www.epo.org/en/legal/guidelines-up/<year>/section_<N>_<M>_<P>``.
Unlike the EPC Guidelines (per-part hierarchy with roman-numeral
chapters), the UP Guidelines use a flat ``section_N.M.P`` numbering.
The legal sitemap enumerates ~140 URLs in one fetch.

Run manually::

    patent-client-agents-build-up-guidelines-corpus \\
        --output ~/.cache/patent_client_agents/up_guidelines.db
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import httpx2
from lxml import html

from patent_client_agents.shared.corpus import fetch_text
from patent_client_agents.shared.corpus.epo_legal import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    BookPages,
    build_book_corpus,
    run_book_cli,
)

logger = logging.getLogger(__name__)

DEFAULT_UP_GUIDELINES_YEAR = "2026"

_SLUG_RE = re.compile(r"^section(?:_\d+)+$", re.IGNORECASE)


def _section_number_from_slug(slug: str) -> str | None:
    """Map ``section_1_2_1`` → ``1.2.1``."""
    m = re.match(r"^section((?:_\d+)+)$", slug, re.IGNORECASE)
    if not m:
        return None
    parts = m.group(1).strip("_").split("_")
    return ".".join(parts)


def _chapter_from_slug(slug: str) -> str | None:
    m = re.match(r"^section_(\d+)", slug, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_main_content(page_html: str) -> tuple[str, str, str | None]:
    """Extract the UP Guidelines content column.

    UP pages don't have a ``<main>`` element. The article body is in
    the Bootstrap column ``col-12 col-lg-8`` that contains the page's
    single ``<h1>``. Walk up from the H1 to that column.
    """
    tree = html.fromstring(page_html)
    h1s = tree.xpath("//h1")
    if not h1s:
        return "", "", None
    h1 = h1s[0]
    # The h1 lives in a sibling col-lg-8 div but the actual article body
    # is several levels up in the ``content-wrapper`` div (h1 + body
    # together total ~2-3KB).
    container = h1
    for _ in range(10):
        parent = container.getparent()
        if parent is None:
            break
        container = parent
        cls = parent.get("class", "") or ""
        if "content-wrapper" in cls:
            break
    for sel in (".//nav", ".//script", ".//style", ".//footer"):
        for node in container.xpath(sel):
            p = node.getparent()
            if p is not None:
                p.remove(node)
    fragment = html.tostring(container, encoding="unicode")
    text = re.sub(r"\s+", " ", container.text_content()).strip()
    title = re.sub(r"\s+", " ", h1.text_content()).strip() or None
    return fragment, text, title


# UP pages are served without an ``.html`` suffix.
_PAGES = BookPages(
    section_number_for=_section_number_from_slug,
    chapter_for=_chapter_from_slug,
    extract=_extract_main_content,
    page_suffix="",
)


async def _discover(client: httpx2.AsyncClient, base_path: str) -> list[str]:
    """The ``section_*`` URLs the legal sitemap lists for this edition."""
    logger.info("Discovering UP Guidelines sections from sitemap")
    sitemap = await fetch_text(client, "/en/legal/sitemap/sitemap-en-1.xml")
    pattern = re.compile(rf"<loc>https?://[^/]+{re.escape(base_path)}/(section(?:_\d+)+)</loc>")
    slugs = sorted({m.group(1) for m in pattern.finditer(sitemap)})
    logger.info("Sitemap enumerates %d UP Guidelines sections", len(slugs))
    return slugs


async def build_corpus(
    output_path: Path,
    *,
    up_guidelines_year: str = DEFAULT_UP_GUIDELINES_YEAR,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
) -> int:
    return await build_book_corpus(
        output_path,
        book="guidelines-up",
        year_key="up_guidelines_year",
        year=up_guidelines_year,
        pages=_PAGES,
        discover=_discover,
        base_url=base_url,
        user_agent=user_agent,
        pause=pause,
        limit=limit,
    )


def main(argv: list[str] | None = None) -> int:
    return run_book_cli(
        argv,
        description="Build an EPO Unitary Patent (UP) Guidelines SQLite/FTS5 corpus.",
        default_output="up_guidelines.db",
        default_year=DEFAULT_UP_GUIDELINES_YEAR,
        year_help="UP Guidelines year",
        build=build_corpus,
        year_kwarg="up_guidelines_year",
    )


if __name__ == "__main__":
    sys.exit(main())
