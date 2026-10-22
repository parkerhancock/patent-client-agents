"""Scrape the EPO Case Law of the Boards of Appeal ("white book") into
a SQLite/FTS5 corpus.

Console-script entry point for ``patent-client-agents-build-caselaw-corpus``.

The "white book" is published at
``www.epo.org/en/legal/case-law/<year>/``. The index page embeds a
JavaScript TOC enumerating ~2,600 ``clr_*`` URLs covering Parts I-VII
of the canonical Case Law compilation. We extract those URLs once
and fetch each directly — no BFS needed.

Run manually for an interactive refresh::

    patent-client-agents-build-caselaw-corpus \\
        --output ~/.cache/patent_client_agents/caselaw.db

For cloud deploys, build in the image and point
``CASELAW_CORPUS_PATH`` at the output path. EPO publishes a new
edition every 2-3 years (2019, 2022, ...).
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import httpx2

from patent_client_agents.shared.corpus import fetch_text
from patent_client_agents.shared.corpus.epo_legal import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    BookPages,
    build_book_corpus,
    run_book_cli,
)

logger = logging.getLogger(__name__)

DEFAULT_CASELAW_YEAR = "2022"

_INDEX_HREF = re.compile(r'"/en/legal/case-law/\d{4}/(clr_[a-z0-9_]+)\.html"', re.IGNORECASE)


def _section_number_from_slug(slug: str) -> str | None:
    """Map slug to citation form: ``clr_i_a_1`` → ``I.A.1``."""
    if not slug.startswith("clr_"):
        return None
    rest = slug[len("clr_") :]
    parts = rest.split("_")
    if not parts:
        return None
    if all(re.match(r"^[ivx]+$|^\d+$|^[a-z]$", p, re.IGNORECASE) for p in parts):
        return ".".join(p.upper() for p in parts)
    return parts[0].capitalize() if len(parts) == 1 else rest.replace("_", " ").title()


def _chapter_from_slug(slug: str) -> str | None:
    if not slug.startswith("clr_"):
        return None
    rest = slug[len("clr_") :]
    first = rest.split("_", 1)[0]
    if re.match(r"^[ivx]+$", first, re.IGNORECASE):
        return f"Part {first.upper()}"
    return first.capitalize()


_PAGES = BookPages(section_number_for=_section_number_from_slug, chapter_for=_chapter_from_slug)


async def _discover(client: httpx2.AsyncClient, base_path: str) -> list[str]:
    """Every ``clr_*`` URL the index page's embedded TOC lists."""
    logger.info("Fetching Case Law index: %s/index.html", base_path)
    index_html = await fetch_text(client, f"{base_path}/index.html")
    slugs = sorted({m.group(1) for m in _INDEX_HREF.finditer(index_html)})
    logger.info("Index page enumerates %d clr_* URLs", len(slugs))
    return slugs


async def build_corpus(
    output_path: Path,
    *,
    caselaw_year: str = DEFAULT_CASELAW_YEAR,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
) -> int:
    return await build_book_corpus(
        output_path,
        book="case-law",
        year_key="caselaw_year",
        year=caselaw_year,
        pages=_PAGES,
        discover=_discover,
        base_url=base_url,
        user_agent=user_agent,
        pause=pause,
        limit=limit,
        log_every=100,
    )


def main(argv: list[str] | None = None) -> int:
    return run_book_cli(
        argv,
        description="Build an EPO Case Law of the Boards of Appeal SQLite/FTS5 corpus.",
        default_output="caselaw.db",
        default_year=DEFAULT_CASELAW_YEAR,
        year_help="Case Law edition year",
        build=build_corpus,
        year_kwarg="caselaw_year",
    )


if __name__ == "__main__":
    sys.exit(main())
