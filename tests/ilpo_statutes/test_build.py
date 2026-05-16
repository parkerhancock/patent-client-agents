"""Tests for the ILPO statutes corpus builder.

We don't fetch the real WIPO Lex PDFs in unit tests — that's a build-CLI
smoke task, not a unit test. We do exercise:

* ``parse_sections`` on synthetic, easy-to-read plaintext.
* ``write_corpus`` round-trip (rows + meta).
* The argparse main loop with a mocked ``build_corpus`` coroutine.
* ``IlpoStatutesFetcher`` HTTP shape with ``httpx.MockTransport``.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from patent_client_agents.ilpo_statutes.corpus.build import (
    SOURCES,
    IlpoStatutesFetcher,
    StatuteSource,
    _looks_like_section_head,
    _normalize_whitespace,
    build_corpus,
    main,
    parse_sections,
    write_corpus,
)
from patent_client_agents.ilpo_statutes.corpus.schema import SCHEMA_VERSION


def _mock_http(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# ──────────────────────────────────────────────────────────────────────
# Static source catalog
# ──────────────────────────────────────────────────────────────────────


def test_sources_cover_five_statutes() -> None:
    keys = {s.statute for s in SOURCES}
    assert keys == {
        "patents",
        "trademarks",
        "designs",
        "copyright",
        "commercial_torts",
    }


def test_commercial_torts_uses_article_unit() -> None:
    """Commercial Torts Law sections are styled 'Article N' per the EN translation."""
    ct = next(s for s in SOURCES if s.statute == "commercial_torts")
    assert ct.section_unit == "Article"


def test_other_statutes_use_section_unit() -> None:
    for source in SOURCES:
        if source.statute != "commercial_torts":
            assert source.section_unit == "Section"


# ──────────────────────────────────────────────────────────────────────
# Whitespace + heading-heuristic helpers
# ──────────────────────────────────────────────────────────────────────


def test_normalize_whitespace_collapses_inner_runs() -> None:
    text = "  a    b\n  c   d   "
    assert _normalize_whitespace(text) == "a b\nc d"


def test_looks_like_section_head_capital_starts() -> None:
    assert _looks_like_section_head("Definitions")
    assert _looks_like_section_head("Patentable invention")
    assert _looks_like_section_head("A Person Shall Not")


def test_looks_like_section_head_lowercase_rejected() -> None:
    # Lowercase rest is body text, not a section head.
    assert not _looks_like_section_head("of the previous section")
    assert not _looks_like_section_head("")


# ──────────────────────────────────────────────────────────────────────
# Section parser
# ──────────────────────────────────────────────────────────────────────


def test_parse_sections_splits_on_numbered_headings() -> None:
    source = StatuteSource(
        statute="patents",
        short_name="Patents Law",
        title="Patents Law, 5727-1967",
        source_url="https://example.com/patents.pdf",
        section_unit="Section",
        source_version="test",
    )
    text = (
        "1. Definitions\n"
        "In this Law definitions follow.\n"
        "2. Scope\n"
        "This Law applies to inventions.\n"
        "3. Patentable invention\n"
        "An invention is patentable if it meets the criteria.\n"
    )
    sections = parse_sections(source, text)
    assert [s.section_number for s in sections] == ["1", "2", "3"]
    assert sections[0].title == "Definitions"
    assert sections[2].section_label == "Section 3 Patents Law"
    assert "patentable" in sections[2].text.lower()


def test_parse_sections_commercial_torts_uses_article_label() -> None:
    source = StatuteSource(
        statute="commercial_torts",
        short_name="Commercial Torts Law",
        title="Commercial Torts Law, 5759-1999",
        source_url="https://example.com/ct.pdf",
        section_unit="Article",
        source_version="test",
    )
    text = "6. Trade secret\nA person shall not misappropriate.\n"
    sections = parse_sections(source, text)
    assert sections[0].section_label == "Article 6 Commercial Torts Law"


def test_parse_sections_ignores_body_only_lines() -> None:
    source = SOURCES[0]
    text = "(a) inline subsection text with no heading\n"
    assert parse_sections(source, text) == []


# ──────────────────────────────────────────────────────────────────────
# write_corpus round-trip
# ──────────────────────────────────────────────────────────────────────


def test_write_corpus_round_trip(tmp_path: Path) -> None:
    source = SOURCES[0]
    text = "3. Patentable invention\nAn invention is patentable.\n"
    sections = parse_sections(source, text)
    output = tmp_path / "ilpo.db"
    count = write_corpus(
        sections,
        output,
        snapshot_date="2026-05-16",
        source_version="WIPO Lex authoritative EN",
    )
    assert count == 1
    conn = sqlite3.connect(output)
    try:
        row = conn.execute("SELECT section_label, text FROM sections").fetchone()
        assert row[0] == "Section 3 Patents Law"
        assert "patentable" in row[1].lower()
        meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
        assert meta["schema_version"] == str(SCHEMA_VERSION)
        assert meta["snapshot_date"] == "2026-05-16"
    finally:
        conn.close()


def test_write_corpus_overwrites_existing(tmp_path: Path) -> None:
    output = tmp_path / "ilpo.db"
    output.write_text("not a db")
    sections = parse_sections(
        SOURCES[0],
        "1. Definitions\nDefs.\n",
    )
    count = write_corpus(sections, output, snapshot_date="2026-05-16", source_version="v")
    assert count == 1
    assert output.exists() and output.stat().st_size > 0


# ──────────────────────────────────────────────────────────────────────
# Fetcher HTTP shape (mocked)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetcher_gets_pdf_bytes() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=b"%PDF-1.4 ...")

    async with IlpoStatutesFetcher() as fetcher:
        # Swap the internal client to the mock so we don't actually call WIPO.
        await fetcher._client.aclose()
        fetcher._client = _mock_http(handler)
        data = await fetcher.fetch(SOURCES[0])

    assert data.startswith(b"%PDF")
    assert captured[0].method == "GET"


# ──────────────────────────────────────────────────────────────────────
# argparse / main
# ──────────────────────────────────────────────────────────────────────


def test_main_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "ilpo.db"

    async def fake_build(out: Path, **_kwargs: object) -> int:
        # Write a placeholder file so the rc-0 path looks real.
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"")
        return 42

    monkeypatch.setattr(
        "patent_client_agents.ilpo_statutes.corpus.build.build_corpus",
        AsyncMock(side_effect=fake_build),
    )
    rc = main(["--output", str(output), "--verbose"])
    assert rc == 0
    assert output.exists()


def test_build_corpus_fetch_failure_skips(tmp_path: Path) -> None:
    """A fetch failure for one statute should not abort the whole build."""

    async def bad_fetch(*_args: object, **_kwargs: object) -> bytes:
        raise httpx.HTTPError("simulated")

    output = tmp_path / "ilpo.db"
    with patch("patent_client_agents.ilpo_statutes.corpus.build.IlpoStatutesFetcher") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.fetch = AsyncMock(side_effect=httpx.HTTPError("simulated"))
        # `build_corpus` swallows fetch errors per-statute and still writes
        # the (possibly empty) corpus.
        count = asyncio.run(build_corpus(output, sources=SOURCES[:1]))
    assert count == 0
    assert output.exists()
    del bad_fetch  # silence unused-symbol lint


def test_build_corpus_extract_failure_skips(tmp_path: Path) -> None:
    """A PDF-extract failure for one statute should not abort the build."""

    output = tmp_path / "ilpo.db"
    with patch("patent_client_agents.ilpo_statutes.corpus.build.IlpoStatutesFetcher") as mock_cls:
        instance = mock_cls.return_value.__aenter__.return_value
        instance.fetch = AsyncMock(return_value=b"not-a-pdf")
        with patch(
            "patent_client_agents.ilpo_statutes.corpus.build.extract_pdf_text",
            side_effect=ValueError("bad pdf"),
        ):
            count = asyncio.run(build_corpus(output, sources=SOURCES[:1]))
    assert count == 0
    assert output.exists()
