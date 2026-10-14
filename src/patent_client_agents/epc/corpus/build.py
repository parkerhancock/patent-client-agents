"""Scrape the European Patent Convention + Implementing Regulations
into a SQLite/FTS5 corpus.

Console-script entry point for ``patent-client-agents-build-epc-corpus``.

EPO publishes the EPC at ``www.epo.org/en/legal/epc/<year>/``:

- ``convention.html`` lists every Article via embedded TOC data
  pointing at one URL per Article: ``a1.html``, ``a10a.html``, etc.
  (180 Articles in the 2020 edition).
- ``regulations.html`` does the same for Rules: ``r1.html``, ``r19.html``,
  etc. (176 Rules).

Run manually for an interactive refresh::

    patent-client-agents-build-epc-corpus \\
        --output ~/.cache/patent_client_agents/epc.db

For cloud deploys, build in the image and point ``EPC_CORPUS_PATH``
at the output path.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import httpx

from patent_client_agents.shared.corpus import fetch_text
from patent_client_agents.shared.corpus.epo_legal import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    BookPages,
    build_book_corpus,
    run_book_cli,
)

logger = logging.getLogger(__name__)

DEFAULT_EPC_YEAR = "2020"

_ARTICLE_HREF = re.compile(r'"/en/legal/epc/\d{4}/(a\d+[a-z]?)\.html"')
_RULE_HREF = re.compile(r'"/en/legal/epc/\d{4}/(r\d+[a-z]?)\.html"')
_SLUG_RE = re.compile(r"^[ar]\d+[a-z]?$", re.IGNORECASE)


def _section_number_from_slug(slug: str) -> str | None:
    """Map slug to human citation form: ``a1`` → ``Article 1``."""
    m = re.match(r"^([ar])(\d+[a-z]?)$", slug, re.IGNORECASE)
    if not m:
        return None
    prefix, num = m.groups()
    label = "Article" if prefix.lower() == "a" else "Rule"
    return f"{label} {num}"


def _chapter_from_slug(slug: str) -> str | None:
    if not slug:
        return None
    return "Article" if slug[0].lower() == "a" else "Rule"


_PAGES = BookPages(section_number_for=_section_number_from_slug, chapter_for=_chapter_from_slug)


async def _discover(client: httpx.AsyncClient, base_path: str) -> list[str]:
    """Articles from ``convention.html``, then Rules from ``regulations.html``."""
    logger.info("Discovering articles + rules from EPC TOC pages")
    convention_html = await fetch_text(client, f"{base_path}/convention.html")
    regulations_html = await fetch_text(client, f"{base_path}/regulations.html")
    article_slugs = sorted({m.group(1) for m in _ARTICLE_HREF.finditer(convention_html)})
    rule_slugs = sorted({m.group(1) for m in _RULE_HREF.finditer(regulations_html)})
    logger.info("Discovered %d articles + %d rules", len(article_slugs), len(rule_slugs))
    return article_slugs + rule_slugs


async def build_corpus(
    output_path: Path,
    *,
    epc_year: str = DEFAULT_EPC_YEAR,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
) -> int:
    return await build_book_corpus(
        output_path,
        book="epc",
        year_key="epc_year",
        year=epc_year,
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
        description="Build an EPC SQLite/FTS5 corpus from www.epo.org.",
        default_output="epc.db",
        default_year=DEFAULT_EPC_YEAR,
        year_help="EPC edition year",
        build=build_corpus,
        year_kwarg="epc_year",
    )


if __name__ == "__main__":
    sys.exit(main())
