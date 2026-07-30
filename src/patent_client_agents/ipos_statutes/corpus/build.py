"""Download the four Singapore IP Acts from SSO and emit a SQLite/FTS5 corpus.

Console-script entry point for
``patent-client-agents-build-ipos-statutes-corpus``. Pulls each Act's
authoritative consolidated HTML (or PDF) from Singapore Statutes Online
(``sso.agc.gov.sg``), parses the section structure, and persists one row
per section (with whole-Act fallback when the per-section anchors aren't
extractable).

Run manually for an interactive refresh::

    patent-client-agents-build-ipos-statutes-corpus \\
        --output ~/.cache/patent_client_agents/ipos_statutes.db

For cloud deploys, run during image build and point
``IPOS_STATUTES_CORPUS_PATH`` at the output path. The wheel ships the
builder, not the corpus.

The source URLs hit the **current in-force** consolidations on SSO so
the snapshot tracks the live revised editions (Patents Act and the
companion 2020 Revised Edition renumbering; Copyright Act 2021 which
replaced the 1987 Act on 21 Nov 2021).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
from pypdf import PdfReader

from mcp_data_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://sso.agc.gov.sg"
DEFAULT_USER_AGENT = (
    "patent-client-agents-ipos/0.20 (+https://github.com/parkerhancock/patent-client-agents)"
)


@dataclass(frozen=True)
class StatuteSource:
    """One Singapore IP Act and the SSO endpoint that serves its
    consolidated full text.

    ``statute`` is the stable lowercase key written into the corpus.
    ``short_name`` is the citation-ready short form ("Patents Act").
    ``path`` is the SSO path that returns either HTML or PDF — the
    fetcher accepts both via :func:`extract_pdf_text` / direct HTML
    parsing.
    """

    statute: str
    short_name: str
    title: str
    path: str
    is_pdf: bool = False


# Canonical SSO endpoints for the four IPOS-administered Acts in scope.
# SSO serves the consolidated revised editions when no version is given;
# we deliberately use the "InForce-current" route so the snapshot tracks
# whatever's currently published.
SOURCES: tuple[StatuteSource, ...] = (
    StatuteSource(
        statute="patents",
        short_name="Patents Act",
        title="Patents Act 1994 (2020 Revised Edition)",
        path="/Act/PA1994",
    ),
    StatuteSource(
        statute="tm",
        short_name="Trade Marks Act",
        title="Trade Marks Act 1998 (2020 Revised Edition)",
        path="/Act/TMA1998",
    ),
    StatuteSource(
        statute="designs",
        short_name="Registered Designs Act",
        title="Registered Designs Act 2000 (2020 Revised Edition)",
        path="/Act/RDA2000",
    ),
    StatuteSource(
        statute="copyright",
        short_name="Copyright Act",
        title="Copyright Act 2021",
        path="/Act/CA2021",
    ),
)


@dataclass(frozen=True)
class FetchedStatute:
    """An Act's full text and the URL it was fetched from."""

    source: StatuteSource
    url: str
    text: str


@dataclass(frozen=True)
class ParsedSection:
    """A single section extracted from an Act."""

    section_label: str
    title: str | None
    text: str


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of in-line whitespace, preserve paragraph breaks."""
    cleaned_lines = []
    for line in text.splitlines():
        stripped = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Return the plain text of a PDF buffer."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover — pypdf can occasionally fail per page
            logger.warning("Skipping unreadable page: %s", exc)
            pages.append("")
    return _normalize_whitespace("\n\n".join(pages))


def extract_html_text(html_bytes: bytes) -> str:
    """Return the plain text of an SSO HTML page.

    Conservative tag stripping: SSO's HTML is heading-anchored with each
    provision wrapped in ``<div class="prov1">`` etc. We keep the section
    breaks intact and drop CSS/JS noise.
    """
    text = html_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)</div>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    return _normalize_whitespace(text)


# Matches lines like:
#   "13. Patentable inventions"
#   "13A.—(1) ..."
#   "27. — (1) Effect of registered trade mark"
_SECTION_HEADER_RE = re.compile(
    r"^(?P<label>\d+[A-Z]?(?:\([0-9A-Za-z]+\))?)\s*[\.—–\-]\s*(?P<title>.+?)$",
    re.MULTILINE,
)


def parse_sections(text: str) -> list[ParsedSection]:
    """Split a flat Act plain-text into per-section rows.

    SSO renderings expose section starts as ``"<num>. <heading>"`` lines.
    When the regex finds zero matches we return an empty list and the
    caller falls back to a single whole-Act row keyed ``"00"``.
    """
    matches = list(_SECTION_HEADER_RE.finditer(text))
    if not matches:
        return []
    sections: list[ParsedSection] = []
    for idx, match in enumerate(matches):
        label = match.group("label")
        title = match.group("title").strip().rstrip(".")
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # Re-prepend the heading line so the stored body is self-contained.
        section_text = f"{label}. {title}\n{body}".strip()
        sections.append(ParsedSection(section_label=label, title=title, text=section_text))
    return sections


class IposStatutesFetcher:
    """Async downloader for SSO Act pages."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/pdf;q=0.8",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> IposStatutesFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def fetch(self, source: StatuteSource) -> FetchedStatute:
        retryer = default_retryer()
        async for attempt in retryer:
            with attempt:
                response = await self._client.get(source.path)
                response.raise_for_status()
                if source.is_pdf:
                    text = extract_pdf_text(response.content)
                else:
                    text = extract_html_text(response.content)
                return FetchedStatute(
                    source=source,
                    url=f"{self._base_url}{source.path}",
                    text=text,
                )
        raise RuntimeError("unreachable: default_retryer reraises")


def write_corpus(
    statutes: list[FetchedStatute],
    output: Path,
    *,
    snapshot_date: str,
    source_version: str | None = None,
) -> int:
    """Materialize the corpus to ``output``; return the section row count."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    section_count = 0
    statute_count = 0
    try:
        conn.executescript(DDL)
        for fetched in statutes:
            src = fetched.source
            sections = parse_sections(fetched.text)
            if not sections:
                # Whole-Act fallback so every Act has at least one row;
                # search still works against the joined text.
                sections = [
                    ParsedSection(
                        section_label="00",
                        title=src.title,
                        text=fetched.text,
                    )
                ]
            statute_count += 1
            for sec in sections:
                breadcrumb = f"{src.short_name} › Section {sec.section_label}"
                conn.execute(
                    """
                    INSERT INTO sections
                        (statute, short_name, statute_title, section_label,
                         title, breadcrumb, source_url, source_version, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        src.statute,
                        src.short_name,
                        src.title,
                        sec.section_label,
                        sec.title,
                        breadcrumb,
                        fetched.url,
                        source_version,
                        sec.text,
                    ),
                )
                section_count += 1
        meta_rows: list[tuple[str, str]] = [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", snapshot_date),
            ("section_count", str(section_count)),
            ("statute_count", str(statute_count)),
        ]
        if source_version:
            meta_rows.append(("source_version", source_version))
        conn.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", meta_rows)
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.close()
    return section_count


async def build_corpus(
    output: Path,
    *,
    sources: tuple[StatuteSource, ...] = SOURCES,
    base_url: str = DEFAULT_BASE_URL,
    source_version: str | None = None,
) -> int:
    snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
    fetched: list[FetchedStatute] = []
    async with IposStatutesFetcher(base_url=base_url) as fetcher:
        for source in sources:
            t0 = time.monotonic()
            try:
                statute = await fetcher.fetch(source)
            except Exception as exc:
                logger.warning("Skipping %s — %s", source.statute, exc)
                continue
            elapsed = time.monotonic() - t0
            logger.info(
                "Fetched %s (%d chars, %.2fs)",
                source.statute,
                len(statute.text),
                elapsed,
            )
            fetched.append(statute)
    return write_corpus(
        fetched,
        output,
        snapshot_date=snapshot_date,
        source_version=source_version,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-build-ipos-statutes-corpus",
        description=(
            "Download Singapore IP Act consolidations (Patents / Trade "
            "Marks / Registered Designs / Copyright) from Singapore "
            "Statutes Online and write a SQLite/FTS5 corpus consumable "
            "by patent_client_agents.ipos_statutes."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to write the corpus SQLite file.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Override SSO base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--source-version",
        default=None,
        help="Optional vendor-style version label (e.g. '2020 Revised Edition').",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log per-Act progress.")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    started = time.monotonic()
    try:
        count = asyncio.run(
            build_corpus(
                args.output,
                base_url=args.base_url,
                source_version=args.source_version,
            )
        )
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    elapsed = time.monotonic() - started
    print(
        f"Wrote {count} sections to {args.output} in {elapsed:.1f}s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
