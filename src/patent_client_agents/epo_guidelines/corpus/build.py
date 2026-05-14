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

import argparse
import asyncio
import logging
import re
import sqlite3
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lxml import html

from law_tools_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.epo.org"
DEFAULT_GUIDELINES_YEAR = "2024"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

# A slug like ``g_ii_3_1`` (no .html). The leading letter is the Part
# (A-H), the roman numeral is the Chapter, and the trailing digits
# are the section / subsection numbers.
_SLUG_RE = re.compile(r"^[a-h](?:_[ivx]+(?:_\d+)*)?$", re.IGNORECASE)
# Match links to other Guidelines pages (relative or absolute) so we
# can BFS the tree.
_LINK_HREF_RE = re.compile(
    r'href="(?:https?://[^/"]+)?(?:/en/legal/guidelines-epc/\d{4}/)?'
    r'([a-h](?:_[ivx]+(?:_\d+)*)?\.html)"',
    re.IGNORECASE,
)


def _slug_from_path(path: str) -> str | None:
    """Extract slug ``g_ii_3_1`` from ``g_ii_3_1.html`` or full path."""
    name = path.rsplit("/", 1)[-1].removesuffix(".html").lower()
    return name if _SLUG_RE.match(name) else None


def _section_number_from_slug(slug: str) -> str | None:
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


def _part_from_slug(slug: str) -> str | None:
    return slug[0].upper() if slug else None


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    retryer = default_retryer()
    async for attempt in retryer:
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    raise RuntimeError("unreachable: default_retryer reraises")


def _enumerate_section_paths(page_html: str) -> set[str]:
    """Pull every ``X_Y_Z.html`` link off one page (returns filenames)."""
    return {m.group(1).lower() for m in _LINK_HREF_RE.finditer(page_html)}


def _extract_main_content(page_html: str) -> tuple[str, str, str | None]:
    """Return (main HTML fragment, plain text, page title)."""
    tree = html.fromstring(page_html)
    mains = tree.xpath("//main")
    if not mains:
        return "", "", None
    main = mains[0]
    for sel in (
        ".//nav",
        ".//script",
        ".//style",
        ".//footer",
        './/div[contains(@class, "breadcrumb")]',
    ):
        for node in main.xpath(sel):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    fragment = html.tostring(main, encoding="unicode")
    text = _normalize_whitespace(main.text_content())
    title = None
    h1s = main.xpath(".//h1")
    if h1s:
        title = _normalize_whitespace(h1s[0].text_content()) or None
    return fragment, text, title


def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


async def build_corpus(
    output_path: Path,
    *,
    guidelines_year: str = DEFAULT_GUIDELINES_YEAR,
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    pause: float = 0.3,
    limit: int | None = None,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    headers = {"User-Agent": user_agent, "Accept": "text/html"}
    async with httpx.AsyncClient(
        base_url=base_url, headers=headers, timeout=httpx.Timeout(30.0, connect=10.0)
    ) as client:
        base_path = f"/en/legal/guidelines-epc/{guidelines_year}"
        logger.info("Fetching Guidelines index: %s%s/index.html", base_url, base_path)
        index_html = await _fetch(client, f"{base_path}/index.html")
        seeds = _enumerate_section_paths(index_html)
        logger.info("Index page links to %d chapter/section files", len(seeds))

        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            now = datetime.now(UTC).strftime("%Y-%m-%d")
            for key, val in (
                ("schema_version", str(SCHEMA_VERSION)),
                ("source", f"{base_url}{base_path}"),
                ("snapshot_date", now),
                ("guidelines_year", guidelines_year),
            ):
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))

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
                if not _SLUG_RE.match(slug):
                    continue
                path = f"{base_path}/{name}"
                try:
                    page_html = await _fetch(client, path)
                except Exception as exc:
                    logger.warning("Skipping %s: %s", path, exc)
                    continue
                for link in _enumerate_section_paths(page_html):
                    if link not in seen:
                        queue.append(link)
                fragment, text, page_title = _extract_main_content(page_html)
                if not text:
                    logger.warning("Empty body for %s — skipping", path)
                    continue
                section_number = _section_number_from_slug(slug)
                conn.execute(
                    "INSERT OR REPLACE INTO sections "
                    "(href, section_number, title, breadcrumb, chapter, html, text) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        slug,
                        section_number,
                        page_title or section_number or slug,
                        None,
                        _part_from_slug(slug),
                        fragment,
                        text,
                    ),
                )
                rows += 1
                if rows % 25 == 0:
                    logger.info("  %d crawled (%d queued)", rows, len(queue))
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
        description="Build an EPO Guidelines for Examination SQLite/FTS5 corpus."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "guidelines.db",
    )
    parser.add_argument(
        "--year",
        default=DEFAULT_GUIDELINES_YEAR,
        help=f"Guidelines year edition (default: {DEFAULT_GUIDELINES_YEAR})",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--limit", type=int, default=None, help="For testing only.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        count = asyncio.run(
            build_corpus(
                args.output,
                guidelines_year=args.year,
                base_url=args.base_url,
                user_agent=args.user_agent,
                pause=args.pause,
                limit=args.limit,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {count} sections to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
