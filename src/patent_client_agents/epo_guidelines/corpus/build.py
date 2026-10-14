"""Scrape the EPO Guidelines for Examination into a SQLite/FTS5 corpus.

Console-script entry point for ``patent-client-agents-build-guidelines-corpus``.

Strategy: BFS from the year's ``index.html`` page over the EPO Guidelines
URL hierarchy ``<part>_<chapter>_<section>_<subsection>.html``. The
EPO publishes each subsection on its own page (typically 500-2000
pages total across Parts A-H + General Part). Each page links to its
siblings and parent, so a single BFS captures the whole tree.

Run manually for an interactive refresh::

    patent-client-agents-build-guidelines-corpus \\
        --output ~/.cache/patent_client_agents/guidelines.db

For cloud deploys, build in the image and point
``GUIDELINES_CORPUS_PATH`` at the output path. EPO publishes a new
edition annually (March releases); rebuild after each edition.

Source: ``https://www.epo.org/en/legal/guidelines-epc/<year>``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from patent_client_agents.shared.corpus.epo_legal import (
    DEFAULT_BASE_URL,
    DEFAULT_USER_AGENT,
    build_guidelines_corpus,
    extract_guidelines_content,
    guidelines_part,
    guidelines_section_number,
    guidelines_section_paths,
    guidelines_slug_from_path,
    run_book_cli,
)

BOOK = "guidelines-epc"
DEFAULT_GUIDELINES_YEAR = "2024"

# Slug and page parsing are shared with the PCT-EPO Guidelines build.
_slug_from_path = guidelines_slug_from_path
_section_number_from_slug = guidelines_section_number
_part_from_slug = guidelines_part
_extract_main_content = extract_guidelines_content


def _enumerate_section_paths(page_html: str) -> set[str]:
    """Pull every ``X_Y_Z.html`` link off one page (returns filenames)."""
    return guidelines_section_paths(page_html, BOOK)


async def build_corpus(
    output_path: Path,
    *,
    guidelines_year: str = DEFAULT_GUIDELINES_YEAR,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
) -> int:
    return await build_guidelines_corpus(
        output_path,
        book=BOOK,
        guidelines_year=guidelines_year,
        base_url=base_url,
        user_agent=user_agent,
        pause=pause,
        limit=limit,
    )


def main(argv: list[str] | None = None) -> int:
    return run_book_cli(
        argv,
        description="Build an EPO Guidelines for Examination SQLite/FTS5 corpus.",
        default_output="guidelines.db",
        default_year=DEFAULT_GUIDELINES_YEAR,
        year_help="Guidelines year edition",
        build=build_corpus,
        year_kwarg="guidelines_year",
    )


if __name__ == "__main__":
    sys.exit(main())
