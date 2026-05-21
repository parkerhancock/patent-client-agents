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

from mcp_data_core.corpus_compression import finalize_outline_corpus
from mcp_data_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.epo.org"
DEFAULT_EPC_YEAR = "2020"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

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
    epc_year: str = DEFAULT_EPC_YEAR,
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
        base_path = f"/en/legal/epc/{epc_year}"
        logger.info("Discovering articles + rules from EPC TOC pages")
        convention_html = await _fetch(client, f"{base_path}/convention.html")
        regulations_html = await _fetch(client, f"{base_path}/regulations.html")
        article_slugs = sorted({m.group(1) for m in _ARTICLE_HREF.finditer(convention_html)})
        rule_slugs = sorted({m.group(1) for m in _RULE_HREF.finditer(regulations_html)})
        slugs = article_slugs + rule_slugs
        if limit:
            slugs = slugs[:limit]
        logger.info(
            "Discovered %d articles + %d rules (%d total)",
            len(article_slugs),
            len(rule_slugs),
            len(slugs),
        )

        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(DDL)
            now = datetime.now(UTC).strftime("%Y-%m-%d")
            for key, val in (
                ("schema_version", str(SCHEMA_VERSION)),
                ("source", f"{base_url}{base_path}"),
                ("snapshot_date", now),
                ("epc_year", epc_year),
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
        description="Build an EPC SQLite/FTS5 corpus from www.epo.org."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "epc.db",
    )
    parser.add_argument(
        "--year",
        default=DEFAULT_EPC_YEAR,
        help=f"EPC edition year (default: {DEFAULT_EPC_YEAR})",
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
                epc_year=args.year,
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
