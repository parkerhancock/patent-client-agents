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

from law_tools_core.corpus_compression import finalize_outline_corpus
from law_tools_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.epo.org"
DEFAULT_UP_GUIDELINES_YEAR = "2026"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

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


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    retryer = default_retryer()
    async for attempt in retryer:
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    raise RuntimeError("unreachable: default_retryer reraises")


async def _enumerate_from_sitemap(client: httpx.AsyncClient, year: str) -> list[str]:
    sitemap = await _fetch(client, "/en/legal/sitemap/sitemap-en-1.xml")
    pattern = re.compile(
        rf"<loc>https?://[^/]+/en/legal/guidelines-up/{year}/(section(?:_\d+)+)</loc>"
    )
    return sorted({m.group(1) for m in pattern.finditer(sitemap)})


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


async def build_corpus(
    output_path: Path,
    *,
    up_guidelines_year: str = DEFAULT_UP_GUIDELINES_YEAR,
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
        base_path = f"/en/legal/guidelines-up/{up_guidelines_year}"
        logger.info("Discovering UP Guidelines sections from sitemap")
        slugs = await _enumerate_from_sitemap(client, up_guidelines_year)
        if limit:
            slugs = slugs[:limit]
        logger.info("Sitemap enumerates %d UP Guidelines sections", len(slugs))

        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            now = datetime.now(UTC).strftime("%Y-%m-%d")
            for key, val in (
                ("schema_version", str(SCHEMA_VERSION)),
                ("source", f"{base_url}{base_path}"),
                ("snapshot_date", now),
                ("up_guidelines_year", up_guidelines_year),
            ):
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))

            rows = 0
            for i, slug in enumerate(slugs, 1):
                path = f"{base_path}/{slug}"
                try:
                    page_html = await _fetch(client, path)
                except Exception as exc:
                    logger.warning("Skipping %s: %s", path, exc)
                    continue
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
                        _chapter_from_slug(slug),
                        fragment,
                        text,
                    ),
                )
                rows += 1
                if i % 25 == 0 or i == len(slugs):
                    logger.info("  %d/%d  %s", i, len(slugs), slug)
                if pause:
                    await asyncio.sleep(pause)
            finalize_outline_corpus(conn, logger=logger)
        finally:
            conn.close()

    if output_path.exists():
        output_path.unlink()
    tmp_path.rename(output_path)
    logger.info("Wrote %d sections to %s", rows, output_path)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build an EPO Unitary Patent (UP) Guidelines SQLite/FTS5 corpus."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "up_guidelines.db",
    )
    parser.add_argument(
        "--year",
        default=DEFAULT_UP_GUIDELINES_YEAR,
        help=f"UP Guidelines year (default: {DEFAULT_UP_GUIDELINES_YEAR})",
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
                up_guidelines_year=args.year,
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
