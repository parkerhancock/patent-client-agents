"""Tests for the IPOS manuals corpus build script."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from patent_client_agents.ipos_manuals.corpus import build as build_mod
from patent_client_agents.ipos_manuals.corpus.build import (
    FetchedManual,
    ManualSource,
    ParsedSection,
    build_corpus,
    extract_pdf_text,
    main,
    parse_sections,
    write_corpus,
)


def test_parse_sections_recognises_dotted_labels():
    text = """
1.5.3 Inventive Step
An invention shall be taken to involve an inventive step if it is not obvious.

1.6 Industrial Applicability
An invention is capable of industrial application.

3.4 Distinctiveness
A trade mark must be distinctive.
""".strip()
    sections = parse_sections(text)
    labels = [s.section_label for s in sections]
    assert "1.5.3" in labels
    assert "1.6" in labels
    assert "3.4" in labels


def test_parse_sections_returns_empty_for_unstructured_text():
    sections = parse_sections("just some prose with no headings")
    assert sections == []


def test_extract_pdf_text_with_blank_pdf(tmp_path: Path):
    pypdf = pytest.importorskip("pypdf")
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    pdf_path = tmp_path / "blank.pdf"
    with pdf_path.open("wb") as fh:
        writer.write(fh)
    pages, text = extract_pdf_text(pdf_path.read_bytes())
    assert pages == 1
    assert isinstance(text, str)


def test_write_corpus_creates_sections_and_meta(tmp_path: Path):
    fetched = [
        FetchedManual(
            source=ManualSource(
                manual="peg",
                short_name="PEG",
                title="IPOS Patent Examination Guidelines",
                path="/peg.pdf",
            ),
            url="https://example.com/peg.pdf",
            pdf_pages=200,
            text=(
                "1.5.3 Inventive Step\n"
                "An invention involves an inventive step.\n"
                "1.6 Industrial Applicability\n"
                "An invention is capable of industrial application."
            ),
        ),
    ]
    db_path = tmp_path / "corpus.db"
    count = write_corpus(
        fetched,
        db_path,
        snapshot_date="2026-05-16",
        source_version="Jan 2026 release",
    )
    assert count >= 2
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT manual, section_label FROM sections ORDER BY section_label"
        ).fetchall()
        labels = {r[1] for r in rows}
        assert {"1.5.3", "1.6"}.issubset(labels)
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["snapshot_date"] == "2026-05-16"
        assert meta["source_version"] == "Jan 2026 release"
    finally:
        conn.close()


def test_write_corpus_falls_back_to_whole_manual_when_no_sections(tmp_path: Path):
    fetched = [
        FetchedManual(
            source=ManualSource(
                manual="designs",
                short_name="Designs Work Manual",
                title="IPOS Designs Work Manual",
                path="/designs.pdf",
            ),
            url="https://example.com/designs.pdf",
            pdf_pages=80,
            text="unstructured PDF text with no section markers",
        ),
    ]
    db_path = tmp_path / "corpus.db"
    count = write_corpus(fetched, db_path, snapshot_date="2026-05-16")
    assert count == 1
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT section_label, manual FROM sections").fetchone()
        assert row[0] == "0"
        assert row[1] == "designs"
    finally:
        conn.close()


def test_write_corpus_empty_input(tmp_path: Path):
    db_path = tmp_path / "empty.db"
    count = write_corpus([], db_path, snapshot_date="2026-05-16")
    assert count == 0


def test_build_corpus_uses_fetcher_and_writes(monkeypatch, tmp_path: Path):
    class _StubFetcher:
        def __init__(self, *_, **__):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def fetch(self, source: ManualSource) -> FetchedManual:
            return FetchedManual(
                source=source,
                url=f"https://stub/{source.path.lstrip('/')}",
                pdf_pages=10,
                text=f"1.5.3 {source.short_name} stub heading\nbody text",
            )

    monkeypatch.setattr(build_mod, "IposManualsFetcher", _StubFetcher)
    db_path = tmp_path / "corpus.db"
    sources = (
        ManualSource(
            manual="peg",
            short_name="PEG",
            title="IPOS Patent Examination Guidelines",
            path="/peg.pdf",
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

        async def fetch(self, source: ManualSource) -> FetchedManual:
            raise RuntimeError("upstream down")

    monkeypatch.setattr(build_mod, "IposManualsFetcher", _BoomFetcher)
    db_path = tmp_path / "corpus.db"
    sources = (
        ManualSource(
            manual="peg",
            short_name="PEG",
            title="IPOS Patent Examination Guidelines",
            path="/peg.pdf",
        ),
    )
    count = asyncio.run(build_corpus(db_path, sources=sources))
    assert count == 0


def test_main_invokes_build_corpus(monkeypatch, tmp_path: Path):
    async def _stub_build(output, *, sources=None, base_url=None, source_version=None):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"")
        return 7

    monkeypatch.setattr(build_mod, "build_corpus", _stub_build)
    out = tmp_path / "corpus.db"
    rc = main(["--output", str(out), "--source-version", "test"])
    assert rc == 0


def test_main_handles_keyboard_interrupt(monkeypatch, tmp_path: Path):
    def _boom(*_, **__):
        raise KeyboardInterrupt()

    monkeypatch.setattr(build_mod, "asyncio", MagicMock(run=_boom))
    out = tmp_path / "corpus.db"
    rc = main(["--output", str(out)])
    assert rc == 130


def test_fetcher_fetch_returns_text(monkeypatch):
    from patent_client_agents.ipos_manuals.corpus.build import IposManualsFetcher

    pypdf = pytest.importorskip("pypdf")
    # Build a minimal PDF in-memory
    import io

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    pdf_bytes = buf.getvalue()

    response = MagicMock()
    response.content = pdf_bytes
    response.raise_for_status = MagicMock()

    async def run():
        fetcher = IposManualsFetcher()
        fetcher._client = MagicMock()
        fetcher._client.get = AsyncMock(return_value=response)
        with patch("patent_client_agents.ipos_manuals.corpus.build.default_retryer") as r:

            class _AttemptContext:
                def __enter__(self):
                    return self

                def __exit__(self, *_):
                    return None

            async def _aiter():
                yield _AttemptContext()

            r.return_value.__aiter__ = lambda self: _aiter()
            source = ManualSource(
                manual="peg",
                short_name="PEG",
                title="IPOS Patent Examination Guidelines",
                path="/peg.pdf",
            )
            return await fetcher.fetch(source)

    result = asyncio.run(run())
    assert result.source.manual == "peg"
    assert result.pdf_pages == 1


def test_parsed_section_immutability():
    from dataclasses import FrozenInstanceError

    sec = ParsedSection(section_label="1.5.3", title="Test", text="body")
    with pytest.raises(FrozenInstanceError):
        sec.section_label = "1.5.4"  # type: ignore[misc]
