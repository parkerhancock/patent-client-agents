"""Download Israeli IP statute PDFs and emit a queryable SQLite/FTS5 corpus.

Console-script entry point for
``patent-client-agents-build-ilpo-statutes-corpus``. Each statute is
downloaded from its WIPO Lex authoritative-EN PDF, parsed with
:mod:`pypdf` to plaintext, then split into sections by a regex tuned to
each statute's numbering style. Sections are persisted as one row per
(statute, section_number) pair.

Run manually for an interactive refresh::

    patent-client-agents-build-ilpo-statutes-corpus \\
        --output ~/.cache/patent_client_agents/ilpo_statutes.db

For cloud deploys, run during image build and point
``ILPO_STATUTES_CORPUS_PATH`` at the output path. The wheel ships the
builder, not the corpus.

The five statutes covered are Patents Law 5727-1967, Trade Marks
Ordinance [New Version] 5732-1972, Designs Law 5777-2017, Copyright Act
5768-2007, and Commercial Torts Law 5759-1999 (the trade-secret
statute). WIPO Lex hosts authoritative English translations prepared by
ILPO / the Israeli Ministry of Justice.
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

DEFAULT_USER_AGENT = (
    "patent-client-agents-ilpo/0.20 (+https://github.com/parkerhancock/patent-client-agents)"
)


@dataclass(frozen=True)
class StatuteSource:
    """A single Israeli IP statute to be fetched and parsed."""

    statute: str  # stable key: 'patents', 'trademarks', 'designs', 'copyright', 'commercial_torts'
    short_name: str  # citation form
    title: str  # full title
    source_url: str  # WIPO Lex / gov.il PDF URL
    section_unit: str  # 'Section' or 'Article' — used in section_label
    source_version: str | None  # WIPO Lex revision date / consolidation label


# Canonical source list. URLs are WIPO Lex authoritative-EN PDFs prepared
# by ILPO / Israeli Ministry of Justice. ``commercial_torts`` is the
# distinctive piece: a standalone statute combining trade-secret
# protection (Arts. 6-9), unregistered-mark protection (Arts. 1-4), and
# statutory damages up to NIS 100,000 without proof (Art. 13).
SOURCES: tuple[StatuteSource, ...] = (
    StatuteSource(
        statute="patents",
        short_name="Patents Law",
        title="Patents Law, 5727-1967",
        source_url="https://www.wipo.int/wipolex/en/legislation/details/15167",
        section_unit="Section",
        source_version="2014 consolidation",
    ),
    StatuteSource(
        statute="trademarks",
        short_name="Trade Marks Ordinance",
        title="Trade Marks Ordinance [New Version], 5732-1972",
        source_url="https://www.wipo.int/wipolex/en/legislation/details/8200",
        section_unit="Section",
        source_version="2010 consolidation",
    ),
    StatuteSource(
        statute="designs",
        short_name="Designs Law",
        title="Designs Law, 5777-2017",
        source_url="https://www.wipo.int/wipolex/en/legislation/details/19434",
        section_unit="Section",
        source_version="in force 2018-08-07",
    ),
    StatuteSource(
        statute="copyright",
        short_name="Copyright Act",
        title="Copyright Act, 5768-2007",
        source_url="https://www.wipo.int/wipolex/en/legislation/details/11509",
        section_unit="Section",
        source_version="in force 2008-05-25",
    ),
    StatuteSource(
        statute="commercial_torts",
        short_name="Commercial Torts Law",
        title="Commercial Torts Law, 5759-1999",
        source_url="https://www.wipo.int/wipolex/en/legislation/details/2375",
        section_unit="Article",
        source_version="1999",
    ),
)


@dataclass(frozen=True)
class ParsedSection:
    statute: str
    section_number: str  # e.g. "3" or "6"
    section_label: str  # e.g. "Section 3 Patents Law" / "Article 6 Commercial Torts Law"
    title: str | None
    text: str
    source_url: str


# A section-heading regex tuned for the WIPO Lex EN PDFs. The Israeli
# statutes use a mix of conventions; this regex captures the dominant
# pattern: a numeric token at the start of a line, followed by either a
# period or a paren'd subsection marker, followed by a section title or
# the text body.
#
# Examples that must match:
#   "1. Definitions"
#   "3. Patentable invention"
#   "Article 6. Trade secret"
#   "6. (a) A person shall not misappropriate ..."
#
# Examples that must NOT match: lines starting with "(a)" or "(1)" alone
# (those are subsections inside an already-opened section).
_SECTION_HEAD_RE = re.compile(
    r"""
    ^\s*
    (?:Section|Article|Sec\.|Art\.)?  # optional explicit unit prefix
    \s*
    (?P<num>\d{1,4}[A-Z]?)            # base number (1, 14, 167A, etc.)
    [.)]                              # period or close-paren after the number
    \s+
    (?P<rest>.+?)
    \s*$
    """,
    re.VERBOSE,
)


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace inside lines, preserve line breaks."""
    cleaned_lines = []
    for line in text.splitlines():
        stripped = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def extract_pdf_text(pdf_bytes: bytes) -> tuple[int, str]:
    """Return ``(page_count, plain_text)`` for a PDF buffer.

    Uses :mod:`pypdf`; WIPO Lex IL PDFs are text-bearing. Pages joined
    with two newlines so paragraph boundaries survive.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover — pypdf can fail per-page
            logger.warning("Skipping unreadable page: %s", exc)
            pages.append("")
    return len(reader.pages), _normalize_whitespace("\n\n".join(pages))


def parse_sections(source: StatuteSource, text: str) -> list[ParsedSection]:
    """Split a statute's plaintext into per-section rows.

    Looks for lines matching :data:`_SECTION_HEAD_RE` as section
    boundaries. Everything between two boundaries is captured as the
    body of the earlier section. Sections without an obvious title get
    a synthesized ``"Section N"`` label.
    """
    lines = text.splitlines()
    sections: list[ParsedSection] = []
    current_num: str | None = None
    current_title: str | None = None
    current_body: list[str] = []

    def _flush() -> None:
        if current_num is None:
            return
        body_joined = "\n".join(current_body).strip()
        full_text_lines: list[str] = []
        if current_title:
            full_text_lines.append(current_title)
        if body_joined:
            full_text_lines.append(body_joined)
        sections.append(
            ParsedSection(
                statute=source.statute,
                section_number=current_num,
                section_label=f"{source.section_unit} {current_num} {source.short_name}",
                title=current_title,
                text="\n\n".join(full_text_lines) or current_title or "",
                source_url=source.source_url,
            )
        )

    for raw in lines:
        match = _SECTION_HEAD_RE.match(raw)
        if match and _looks_like_section_head(match.group("rest")):
            _flush()
            current_num = match.group("num")
            current_title = match.group("rest").strip() or None
            current_body = []
        else:
            current_body.append(raw)
    _flush()
    return sections


def _looks_like_section_head(rest: str) -> bool:
    """Heuristic: does ``rest`` look like a section title rather than body text?

    A section heading typically starts with a capital letter and is
    relatively short (a clause or phrase, not a sentence). We accept any
    rest that starts with a non-lowercase character — this is loose, but
    the PDFs are well-structured enough that false positives are rare.
    """
    cleaned = rest.strip()
    if not cleaned:
        return False
    return not cleaned[0].islower()


class IlpoStatutesFetcher:
    """Async downloader for WIPO Lex IL PDFs."""

    def __init__(
        self,
        *,
        timeout: float = 120.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._client = httpx.AsyncClient(
            headers={"User-Agent": user_agent, "Accept": "application/pdf"},
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> IlpoStatutesFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def fetch(self, source: StatuteSource) -> bytes:
        retryer = default_retryer()
        async for attempt in retryer:
            with attempt:
                response = await self._client.get(source.source_url)
                response.raise_for_status()
                return response.content
        raise RuntimeError("unreachable: default_retryer reraises")


def write_corpus(
    sections: list[ParsedSection],
    output: Path,
    *,
    snapshot_date: str,
    source_version: str,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    try:
        conn.executescript(DDL)
        for section in sections:
            conn.execute(
                """
                INSERT INTO sections
                    (statute, section_number, section_label, title, text, source_url)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    section.statute,
                    section.section_number,
                    section.section_label,
                    section.title,
                    section.text,
                    section.source_url,
                ),
            )
        meta_rows = [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", snapshot_date),
            ("source_version", source_version),
            ("section_count", str(len(sections))),
        ]
        conn.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", meta_rows)
        conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.close()
    return len(sections)


async def build_corpus(
    output: Path,
    *,
    sources: tuple[StatuteSource, ...] = SOURCES,
) -> int:
    snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
    all_sections: list[ParsedSection] = []
    async with IlpoStatutesFetcher() as fetcher:
        for source in sources:
            t0 = time.monotonic()
            try:
                pdf_bytes = await fetcher.fetch(source)
            except Exception as exc:
                logger.warning("Skipping %s — fetch failed: %s", source.statute, exc)
                continue
            try:
                _pages, text = extract_pdf_text(pdf_bytes)
            except Exception as exc:
                logger.warning("Skipping %s — PDF extract failed: %s", source.statute, exc)
                continue
            sections = parse_sections(source, text)
            elapsed = time.monotonic() - t0
            logger.info(
                "Fetched %s (%d sections, %.2fs)",
                source.statute,
                len(sections),
                elapsed,
            )
            all_sections.extend(sections)
    return write_corpus(
        all_sections,
        output,
        snapshot_date=snapshot_date,
        source_version="WIPO Lex authoritative EN",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-build-ilpo-statutes-corpus",
        description=(
            "Download the five Israeli IP statutes from WIPO Lex and "
            "write a SQLite/FTS5 corpus consumable by "
            "patent_client_agents.ilpo_statutes. Run periodically; "
            "output is deterministic for a given snapshot of WIPO Lex."
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Path to write the corpus SQLite file.",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log per-statute progress.")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    started = time.monotonic()
    try:
        count = asyncio.run(build_corpus(args.output))
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
