"""Tests for the IPOS manuals corpus build script.

The end-to-end tests run the real fetcher, discovery, parsers, and writer
against a fake IPOS site served by ``httpx2.MockTransport``. Only PDF text
extraction is replaced, so a "PDF" in these tests is its text as UTF-8 bytes.
The page and chapter fixtures copy the shapes found on ipos.gov.sg on
2026-11-19: link text with a size suffix, upload hosts other than
ipos.gov.sg, contents pages with dot leaders, and headings whose style
varies by chapter.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import httpx2
import pytest

from patent_client_agents.ipos_manuals.corpus import build as build_mod
from patent_client_agents.ipos_manuals.corpus.build import (
    SOURCES,
    build_corpus,
    discover_documents,
    document_version,
    extract_pdf_text,
    main,
    parse_chapter_sections,
    parse_sections,
)

PEG, TM, DESIGNS = SOURCES
UPLOADS = "https://isomer-user-content.by.gov.sg/61"


def _link(text: str, href: str) -> str:
    return f'<li><a href="{href}">{text} [PDF, 431 KB] <span>(opens in new tab)</span></a></li>'


PATENTS_PAGE = f"""<html><body><main>
{_link("Patents Formalities Manual", f"{UPLOADS}/aaa/patents-formalities-manual.pdf")}
{_link("Examination Guidelines for Patent Applications", f"{UPLOADS}/bbb/peg.pdf")}
{_link("Supplemental Guidance for the Examination of AI-related Patent Applications", f"{UPLOADS}/ccc/ai.pdf")}
<a href="/about-ip/patents/forms-and-fees-singapore/">Examination Guidelines for Patent Applications</a>
</main></body></html>"""

TRADE_MARKS_PAGE = f"""<html><body><main>
{_link("Trade Marks Infopack", f"{UPLOADS}/ddd/trade-marks-infopack.pdf")}
{_link("Cover Page and Contents", f"{UPLOADS}/eee/cover-page-and-contents.pdf")}
{_link("Chapter 22 - Assignment", "https://file.go.gov.sg/chapter22---assignment.pdf")}
{_link("Chapter 7 - Relative Grounds for Refusal of Registration", f"{UPLOADS}/fff/chapter-7.pdf")}
{_link("Chapter 7 - Relative Grounds (superseded)", f"{UPLOADS}/old/chapter-7-old.pdf")}
{_link("Chapter 2 – Colour Marks", f"{UPLOADS}/ggg/chapter-2.pdf")}
</main></body></html>"""

DESIGNS_PAGE = f"""<html><body><main>
{_link("Registered Designs - Guidelines for Non-Physical Products", f"{UPLOADS}/hhh/non-physical.pdf")}
{_link("Registered Designs Infopack", f"{UPLOADS}/iii/infopack.pdf")}
{_link("Information Note on Colours as a Design Feature", f"{UPLOADS}/jjj/colours.pdf")}
{_link("Information Note on the Interface between Registered Designs and Copyright", f"{UPLOADS}/kkk/copyright.pdf")}
{_link("Acceptable and Unacceptable Images", f"{UPLOADS}/lll/images.pdf")}
</main></body></html>"""

PEG_TEXT = """Examination Guidelines for Patent Applications at IPOS

1.1 Upon receiving a request, the Examiner conducts a search.
The search covers the state of the art.
1.2 The Guidelines aim to provide the Examiner with guidance.
8.A.1 Subject matter that is not an invention is excluded.
"""

CHAPTER_7 = """Version 9.1 (November 2022) Intellectual Property Office of Singapore

RELATIVE GROUNDS FOR REFUSAL OF REGISTRATION

Contents Page
1 INTRODUCTION ............................................................ 3
2 RELEVANT LEGISLATION ...................................... 4
5 CONFLICT WITH EARLIER TRADE MARKS ....................... 21
5.1 Step-by-step approach ................................................. 21
5.2.5.2.5 Where the earlier mark and/or the subject mark are composite marks
with a dominant element ................................................ 28

1 INTRODUCTION
This chapter deals with relative grounds for refusal.

2 RELEVANT LEGISLATION
Trade Marks Act 1998
8. —(1) A trade mark must not be registered if it is identical with an earlier trade mark.
10 or such other provision as appears to the Minister to be appropriate.

5 CONFLICT WITH EARLIER TRADE MARKS
5.1 Step-by-step approach
The examiner proceeds in three steps:
1. Compare the marks.
2. Compare the goods or services.
5.2.5.2.5 Where the earlier mark and/or the subject mark are composite marks
with a dominant element
The dominant element is given more weight.
"""

# Chapters 3 and 8 punctuate labels and mix heading case; PDF extraction also
# splits words differently in the body than in the contents page.
CHAPTER_2 = """Version 2.1 (November 2022) Intellectual Property Office of Singapore
COLOUR MARKS
1. Introduction 2
4. SECTION 7(3) OBJECTIONS APPLICABLE TO SHAPES .................. 6
4.3.1. American and British spelling ........ 9

1. Introduction
Colour marks are discussed here.
4. SECTION 7(3) O BJECTIONS APPLICABLE T O SHAPES
A shape objection may arise.
4.3.1. American and British spelling
Both spellings are accepted.
"""

COLOURS_NOTE = "Colours as a design feature\nThis note has no numbered sections."

DESIGN_GUIDELINES = """Introduction
1.1 Virtual designs refer to designs that do not have a physical form.
1.2 Immersive technologies may contain designs.
"""

PAGES = {
    "/about-ip/patents/guides/": PATENTS_PAGE,
    "/about-ip/trade-marks/tm-guides/": TRADE_MARKS_PAGE,
    "/about-ip/designs/guides/": DESIGNS_PAGE,
}
PDFS = {
    "/61/bbb/peg.pdf": PEG_TEXT,
    "/chapter22---assignment.pdf": "ASSIGNMENT\nNo contents page in this stub.",
    "/61/fff/chapter-7.pdf": CHAPTER_7,
    "/61/ggg/chapter-2.pdf": CHAPTER_2,
    "/61/hhh/non-physical.pdf": DESIGN_GUIDELINES,
    "/61/jjj/colours.pdf": COLOURS_NOTE,
    "/61/kkk/copyright.pdf": "Interface between registered designs and copyright.",
    "/61/lll/images.pdf": "Acceptable images.",
}


class FakeIpos:
    """Serves the guides pages and PDFs above and records every request."""

    def __init__(self) -> None:
        self.pages = dict(PAGES)
        self.pdfs = dict(PDFS)
        self.requested: list[str] = []

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requested.append(str(request.url))
        path = request.url.path
        if request.url.host == "www.ipos.gov.sg" and path in self.pages:
            return httpx2.Response(200, html=self.pages[path])
        if path in self.pdfs:
            return httpx2.Response(200, content=self.pdfs[path].encode())
        return httpx2.Response(404, text="Page not found")


@pytest.fixture
def ipos(monkeypatch: pytest.MonkeyPatch) -> FakeIpos:
    fake = FakeIpos()
    real_client = httpx2.AsyncClient

    def client(**kwargs: object) -> httpx2.AsyncClient:
        return real_client(transport=httpx2.MockTransport(fake.handle), **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(build_mod.httpx2, "AsyncClient", client)
    monkeypatch.setattr(build_mod, "extract_pdf_text", lambda data: (1, data.decode()))
    return fake


def _rows(db_path: Path, manual: str) -> dict[str, sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        found = conn.execute("SELECT * FROM sections WHERE manual = ?", (manual,)).fetchall()
        return {row["section_label"]: row for row in found}
    finally:
        conn.close()


# ─────────────────────────────── discovery ────────────────────────────────


def test_discover_selects_the_patent_guidelines_pdf_only() -> None:
    (document,) = discover_documents(PEG, PATENTS_PAGE, "https://www.ipos.gov.sg/x/")

    assert (document.key, document.title, document.url) == (
        None,
        "Examination Guidelines for Patent Applications",
        f"{UPLOADS}/bbb/peg.pdf",
    )


def test_discover_lists_trade_mark_chapters_in_numeric_order() -> None:
    documents = discover_documents(TM, TRADE_MARKS_PAGE, "https://www.ipos.gov.sg/x/")

    assert [(d.key, d.title) for d in documents] == [
        ("2", "Colour Marks"),
        ("7", "Relative Grounds for Refusal of Registration"),
        ("22", "Assignment"),
    ]
    assert documents[1].url == f"{UPLOADS}/fff/chapter-7.pdf"  # first link wins
    assert documents[2].url == "https://file.go.gov.sg/chapter22---assignment.pdf"


def test_discover_keys_design_documents_by_title() -> None:
    documents = discover_documents(DESIGNS, DESIGNS_PAGE, "https://www.ipos.gov.sg/x/")

    assert [d.key for d in documents] == [
        "guidelines-non-physical-products",
        "colours-design-feature",
        "interface-designs-copyright",
        "acceptable-unacceptable-images",
    ]


# ─────────────────────────────── parsing ──────────────────────────────────


def test_parse_sections_recognises_dotted_labels() -> None:
    sections = parse_sections(PEG_TEXT)

    assert [s.section_label for s in sections] == ["1.1", "1.2", "8.A.1"]
    assert sections[0].text.endswith("The search covers the state of the art.")


def test_parse_sections_returns_empty_for_unstructured_text() -> None:
    assert parse_sections("just some prose with no headings") == []


def test_chapter_headings_are_the_contents_entries_found_in_the_body() -> None:
    sections = {s.section_label: s for s in parse_chapter_sections(CHAPTER_7)}

    # Quoted legislation ("8. —(1)"), a stray numbered line ("10 or such"),
    # and list items ("1. Compare the marks.") are body text, not headings.
    assert list(sections) == ["1", "2", "5", "5.1", "5.2.5.2.5"]
    assert sections["1"].text == (
        "1 INTRODUCTION\nThis chapter deals with relative grounds for refusal."
    )
    assert "8. —(1) A trade mark must not be registered" in sections["2"].text
    assert "10 or such other provision" in sections["2"].text
    assert "2. Compare the goods or services." in sections["5.1"].text
    assert sections["5.2.5.2.5"].text.endswith("The dominant element is given more weight.")


def test_chapter_headings_tolerate_label_periods_and_extraction_spacing() -> None:
    sections = parse_chapter_sections(CHAPTER_2)

    assert [(s.section_label, s.title) for s in sections] == [
        ("1", "Introduction"),
        ("4", "SECTION 7(3) O BJECTIONS APPLICABLE T O SHAPES"),
        ("4.3.1", "American and British spelling"),
    ]


def test_chapter_without_a_contents_page_is_not_split() -> None:
    assert parse_chapter_sections("1 INTRODUCTION\nNo contents page.\n2 SCOPE\nText.") == []


def test_document_version_reads_the_cover_page() -> None:
    assert document_version(CHAPTER_7) == "9.1 (November 2022)"
    assert document_version(PEG_TEXT) is None


def test_extract_pdf_text_with_blank_pdf(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as fh:
        writer.write(fh)

    pages, text = extract_pdf_text(pdf_path.read_bytes())

    assert (pages, text.strip()) == (1, "")


# ─────────────────────────────── build ────────────────────────────────────


def test_build_corpus_follows_the_guides_pages(ipos: FakeIpos, tmp_path: Path) -> None:
    db_path = tmp_path / "corpus.db"

    count = asyncio.run(build_corpus(db_path, source_version="2026 edition"))

    peg, tm, designs = (_rows(db_path, m) for m in ("peg", "tm", "designs"))
    assert count == len(peg) + len(tm) + len(designs) == 17
    assert list(peg) == ["1.1", "1.2", "8.A.1"]
    assert (peg["1.1"]["breadcrumb"], peg["1.1"]["source_version"]) == (
        "PEG › 1.1",
        "2026 edition",
    )

    # Chapters restart their numbering, so labels carry the chapter.
    assert list(tm) == ["2:1", "2:4", "2:4.3.1", "7:1", "7:2", "7:5", "7:5.1", "7:5.2.5.2.5", "22"]
    section = tm["7:5.1"]
    assert section["breadcrumb"] == (
        "TM Work Manual › Chapter 7 Relative Grounds for Refusal of Registration › 5.1"
    )
    assert section["source_url"] == f"{UPLOADS}/fff/chapter-7.pdf"
    assert section["source_version"] == "9.1 (November 2022)"
    assert tm["2:1"]["source_version"] == "2.1 (November 2022)"
    # A chapter that can't be split is kept whole under its chapter number.
    assert (tm["22"]["title"], tm["22"]["breadcrumb"]) == (
        "Assignment",
        "TM Work Manual › Chapter 22 Assignment",
    )

    assert list(designs) == [
        "guidelines-non-physical-products:1.1",
        "guidelines-non-physical-products:1.2",
        "colours-design-feature",
        "interface-designs-copyright",
        "acceptable-unacceptable-images",
    ]
    assert designs["colours-design-feature"]["text"] == COLOURS_NOTE

    conn = sqlite3.connect(db_path)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        hits = conn.execute(
            "SELECT count(*) FROM sections_fts WHERE sections_fts MATCH 'dominant'"
        ).fetchone()
    finally:
        conn.close()
    assert (meta["section_count"], meta["manual_count"]) == ("17", "3")
    assert hits == (1,)
    # Nothing off the guides pages is fetched: not the infopacks, not the
    # formalities manual, not the superseded chapter.
    assert len(ipos.requested) == 3 + 8


def test_build_fails_when_a_guides_page_lists_no_matching_pdf(
    ipos: FakeIpos, tmp_path: Path
) -> None:
    ipos.pages["/about-ip/trade-marks/tm-guides/"] = "<html><body>Moved.</body></html>"
    db_path = tmp_path / "corpus.db"
    db_path.write_bytes(b"previous corpus")

    with pytest.raises(RuntimeError, match=r"No PDFs for the TM Work Manual .*tm-guides"):
        asyncio.run(build_corpus(db_path))

    assert db_path.read_bytes() == b"previous corpus"


def test_build_fails_when_a_listed_pdf_is_gone(ipos: FakeIpos, tmp_path: Path) -> None:
    del ipos.pdfs["/61/ggg/chapter-2.pdf"]
    db_path = tmp_path / "corpus.db"
    db_path.write_bytes(b"previous corpus")

    with pytest.raises(httpx2.HTTPStatusError, match="404"):
        asyncio.run(build_corpus(db_path))

    assert db_path.read_bytes() == b"previous corpus"


def test_main_invokes_build_corpus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _stub_build(output, *, sources=None, base_url=None, source_version=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"")
        return 7

    monkeypatch.setattr(build_mod, "build_corpus", _stub_build)

    assert main(["--output", str(tmp_path / "corpus.db"), "--source-version", "test"]) == 0


def test_main_handles_keyboard_interrupt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(*_, **__):
        raise KeyboardInterrupt()

    monkeypatch.setattr(build_mod, "build_corpus", _boom)

    assert main(["--output", str(tmp_path / "corpus.db")]) == 130
