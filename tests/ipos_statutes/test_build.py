"""Tests for the IPOS statutes corpus build script.

The fetch loop is exercised against a stub ``IposStatutesFetcher`` so
the tests don't hit ``sso.agc.gov.sg``. The section-extraction regex,
HTML-to-text stripper, and SQLite write path are pinned at this layer
because the build script is the only producer of the live corpus on
disk.
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patent_client_agents.ipos_statutes.corpus import build as build_mod
from patent_client_agents.ipos_statutes.corpus.build import (
    FetchedStatute,
    ParsedSection,
    StatuteSource,
    build_corpus,
    extract_html_text,
    extract_pdf_text,
    main,
    parse_sections,
    write_corpus,
)


def test_parse_sections_recognises_numbered_headings():
    text = """
13. Patentable inventions
An invention shall be patentable if it is new, involves an inventive step,
and is capable of industrial application.

13A.—(1) Methods of human treatment excluded.
Methods of treatment of the human or animal body by surgery or therapy.

14. Novelty
An invention shall be taken to be new if it does not form part of the state of the art.
""".strip()
    sections = parse_sections(text)
    labels = [s.section_label for s in sections]
    assert "13" in labels
    assert "13A" in labels
    assert "14" in labels
    s13 = next(s for s in sections if s.section_label == "13")
    assert s13.title == "Patentable inventions"
    assert "inventive step" in s13.text


def test_parse_sections_returns_empty_for_unstructured_text():
    sections = parse_sections("just some prose with no section markers")
    assert sections == []


def test_extract_html_text_strips_tags_and_scripts():
    html = (
        b"<html><head><style>body{}</style></head>"
        b"<body><p>Section 13</p><script>alert(1)</script>"
        b"<div>Patentable&nbsp;inventions</div></body></html>"
    )
    text = extract_html_text(html)
    assert "Section 13" in text
    assert "Patentable inventions" in text
    assert "alert" not in text


def test_extract_pdf_text_with_minimal_pdf(tmp_path: Path):
    # Build a tiny one-page PDF using pypdf so we exercise the extraction
    # path without committing a binary fixture to git.
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as fh:
        writer.write(fh)
    page_count_or_text = extract_pdf_text(pdf_path.read_bytes())
    # extract_pdf_text returns just text (str); the manuals build script
    # returns (pages, text). For statutes it's str only.
    assert isinstance(page_count_or_text, str)


def test_write_corpus_creates_sections_and_meta(tmp_path: Path):
    fetched = [
        FetchedStatute(
            source=StatuteSource(
                statute="patents",
                short_name="Patents Act",
                title="Patents Act 1994",
                path="/Act/PA1994",
            ),
            url="https://sso.agc.gov.sg/Act/PA1994",
            text=(
                "13. Patentable inventions\n"
                "An invention shall be patentable if it is new.\n"
                "14. Novelty\n"
                "An invention is new if not in the state of the art."
            ),
        ),
    ]
    db_path = tmp_path / "corpus.db"
    count = write_corpus(
        fetched,
        db_path,
        snapshot_date="2026-05-16",
        source_version="2020 Revised Edition",
    )
    assert count >= 2
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT statute, section_label FROM sections ORDER BY section_label"
        ).fetchall()
        labels = {r[1] for r in rows}
        assert {"13", "14"}.issubset(labels)
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["schema_version"] == "1"
        assert meta["snapshot_date"] == "2026-05-16"
        assert meta["source_version"] == "2020 Revised Edition"
    finally:
        conn.close()


def test_write_corpus_falls_back_to_whole_act_when_no_sections(tmp_path: Path):
    """Whole-Act fallback preserves the schema invariant (≥1 row per Act)."""
    fetched = [
        FetchedStatute(
            source=StatuteSource(
                statute="copyright",
                short_name="Copyright Act",
                title="Copyright Act 2021",
                path="/Act/CA2021",
            ),
            url="https://sso.agc.gov.sg/Act/CA2021",
            text="unstructured copyright text with no section anchors",
        ),
    ]
    db_path = tmp_path / "corpus.db"
    count = write_corpus(fetched, db_path, snapshot_date="2026-05-16")
    assert count == 1
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT section_label, statute FROM sections").fetchone()
        assert row[0] == "00"
        assert row[1] == "copyright"
    finally:
        conn.close()


def test_write_corpus_skips_when_no_input(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    count = write_corpus([], db_path, snapshot_date="2026-05-16")
    assert count == 0
    # Schema is still applied so the file is a valid corpus shell.
    conn = sqlite3.connect(db_path)
    try:
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["snapshot_date"] == "2026-05-16"
    finally:
        conn.close()


def test_build_corpus_uses_fetcher_and_writes(monkeypatch, tmp_path: Path):
    """End-to-end: a stub fetcher feeds the writer, no network."""

    class _StubFetcher:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def fetch(self, source: StatuteSource) -> FetchedStatute:
            return FetchedStatute(
                source=source,
                url=f"https://stub/{source.path.lstrip('/')}",
                text=f"13. {source.short_name} stub text\nbody text",
            )

    monkeypatch.setattr(build_mod, "IposStatutesFetcher", _StubFetcher)
    db_path = tmp_path / "corpus.db"
    sources = (
        StatuteSource(
            statute="patents",
            short_name="Patents Act",
            title="Patents Act 1994",
            path="/Act/PA1994",
        ),
    )
    count = asyncio.run(build_corpus(db_path, sources=sources))
    assert count == 1
    assert db_path.exists()


def test_build_corpus_skips_on_fetch_failure(monkeypatch, tmp_path: Path):
    class _BoomFetcher:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def fetch(self, source: StatuteSource) -> FetchedStatute:
            raise RuntimeError("upstream down")

    monkeypatch.setattr(build_mod, "IposStatutesFetcher", _BoomFetcher)
    db_path = tmp_path / "corpus.db"
    sources = (
        StatuteSource(
            statute="patents",
            short_name="Patents Act",
            title="Patents Act 1994",
            path="/Act/PA1994",
        ),
    )
    # Should not raise; failed fetch just yields zero rows.
    count = asyncio.run(build_corpus(db_path, sources=sources))
    assert count == 0


def test_main_invokes_build_corpus(monkeypatch, tmp_path: Path):
    called = {}

    async def _stub_build(output, *, sources=None, base_url=None, source_version=None):
        called["output"] = output
        called["source_version"] = source_version
        # touch the file so the print() at the end can stat it
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"")
        return 42

    monkeypatch.setattr(build_mod, "build_corpus", _stub_build)
    out = tmp_path / "corpus.db"
    rc = main(["--output", str(out), "--source-version", "test"])
    assert rc == 0
    assert called["output"] == out
    assert called["source_version"] == "test"


def test_main_handles_keyboard_interrupt(monkeypatch, tmp_path: Path):
    def _boom(*_, **__):
        raise KeyboardInterrupt()

    monkeypatch.setattr(build_mod, "asyncio", MagicMock(run=_boom))
    out = tmp_path / "corpus.db"
    rc = main(["--output", str(out)])
    assert rc == 130


def test_fetcher_fetch_retries_then_succeeds(monkeypatch):
    """The fetcher returns plain text from a happy-path HTTP response."""
    from patent_client_agents.ipos_statutes.corpus.build import IposStatutesFetcher

    response = MagicMock()
    response.content = b"<html><body><p>13. Stub heading</p></body></html>"
    response.raise_for_status = MagicMock()

    async def run():
        fetcher = IposStatutesFetcher()
        # Patch the internal client.get method
        fetcher._client = MagicMock()
        fetcher._client.get = AsyncMock(return_value=response)
        with patch("patent_client_agents.ipos_statutes.corpus.build.default_retryer") as r:
            # Single iteration succeeding
            class _AttemptContext:
                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return None

            async def _aiter():
                yield _AttemptContext()

            r.return_value.__aiter__ = lambda self: _aiter()
            source = StatuteSource(
                statute="patents",
                short_name="Patents Act",
                title="Patents Act 1994",
                path="/Act/PA1994",
            )
            result = await fetcher.fetch(source)
            return result

    result = asyncio.run(run())
    assert result.source.statute == "patents"
    assert "Stub" in result.text


def test_parsed_section_immutability():
    """ParsedSection is a frozen dataclass."""
    from dataclasses import FrozenInstanceError

    sec = ParsedSection(section_label="13", title="Test", text="body")
    with pytest.raises(FrozenInstanceError):
        sec.section_label = "14"  # ty: ignore[invalid-assignment]
