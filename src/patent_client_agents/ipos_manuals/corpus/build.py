"""Download IPOS examination + work manuals and emit a SQLite/FTS5 corpus.

Console-script entry point for
``patent-client-agents-build-ipos-manuals-corpus``. IPOS publishes each
manual as one or more PDFs linked from a "guides" page on its website.
The PDF addresses carry upload identifiers that change whenever IPOS
replaces a file, so the builder reads each guides page, picks out the
manual's PDFs by their link text, downloads them, parses them with
:mod:`pypdf` to plaintext, and persists section rows (with a
whole-document fallback when section headings aren't extractable).

The build fails if a manual's PDFs can't be found or downloaded. An
empty or partial corpus is worse than no new corpus: it replaces a good
one and answers every search with nothing.

Run manually for an interactive refresh::

    patent-client-agents-build-ipos-manuals-corpus \\
        --output ~/.cache/patent_client_agents/ipos_manuals.db

For cloud deploys, run during image build and point
``IPOS_MANUALS_CORPUS_PATH`` at the output path. The wheel ships the
builder, not the corpus.
"""

from __future__ import annotations

import argparse
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx2
from lxml import html
from pypdf import PdfReader

from mcp_data_core.resilience import default_retryer
from patent_client_agents.shared.corpus import atomic_output, run_build_cli

from .schema import DDL, SCHEMA_VERSION

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://www.ipos.gov.sg"
DEFAULT_USER_AGENT = (
    "patent-client-agents-ipos/0.20 (+https://github.com/parkerhancock/patent-client-agents)"
)


@dataclass(frozen=True)
class ManualSource:
    """One IPOS manual and where IPOS lists its PDFs.

    ``manual`` is the lowercase key written into the corpus.
    ``short_name`` is the citation-ready abbreviation (``PEG``,
    ``TM Work Manual``, ``Designs Guidelines``).

    ``index_path`` is the IPOS guides page that links the manual's PDFs.
    ``link_pattern`` is matched against each link's text; a link that
    matches is one document of the manual. A ``key`` group names the
    document within the manual (the chapter number), and a ``title``
    group gives its title. A pattern with no ``key`` group either selects
    the manual's only document or, with ``multi_document``, selects
    several documents keyed by a slug of their titles.

    ``chaptered`` selects the heading parser for documents laid out as a
    Trade Marks Work Manual chapter: a contents page followed by numbered
    headings.
    """

    manual: str
    short_name: str
    title: str
    index_path: str
    link_pattern: re.Pattern[str]
    multi_document: bool = False
    chaptered: bool = False


# The IPOS site was rebuilt in 2026 and may be rearranged again; the build
# script accepts ``--base-url`` so a deployment can follow a host change
# without a code change. A moved guides page needs ``index_path`` updated.
SOURCES: tuple[ManualSource, ...] = (
    ManualSource(
        manual="peg",
        short_name="PEG",
        title="IPOS Patent Examination Guidelines",
        index_path="/about-ip/patents/guides/",
        link_pattern=re.compile(r"^Examination Guidelines for Patent Applications$", re.I),
    ),
    ManualSource(
        manual="tm",
        short_name="TM Work Manual",
        title="IPOS Trade Marks Work Manual",
        index_path="/about-ip/trade-marks/tm-guides/",
        link_pattern=re.compile(r"^Chapter\s+(?P<key>\d+)\s*[-–—]\s*(?P<title>.+)$", re.I),
        multi_document=True,
        chaptered=True,
    ),
    # IPOS no longer publishes a single Designs Work Manual. Its designs
    # guidance is a set of shorter guidelines and information notes.
    ManualSource(
        manual="designs",
        short_name="Designs Guidelines",
        title="IPOS Registered Designs Guidelines and Information Notes",
        index_path="/about-ip/designs/guides/",
        link_pattern=re.compile(
            r"^(?P<title>Registered Designs\s*[-–—]\s*Guidelines\b.+"
            r"|Information Note on .+"
            r"|Acceptable and Unacceptable Images)$",
            re.I,
        ),
        multi_document=True,
    ),
)


@dataclass(frozen=True)
class ManualDocument:
    """One PDF of a manual, as listed on its guides page."""

    key: str | None
    title: str
    url: str


@dataclass(frozen=True)
class FetchedDocument:
    """A document's full text and where it came from."""

    source: ManualSource
    document: ManualDocument
    pdf_pages: int
    text: str


@dataclass(frozen=True)
class ParsedSection:
    """A single section extracted from a document."""

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


# ---------------------------------------------------------------------------
# Guides-page discovery
# ---------------------------------------------------------------------------

# IPOS appends "[PDF, 431 KB]" and "(opens in new tab)" to a link's text.
_LINK_SUFFIX_RE = re.compile(r"\s*(?:\[PDF[^\]]*\]|\(opens in new tab\))\s*", re.I)

# Words dropped when a document title becomes a document key.
_SLUG_STOPWORDS = frozenset(
    "a an and as between for information note of on registered the to".split()
)


def _slugify(title: str) -> str:
    words = re.findall(r"[a-z0-9]+", title.lower())
    kept = [w for w in words if w not in _SLUG_STOPWORDS]
    # "Registered Designs - Guidelines for ..." would otherwise lead with
    # "designs", which says nothing inside the designs manual.
    if len(kept) > 1 and kept[0] == "designs":
        kept = kept[1:]
    return "-".join(kept or words)


def discover_documents(source: ManualSource, page_html: str, page_url: str) -> list[ManualDocument]:
    """Pick a manual's PDF links out of its IPOS guides page.

    Returns documents in page order, except numbered chapters, which are
    returned in numeric order. A document key that appears twice keeps its
    first link.
    """
    tree = html.fromstring(page_html)
    documents: dict[str | None, ManualDocument] = {}
    for anchor in tree.iter("a"):
        href = (anchor.get("href") or "").strip()
        if not urlsplit(href).path.lower().endswith(".pdf"):
            continue
        text = _LINK_SUFFIX_RE.sub(" ", " ".join(anchor.text_content().split())).strip()
        match = source.link_pattern.match(text)
        if not match:
            continue
        groups = match.groupdict()
        title = (groups.get("title") or text).strip()
        key = groups.get("key")
        if key is None and source.multi_document:
            key = _slugify(title)
        if not source.multi_document:
            key = None
        documents.setdefault(key, ManualDocument(key=key, title=title, url=urljoin(page_url, href)))

    found = list(documents.values())
    if all(doc.key is not None and doc.key.isdigit() for doc in found):
        found.sort(key=lambda doc: int(doc.key or 0))
    return found


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

# Matches dotted section labels common to IPOS manuals:
#   "1.5.3 Title here"
#   "4.A.2 Subsection"
#   "1.5 Heading"
_SECTION_HEADER_RE = re.compile(
    r"^(?P<label>\d+(?:\.\d+){1,3}|\d+\.[A-Z](?:\.\d+)?)\s+(?P<title>[A-Z][^\n]{0,140})$",
    re.MULTILINE,
)


def _sections_from_matches(text: str, matches: list[re.Match[str]]) -> list[ParsedSection]:
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


def parse_sections(text: str) -> list[ParsedSection]:
    """Split a flat manual plain-text into per-section rows.

    Manuals expose section starts as ``"<dotted-label> <title-cased
    heading>"`` lines. When the regex finds zero matches we return an
    empty list and the caller falls back to a whole-document row.
    """
    return _sections_from_matches(text, list(_SECTION_HEADER_RE.finditer(text)))


# A Trade Marks Work Manual chapter opens with a contents page and then
# repeats each entry as a heading in the body. Chapters disagree on style:
# "5 CONFLICT WITH EARLIER TRADE MARKS", "4. General approach", and
# "4.3.1. American and British spelling" all occur, down to six levels.
# Quoted legislation ("7. —(1) The following must not be registered") and
# numbered lists also start lines with a number, so a body line counts as
# a heading only when the contents page lists the same number and title.
_CHAPTER_HEADING_RE = re.compile(
    r"^(?P<label>\d{1,2}(?:\.\d{1,2}){0,5})\.?[ \t]+(?P<title>[A-Za-z“\"‘'][^\n]{1,160})$",
    re.MULTILINE,
)
# What the contents page appends to a title: dot leaders, a page number.
_CONTENTS_SUFFIX_RE = re.compile(r"\s*\.{3,}.*$|\s+\d{1,3}$")
_TITLE_PREFIX = 12


def _title_key(title: str) -> str:
    """Reduce a title to what survives PDF extraction: letters and digits.

    Extraction splits words differently on each page ("O BJECTIONS" in the
    body, "OBJECTIONS" in the contents), so spacing and case can't be compared.
    """
    return re.sub(r"[^a-z0-9]", "", _CONTENTS_SUFFIX_RE.sub("", title).lower())[:_TITLE_PREFIX]


def _heading_key(match: re.Match[str]) -> tuple[str, str]:
    return match.group("label"), _title_key(match.group("title"))


def parse_chapter_sections(text: str) -> list[ParsedSection]:
    """Split a Trade Marks Work Manual chapter into per-heading rows.

    The contents page runs from its first entry to the line where that
    entry's heading comes round again without a page number; the body
    starts there. Returns an empty list when the chapter has no contents
    page or its first entry never reappears.
    """
    lines = list(_CHAPTER_HEADING_RE.finditer(text))
    first_entry = next(
        (i for i, m in enumerate(lines) if _CONTENTS_SUFFIX_RE.search(m.group("title"))), None
    )
    if first_entry is None:
        return []
    opening = _heading_key(lines[first_entry])
    body_start = next(
        (
            i
            for i in range(first_entry + 1, len(lines))
            if _heading_key(lines[i]) == opening
            and not _CONTENTS_SUFFIX_RE.search(lines[i].group("title"))
        ),
        None,
    )
    if body_start is None:
        return []

    listed: dict[str, str] = {}
    for match in lines[:body_start]:
        listed.setdefault(*_heading_key(match))
    body: list[re.Match[str]] = []
    seen: set[str] = set()
    for match in lines[body_start:]:
        label, title = _heading_key(match)
        if label in seen or listed.get(label) != title:
            continue
        seen.add(label)
        body.append(match)
    return _sections_from_matches(text, body)


# "Version 9.1 (November 2022)" on a work manual chapter's cover page.
_VERSION_RE = re.compile(r"\bVersion\s+(?P<number>\d+(?:\.\d+)*)\s*\((?P<date>[A-Za-z]+\s+\d{4})\)")


def document_version(text: str) -> str | None:
    """Return a document's own version label, when its cover page has one."""
    match = _VERSION_RE.search(text[:4000])
    return f"{match.group('number')} ({match.group('date')})" if match else None


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


class IposManualsFetcher:
    """Async reader of IPOS guides pages and the manual PDFs they link."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 120.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx2.AsyncClient(
            headers={"User-Agent": user_agent},
            timeout=httpx2.Timeout(timeout, connect=10.0),
            follow_redirects=True,
        )

    async def __aenter__(self) -> IposManualsFetcher:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self._client.aclose()

    async def _get(self, url: str) -> httpx2.Response:
        async for attempt in default_retryer():
            with attempt:
                response = await self._client.get(url)
                response.raise_for_status()
                return response
        raise RuntimeError("unreachable: default_retryer reraises")

    async def discover(self, source: ManualSource) -> list[ManualDocument]:
        """List a manual's documents from its IPOS guides page."""
        page_url = f"{self._base_url}{source.index_path}"
        response = await self._get(page_url)
        return discover_documents(source, response.text, page_url)

    async def fetch(self, source: ManualSource, document: ManualDocument) -> FetchedDocument:
        response = await self._get(document.url)
        pages, text = extract_pdf_text(response.content)
        return FetchedDocument(source=source, document=document, pdf_pages=pages, text=text)


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def _document_rows(fetched: FetchedDocument) -> list[tuple[str, str | None, str, str]]:
    """Return ``(section_label, title, breadcrumb, text)`` rows for one document.

    A document of a multi-document manual prefixes its labels with its key
    (``7:5.2.1`` is section 5.2.1 of chapter 7), because every chapter
    restarts its numbering.
    """
    src, doc = fetched.source, fetched.document
    sections = (parse_chapter_sections if src.chaptered else parse_sections)(fetched.text)
    if doc.key is None:
        if not sections:
            return [("0", src.title, f"{src.short_name} › 0", fetched.text)]
        return [
            (sec.section_label, sec.title, f"{src.short_name} › {sec.section_label}", sec.text)
            for sec in sections
        ]

    where = f"Chapter {doc.key} {doc.title}" if doc.key.isdigit() else doc.title
    if not sections:
        return [(doc.key, doc.title, f"{src.short_name} › {where}", fetched.text)]
    return [
        (
            f"{doc.key}:{sec.section_label}",
            sec.title,
            f"{src.short_name} › {where} › {sec.section_label}",
            sec.text,
        )
        for sec in sections
    ]


def write_corpus(
    documents: list[FetchedDocument],
    output: Path,
    *,
    snapshot_date: str,
    source_version: str | None = None,
) -> int:
    with atomic_output(output) as tmp_path:
        conn = sqlite3.connect(tmp_path)
        section_count = 0
        manuals: set[str] = set()
        try:
            conn.executescript(DDL)
            for fetched in documents:
                src = fetched.source
                manuals.add(src.manual)
                version = document_version(fetched.text) or source_version
                seen: set[str] = set()
                for label, title, breadcrumb, text in _document_rows(fetched):
                    if label in seen:
                        logger.warning(
                            "Duplicate section %s %s; keeping the first", src.manual, label
                        )
                        continue
                    seen.add(label)
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
                            label,
                            title,
                            breadcrumb,
                            fetched.document.url,
                            version,
                            text,
                        ),
                    )
                    section_count += 1
            meta_rows: list[tuple[str, str]] = [
                ("schema_version", str(SCHEMA_VERSION)),
                ("snapshot_date", snapshot_date),
                ("section_count", str(section_count)),
                ("manual_count", str(len(manuals))),
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
    """Fetch every manual and write the corpus.

    Raises ``RuntimeError`` when a guides page lists none of a manual's
    PDFs, and re-raises a download failure. Nothing is written in either
    case, so an existing corpus at ``output`` is left as it was.
    """
    snapshot_date = datetime.now(UTC).strftime("%Y-%m-%d")
    fetched: list[FetchedDocument] = []
    async with IposManualsFetcher(base_url=base_url) as fetcher:
        for source in sources:
            documents = await fetcher.discover(source)
            if not documents:
                raise RuntimeError(
                    f"No PDFs for the {source.short_name} found on "
                    f"{base_url.rstrip('/')}{source.index_path}. IPOS has probably "
                    f"moved the page or renamed its links; update SOURCES."
                )
            for document in documents:
                t0 = time.monotonic()
                result = await fetcher.fetch(source, document)
                logger.info(
                    "Fetched %s %s (%d pages, %d chars, %.2fs)",
                    source.manual,
                    document.key or document.title,
                    result.pdf_pages,
                    len(result.text),
                    time.monotonic() - t0,
                )
                fetched.append(result)
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
            "Download the IPOS Patent Examination Guidelines, Trade Marks "
            "Work Manual chapters, and registered designs guidelines, and "
            "write a SQLite/FTS5 corpus consumable by "
            "patent_client_agents.ipos_manuals."
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
        help=(
            "Version label for documents that don't state their own "
            "(work manual chapters do, on their cover page)."
        ),
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log per-document progress.")
    args = parser.parse_args(argv)
    return run_build_cli(
        lambda: build_corpus(
            args.output,
            base_url=args.base_url,
            source_version=args.source_version,
        ),
        verbose=args.verbose,
        done=lambda count, elapsed: f"Wrote {count} sections to {args.output} in {elapsed:.1f}s",
        to_stderr=True,
        catch_errors=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
