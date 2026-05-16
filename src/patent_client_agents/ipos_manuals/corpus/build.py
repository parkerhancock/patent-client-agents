"""Download IPOS examination + work manuals and emit a SQLite/FTS5 corpus.

Console-script entry point for
``patent-client-agents-build-ipos-manuals-corpus``. Each manual is
downloaded from its stable URL on the IPOS website, parsed with
:mod:`pypdf` to plaintext, and persisted as section rows (with whole-
manual fallback when section anchors aren't extractable).

Run manually for an interactive refresh::

    patent-client-agents-build-ipos-manuals-corpus \\
        --output ~/.cache/patent_client_agents/ipos_manuals.db

For cloud deploys, run during image build and point
``IPOS_MANUALS_CORPUS_PATH`` at the output path. The wheel ships the
builder, not the corpus.
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

from law_tools_core.resilience import default_retryer

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.ipos.gov.sg"
DEFAULT_USER_AGENT = (
    "patent-client-agents-ipos/0.20 (+https://github.com/parkerhancock/patent-client-agents)"
)


@dataclass(frozen=True)
class ManualSource:
    """One IPOS work manual and its stable IPOS URL.

    ``manual`` is the lowercase key written into the corpus.
    ``short_name`` is the citation-ready abbreviation (``PEG``,
    ``TM Work Manual``, ``Designs Work Manual``).
    """

    manual: str
    short_name: str
    title: str
    path: str
    is_pdf: bool = True


# Canonical IPOS manual endpoints in scope for v1. The IPOS site
# rearranges its `/about-ip/` paths periodically; the build script
# accepts ``--base-url`` so deployment-time overrides can patch
# without a code change.
SOURCES: tuple[ManualSource, ...] = (
    ManualSource(
        manual="peg",
        short_name="PEG",
        title="IPOS Patent Examination Guidelines",
        path="/docs/default-source/resources-library/patents/guidelines-and-useful-information/examination-guidelines-for-patent-applications-at-ipos.pdf",
    ),
    ManualSource(
        manual="tm",
        short_name="TM Work Manual",
        title="IPOS Trade Marks Work Manual",
        path="/docs/default-source/resources-library/trade-marks/infopacks/trade-marks-work-manual.pdf",
    ),
    ManualSource(
        manual="designs",
        short_name="Designs Work Manual",
        title="IPOS Industrial Designs Work Manual",
        path="/docs/default-source/resources-library/designs/guidelines/registered-designs-work-manual.pdf",
    ),
)


@dataclass(frozen=True)
class FetchedManual:
    """A manual's full text and the URL it was fetched from."""

    source: ManualSource
    url: str
    pdf_pages: int
    text: str


@dataclass(frozen=True)
class ParsedSection:
    """A single section extracted from a manual."""

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


def extract_pdf_text(pdf_bytes: bytes) -> tuple[int, str]:
    """Return ``(page_count, plain_text)`` for a PDF buffer."""
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover — pypdf can occasionally fail per page
            logger.warning("Skipping unreadable page: %s", exc)
            pages.append("")
    return len(reader.pages), _normalize_whitespace("\n\n".join(pages))


# Matches dotted section labels common to IPOS manuals:
#   "1.5.3 Title here"
#   "4.A.2 Subsection"
#   "1.5 Heading"
_SECTION_HEADER_RE = re.compile(
    r"^(?P<label>\d+(?:\.\d+){1,3}|\d+\.[A-Z](?:\.\d+)?)\s+(?P<title>[A-Z][^\n]{0,140})$",
    re.MULTILINE,
)


def parse_sections(text: str) -> list[ParsedSection]:
    """Split a flat manual plain-text into per-section rows.

    Manuals expose section starts as ``"<dotted-label> <title-cased
    heading>"`` lines. When the regex finds zero matches we return an
    empty list and the caller falls back to a whole-manual row.
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
        section_text = f"{label} {title}\n{body}".strip()
        sections.append(ParsedSection(section_label=label, title=title, text=section_text))
    return sections


class IposManualsFetcher:
    """Async downloader for IPOS manual PDFs."""

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
                "Accept": "application/pdf",
            },
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> IposManualsFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def fetch(self, source: ManualSource) -> FetchedManual:
        retryer = default_retryer()
        async for attempt in retryer:
            with attempt:
                response = await self._client.get(source.path)
                response.raise_for_status()
                pages, text = extract_pdf_text(response.content)
                return FetchedManual(
                    source=source,
                    url=f"{self._base_url}{source.path}",
                    pdf_pages=pages,
                    text=text,
                )
        raise RuntimeError("unreachable: default_retryer reraises")


def write_corpus(
    manuals: list[FetchedManual],
    output: Path,
    *,
    snapshot_date: str,
    source_version: str | None = None,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    section_count = 0
    manual_count = 0
    try:
        conn.executescript(DDL)
        for fetched in manuals:
            src = fetched.source
            sections = parse_sections(fetched.text)
            if not sections:
                sections = [
                    ParsedSection(
                        section_label="0",
                        title=src.title,
                        text=fetched.text,
                    )
                ]
            manual_count += 1
            for sec in sections:
                breadcrumb = f"{src.short_name} › {sec.section_label}"
                conn.execute(
                    """
                    INSERT INTO sections
                        (manual, short_name, manual_title, section_label,
                         title, breadcrumb, source_url, source_version, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        src.manual,
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
            ("manual_count", str(manual_count)),
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
    sources: tuple[ManualSource, ...] = SOURCES,
    base_url: str = DEFAULT_BASE_URL,
    source_version: str | None = None,
) -> int:
    snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
    fetched: list[FetchedManual] = []
    async with IposManualsFetcher(base_url=base_url) as fetcher:
        for source in sources:
            t0 = time.monotonic()
            try:
                manual = await fetcher.fetch(source)
            except Exception as exc:
                logger.warning("Skipping %s — %s", source.manual, exc)
                continue
            elapsed = time.monotonic() - t0
            logger.info(
                "Fetched %s (%d pages, %d chars, %.2fs)",
                source.manual,
                manual.pdf_pages,
                len(manual.text),
                elapsed,
            )
            fetched.append(manual)
    return write_corpus(
        fetched,
        output,
        snapshot_date=snapshot_date,
        source_version=source_version,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-build-ipos-manuals-corpus",
        description=(
            "Download IPOS examination + work manual PDFs (PEG / TM Work "
            "Manual / Designs Work Manual) and write a SQLite/FTS5 "
            "corpus consumable by patent_client_agents.ipos_manuals."
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
        help=f"Override IPOS base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--source-version",
        default=None,
        help="Optional vendor-style version label.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log per-manual progress.")
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
