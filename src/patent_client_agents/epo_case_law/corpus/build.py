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
DEFAULT_CASELAW_YEAR = "2022"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

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


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    retryer = default_retryer()
    async for attempt in retryer:
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    raise RuntimeError("unreachable: default_retryer reraises")


def _extract_main_content(page_html: str) -> tuple[str, str, str | None]:
    tree = html.fromstring(page_html)
    mains = tree.xpath("//main")
    if not mains:
        return "", "", None
    main = mains[0]
    for sel in (".//nav", ".//script", ".//style", ".//footer"):
        for node in main.xpath(sel):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    fragment = html.tostring(main, encoding="unicode")
    text = re.sub(r"\s+", " ", main.text_content()).strip()
    title = None
    h1s = main.xpath(".//h1")
    if h1s:
        title = re.sub(r"\s+", " ", h1s[0].text_content()).strip() or None
    return fragment, text, title


async def build_corpus(
    output_path: Path,
    *,
    caselaw_year: str = DEFAULT_CASELAW_YEAR,
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
        base_path = f"/en/legal/case-law/{caselaw_year}"
        logger.info("Fetching Case Law index: %s%s/index.html", base_url, base_path)
        index_html = await _fetch(client, f"{base_path}/index.html")
        slugs = sorted({m.group(1) for m in _INDEX_HREF.finditer(index_html)})
        if limit:
            slugs = slugs[:limit]
        logger.info("Index page enumerates %d clr_* URLs", len(slugs))

        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            now = datetime.now(UTC).strftime("%Y-%m-%d")
            for key, val in (
                ("schema_version", str(SCHEMA_VERSION)),
                ("source", f"{base_url}{base_path}"),
                ("snapshot_date", now),
                ("caselaw_year", caselaw_year),
            ):
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))

            rows = 0
            for i, slug in enumerate(slugs, 1):
                path = f"{base_path}/{slug}.html"
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
                if i % 100 == 0 or i == len(slugs):
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
        description="Build an EPO Case Law of the Boards of Appeal SQLite/FTS5 corpus."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "caselaw.db",
    )
    parser.add_argument(
        "--year",
        default=DEFAULT_CASELAW_YEAR,
        help=f"Case Law edition year (default: {DEFAULT_CASELAW_YEAR})",
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
                caselaw_year=args.year,
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
