"""Download UPC legal-document PDFs and emit a queryable SQLite/FTS5 corpus.

Console-script entry point for
``patent-client-agents-build-upc-statutes-corpus``. Each instrument is
downloaded from its stable URL on ``unifiedpatentcourt.org``, parsed
with :mod:`pypdf` to plaintext, and persisted as one row per
(instrument, language) pair.

Run manually for an interactive refresh::

    patent-client-agents-build-upc-statutes-corpus \\
        --output ~/.cache/patent_client_agents/upc_statutes.db

For cloud deploys, run during image build and point
``UPC_STATUTES_CORPUS_PATH`` at the output path. The wheel ships the
builder, not the corpus.

The source URLs are the **consolidated** versions of the RoP and Court
Fees (these include amendments adopted after the original 2022
publications); for UPCA / Statute / CoC the singular originals are used.
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

DEFAULT_BASE_URL = "https://www.unifiedpatentcourt.org"
DEFAULT_USER_AGENT = (
    "patent-client-agents-upc/0.11 (+https://github.com/parkerhancock/patent-client-agents)"
)


@dataclass(frozen=True)
class InstrumentSource:
    instrument: str  # stable key
    short_name: str  # citation form
    title: str  # full title
    language: str  # 'en' | 'fr' | 'de'
    path: str  # path relative to base_url


# Canonical source list as of 2026-05. Verified live against
# unifiedpatentcourt.org/en/court/legal-documents — the consolidated
# RoP and Fees PDFs incorporate post-2022 amendments. UPCA and Statute
# share a single PDF (the Statute is Annex I to UPCA); for those, the
# 'statute' rows reuse the UPCA PDF and the parser extracts the Annex I
# portion when section-level extraction lands in v0.12.0. For now the
# UPCA row is the only Annex-bearing instrument.
SOURCES: tuple[InstrumentSource, ...] = (
    InstrumentSource(
        instrument="upca",
        short_name="UPCA",
        title="Agreement on a Unified Patent Court (including Annex I, Statute of the UPC)",
        language="en",
        path="/sites/default/files/upc_documents/agreement-on-a-unified-patent-court.pdf",
    ),
    InstrumentSource(
        instrument="upca",
        short_name="UPCA",
        title="Accord relatif à une juridiction unifiée du brevet",
        language="fr",
        path="/sites/default/files/upc_documents/accord-relatif-a-une-juridiction-unifiee-du-brevet.pdf",
    ),
    InstrumentSource(
        instrument="upca",
        short_name="UPCA",
        title="Übereinkommen über ein einheitliches Patentgericht",
        language="de",
        path="/sites/default/files/upc_documents/ubereinkommen-uber-ein-einheitliches-patentgericht-.pdf",
    ),
    InstrumentSource(
        instrument="rop",
        short_name="RoP",
        title="Consolidated Rules of Procedure of the Unified Patent Court",
        language="en",
        path="/sites/default/files/upc_documents/Consolidated Rules of Procedure UPC_EN.pdf",
    ),
    InstrumentSource(
        instrument="rop",
        short_name="RoP",
        title="Règlement de procédure de la juridiction unifiée du brevet (version consolidée)",
        language="fr",
        path="/sites/default/files/upc_documents/Consolidated Rules of Procedure UPC_FR.pdf",
    ),
    InstrumentSource(
        instrument="rop",
        short_name="RoP",
        title="Konsolidierte Verfahrensordnung des Einheitlichen Patentgerichts",
        language="de",
        path="/sites/default/files/upc_documents/Consolidated Rules of Procedure UPC_DE.pdf",
    ),
    InstrumentSource(
        instrument="fees",
        short_name="Fees",
        title="Consolidated Table of Court Fees and Recoverable Costs",
        language="en",
        path="/sites/default/files/upc_documents/Consolidated Table of Court fees_EN.pdf",
    ),
    InstrumentSource(
        instrument="fees",
        short_name="Fees",
        title="Tableau consolidé des frais de procédure et des dépens recouvrables",
        language="fr",
        path="/sites/default/files/upc_documents/Consolidated Table of Court fees_FR.pdf",
    ),
    InstrumentSource(
        instrument="fees",
        short_name="Fees",
        title="Konsolidierte Tabelle der Gerichtsgebühren und erstattungsfähigen Kosten",
        language="de",
        path="/sites/default/files/upc_documents/Consolidated Table of Court fees_DE.pdf",
    ),
)


@dataclass(frozen=True)
class FetchedInstrument:
    source: InstrumentSource
    url: str
    pdf_pages: int
    text: str


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace but preserve paragraph-style line breaks.

    PDFs extract with abundant spurious whitespace inside lines and few
    deliberate line breaks. We collapse internal whitespace but leave
    newlines alone so callers can still identify paragraph boundaries.
    """
    cleaned_lines = []
    for line in text.splitlines():
        stripped = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(stripped)
    return "\n".join(cleaned_lines)


def extract_pdf_text(pdf_bytes: bytes) -> tuple[int, str]:
    """Return ``(page_count, plain_text)`` for a PDF buffer.

    Uses :mod:`pypdf` for text extraction — UPC documents are PDF/A
    with embedded text (no OCR required). Pages are joined with two
    newlines so paragraph boundaries are preserved.
    """
    reader = PdfReader(BytesIO(pdf_bytes))
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception as exc:  # pragma: no cover — pypdf can occasionally fail per page
            logger.warning("Skipping unreadable page: %s", exc)
            pages.append("")
    return len(reader.pages), _normalize_whitespace("\n\n".join(pages))


class UpcStatutesFetcher:
    """Async downloader for UPC source PDFs."""

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
            headers={"User-Agent": user_agent, "Accept": "application/pdf"},
            timeout=httpx.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> UpcStatutesFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def fetch(self, source: InstrumentSource) -> FetchedInstrument:
        retryer = default_retryer()
        async for attempt in retryer:
            with attempt:
                response = await self._client.get(source.path)
                response.raise_for_status()
                pages, text = extract_pdf_text(response.content)
                return FetchedInstrument(
                    source=source,
                    url=f"{self._base_url}{source.path}",
                    pdf_pages=pages,
                    text=text,
                )
        raise RuntimeError("unreachable: default_retryer reraises")


def write_corpus(instruments: list[FetchedInstrument], output: Path, *, snapshot_date: str) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    conn = sqlite3.connect(output)
    try:
        conn.executescript(DDL)
        for fetched in instruments:
            src = fetched.source
            conn.execute(
                """
                INSERT INTO instruments
                    (instrument, language, short_name, title,
                     source_url, source_version, pdf_pages, text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    src.instrument,
                    src.language,
                    src.short_name,
                    src.title,
                    fetched.url,
                    None,  # consolidated PDFs don't carry a discrete version label
                    fetched.pdf_pages,
                    fetched.text,
                ),
            )
        meta_rows = [
            ("schema_version", str(SCHEMA_VERSION)),
            ("snapshot_date", snapshot_date),
            ("instrument_count", str(len(instruments))),
        ]
        conn.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", meta_rows)
        conn.execute("INSERT INTO instruments_fts(instruments_fts) VALUES ('optimize')")
        conn.commit()
        conn.isolation_level = None
        conn.execute("VACUUM")
    finally:
        conn.close()
    return len(instruments)


async def build_corpus(
    output: Path,
    *,
    sources: tuple[InstrumentSource, ...] = SOURCES,
    base_url: str = DEFAULT_BASE_URL,
) -> int:
    snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
    fetched: list[FetchedInstrument] = []
    async with UpcStatutesFetcher(base_url=base_url) as fetcher:
        for source in sources:
            t0 = time.monotonic()
            try:
                instrument = await fetcher.fetch(source)
            except Exception as exc:
                logger.warning("Skipping %s/%s — %s", source.instrument, source.language, exc)
                continue
            elapsed = time.monotonic() - t0
            logger.info(
                "Fetched %s/%s (%d pages, %d chars, %.2fs)",
                source.instrument,
                source.language,
                instrument.pdf_pages,
                len(instrument.text),
                elapsed,
            )
            fetched.append(instrument)
    return write_corpus(fetched, output, snapshot_date=snapshot_date)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="patent-client-agents-build-upc-statutes-corpus",
        description=(
            "Download UPC legal-document PDFs and write a SQLite/FTS5 "
            "corpus consumable by patent_client_agents.upc_statutes. "
            "Run periodically; output is deterministic for a given "
            "snapshot of unifiedpatentcourt.org."
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
        help=f"Override UPC base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log per-document progress.")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    started = time.monotonic()
    try:
        count = asyncio.run(build_corpus(args.output, base_url=args.base_url))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    elapsed = time.monotonic() - started
    print(
        f"Wrote {count} instruments to {args.output} in {elapsed:.1f}s",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
