"""Scrape the LPI (Lei nº 9.279/1996) into a SQLite/FTS5 corpus.

Console-script entry point for
``patent-client-agents-build-inpi-br-statutes-corpus``.

Brazilian IP law is unified into a single statute. Planalto publishes
the authoritative PT consolidation at:

    https://www.planalto.gov.br/ccivil_03/leis/l9279.htm

The page is a single long document with anchor IDs of the form
``art1``, ``art2``, … ``art243``. We split on those anchors and store
one row per Article.

When a WIPO Lex EN translation URL is supplied via ``--wipo-en-url``,
the script also splits the EN HTML and joins to the PT row. Splitting
is heuristic (Article boundaries marked by ``Article 1``, ``Article 2``,
…). When EN parsing fails or no URL is given, rows ship PT-only and the
EN columns are NULL — the runtime is tolerant.

Run manually for an interactive refresh::

    patent-client-agents-build-inpi-br-statutes-corpus \\
        --output ~/.cache/patent_client_agents/inpi_br_statutes.db

For cloud deploys, build in the image and point
``INPI_BR_STATUTES_CORPUS_PATH`` at the output path.
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

from mcp_data_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_PT_URL = "https://www.planalto.gov.br/ccivil_03/leis/l9279.htm"
DEFAULT_LPI_YEAR = "1996"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

# Planalto anchors articles as ``<a name="art1">``/``<a id="art1">`` and
# inside <p> blocks ``Art. 1º``. We split on the textual marker because
# the HTML is loose and the anchor coverage is uneven across older laws.
_ARTICLE_HEAD_PT = re.compile(
    r"(?P<head>Art\.?\s*(?P<num>\d{1,3}[A-Za-z]?)\s*[º°]?\s*[\-\.\s])",
    re.IGNORECASE,
)
_ARTICLE_HEAD_EN = re.compile(
    r"(?P<head>Article\s+(?P<num>\d{1,3}[A-Za-z]?)\b)",
    re.IGNORECASE,
)


def _slug_from_num(num: str) -> str:
    return f"art{num.lower()}"


def _article_label_pt(num: str) -> str:
    return f"Art. {num}"


def _article_label_en(num: str) -> str:
    return f"Article {num}"


async def _fetch(client: httpx.AsyncClient, url: str) -> str:
    retryer = default_retryer()
    async for attempt in retryer:
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    raise RuntimeError("unreachable: default_retryer reraises")


def _strip_html(page_html: str) -> str:
    """Reduce a Planalto HTML page to plain text, collapsing whitespace."""
    try:
        tree = html.fromstring(page_html)
    except Exception:
        return page_html
    for sel in (".//script", ".//style", ".//head"):
        for node in tree.xpath(sel):
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
    text = tree.text_content()
    return re.sub(r"\s+", " ", text).strip()


def _split_articles(text: str, pattern: re.Pattern[str]) -> dict[str, str]:
    """Split a flat-text statute on Article boundaries.

    Returns a mapping from Article number (e.g. ``"1"``, ``"195"``) to
    the article body text (including the heading itself).
    """
    out: dict[str, str] = {}
    matches = list(pattern.finditer(text))
    if not matches:
        return out
    for idx, m in enumerate(matches):
        num = m.group("num")
        start = m.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # Skip pathological short matches (false positives like "Art. 5º
        # da Constituição" appearing inside another article's body — when
        # body is too short to be a real article).
        if len(body) < 20:
            continue
        # Keep the first occurrence per article number (later mentions
        # are typically cross-references inside other articles' bodies).
        if num not in out:
            out[num] = body
    return out


def _title_from_body(body: str, *, max_chars: int = 120) -> str:
    """Pull a one-line title from the first sentence-ish chunk of a body."""
    first = re.split(r"(?<=[.;])\s", body, maxsplit=1)[0]
    if len(first) > max_chars:
        first = first[: max_chars - 1].rstrip() + "…"
    return first


async def build_corpus(
    output_path: Path,
    *,
    pt_url: str = DEFAULT_PT_URL,
    en_url: str | None = None,
    lpi_year: str = DEFAULT_LPI_YEAR,
    user_agent: str = DEFAULT_USER_AGENT,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    headers = {"User-Agent": user_agent, "Accept": "text/html"}
    async with httpx.AsyncClient(
        headers=headers, timeout=httpx.Timeout(30.0, connect=10.0)
    ) as client:
        logger.info("Fetching LPI PT consolidation from %s", pt_url)
        pt_html = await _fetch(client, pt_url)
        pt_text = _strip_html(pt_html)
        pt_articles = _split_articles(pt_text, _ARTICLE_HEAD_PT)
        logger.info("PT split: %d Articles", len(pt_articles))

        en_articles: dict[str, str] = {}
        if en_url:
            try:
                logger.info("Fetching LPI EN translation from %s", en_url)
                en_html = await _fetch(client, en_url)
                en_text = _strip_html(en_html)
                en_articles = _split_articles(en_text, _ARTICLE_HEAD_EN)
                logger.info("EN split: %d Articles", len(en_articles))
            except Exception as exc:
                logger.warning("EN fetch failed (%s); shipping PT-only rows.", exc)

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(DDL)
        now = datetime.now(UTC).strftime("%Y-%m-%d")
        for key, val in (
            ("schema_version", str(SCHEMA_VERSION)),
            ("source_pt", pt_url),
            ("source_en", en_url or ""),
            ("snapshot_date", now),
            ("lpi_year", lpi_year),
        ):
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))

        rows = 0
        for num in sorted(pt_articles, key=lambda n: (len(n), n)):
            pt_body = pt_articles[num]
            en_body = en_articles.get(num)
            slug = _slug_from_num(num)
            pt_label = _article_label_pt(num)
            en_label = _article_label_en(num) if en_body else None
            pt_title = _title_from_body(pt_body)
            en_title = _title_from_body(en_body) if en_body else None
            conn.execute(
                "INSERT OR REPLACE INTO sections "
                "(href, article_number, title_pt, title_en, title_section, "
                " text_pt, text_en, html_pt, html_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    slug,
                    pt_label,
                    pt_title,
                    en_title,
                    None,
                    pt_body,
                    en_body,
                    f"<p>{pt_body}</p>",
                    f"<p>{en_body}</p>" if en_body else None,
                ),
            )
            rows += 1
            del en_label  # not stored — only used to gate en_title above

        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            ("section_count", str(rows)),
        )
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
        description="Build an LPI (Lei 9.279/1996) SQLite/FTS5 corpus."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".cache" / "patent_client_agents" / "inpi_br_statutes.db",
    )
    parser.add_argument("--pt-url", default=DEFAULT_PT_URL)
    parser.add_argument(
        "--wipo-en-url",
        default=None,
        help=(
            "Optional WIPO Lex EN translation URL (e.g. the HTML rendering "
            "of the LPI EN PDF). When omitted, EN columns are NULL."
        ),
    )
    parser.add_argument(
        "--year",
        default=DEFAULT_LPI_YEAR,
        help=f"LPI consolidation year (default: {DEFAULT_LPI_YEAR})",
    )
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
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
                pt_url=args.pt_url,
                en_url=args.wipo_en_url,
                lpi_year=args.year,
                user_agent=args.user_agent,
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
