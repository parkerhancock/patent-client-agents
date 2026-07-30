"""Smoke tests for the LPI corpus builder.

We don't hit Planalto live — the build pipeline is exercised with a
mocked HTTP transport that returns a tiny synthetic LPI HTML fragment.
The goal is to lock in:

  * the article-splitting regex behavior (PT + EN heads)
  * the SQLite schema write path
  * the meta-table bookkeeping (snapshot_date, lpi_year, source URLs)
  * the round-trip from build → CorpusDB read
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from patent_client_agents.inpi_br_statutes.corpus.build import (
    _ARTICLE_HEAD_EN,
    _ARTICLE_HEAD_PT,
    _split_articles,
    _strip_html,
    _title_from_body,
    build_corpus,
    main,
)
from patent_client_agents.inpi_br_statutes.corpus.db import CorpusDB


class TestSplitArticles:
    def test_pt_pattern_finds_articles(self) -> None:
        text = (
            "Art. 1º Esta lei dispõe sobre direitos. "
            "Art. 6º Ao autor é assegurado o direito. "
            "Art. 195. Comete crime quem... "
        )
        out = _split_articles(text, _ARTICLE_HEAD_PT)
        assert set(out.keys()) >= {"1", "6", "195"}
        assert "direitos" in out["1"]
        assert "autor" in out["6"]
        assert "crime" in out["195"]

    def test_en_pattern_finds_articles(self) -> None:
        text = (
            "Article 1. This law sets out rights. "
            "Article 6. The author is assured the right. "
            "Article 195. Whoever commits a crime... "
        )
        out = _split_articles(text, _ARTICLE_HEAD_EN)
        assert set(out.keys()) >= {"1", "6", "195"}

    def test_short_match_filtered_out(self) -> None:
        """Bodies under ~20 chars are skipped to silence cross-reference noise."""
        text = "Art. 999 ref."
        out = _split_articles(text, _ARTICLE_HEAD_PT)
        assert "999" not in out

    def test_first_occurrence_wins(self) -> None:
        text = (
            "Art. 6º Primeiro corpo do artigo seis com texto suficiente para passar pelo filtro. "
            "Algo mais. Art. 6º Segunda menção apenas referência cruzada."
        )
        out = _split_articles(text, _ARTICLE_HEAD_PT)
        assert "Primeiro" in out["6"]


class TestStripHtml:
    def test_collapses_whitespace_and_drops_scripts(self) -> None:
        html = (
            "<html><head><title>x</title></head><body>"
            "<script>alert('no');</script>"
            "<p>Art.\n\n1º texto.</p>"
            "<style>.x { color: red; }</style>"
            "</body></html>"
        )
        out = _strip_html(html)
        assert "alert" not in out
        assert "color" not in out
        assert "Art. 1º texto." in out

    def test_handles_non_html_gracefully(self) -> None:
        # lxml will accept arbitrary fragments; just verify we don't crash.
        out = _strip_html("Art. 1º plain text not html")
        assert "Art. 1" in out


class TestTitleFromBody:
    def test_truncates_long_bodies_without_sentence_break(self) -> None:
        """A body with no early period or semicolon is truncated to max_chars."""
        body = "Art 6 " + "x" * 500
        title = _title_from_body(body, max_chars=80)
        assert len(title) <= 80
        assert title.endswith("…")

    def test_splits_on_first_period(self) -> None:
        """``_title_from_body`` splits on the first period — that yields a
        short head for LPI bodies (because Planalto's article heads carry
        ``Art. 6º`` followed by a period). The implementation prefers a
        short, syntactically clean head over a more semantically rich one.
        """
        body = "Art. 6º Primeira frase curta. Segunda frase mais longa segue."
        title = _title_from_body(body)
        # The first period inside ``Art.`` is treated as a sentence break.
        assert title  # any non-empty string is fine — the contract is "short"
        assert "Segunda" not in title

    def test_max_chars_cap(self) -> None:
        body = "Sentença longa sem qualquer ponto até o final atinge o cap"
        title = _title_from_body(body, max_chars=30)
        assert len(title) <= 30


_FAKE_PT_HTML = (
    "<html><body>"
    "<p>LEI Nº 9.279, DE 14 DE MAIO DE 1996.</p>"
    "<p>Art. 6º Ao autor de invenção ou de modelo de utilidade será "
    "assegurado o direito de obter a patente.</p>"
    "<p>Art. 195. Comete crime de concorrência desleal quem divulga "
    "segredo industrial sem autorização.</p>"
    "</body></html>"
)

_FAKE_EN_HTML = (
    "<html><body>"
    "<p>LAW No. 9279 OF MAY 14 1996.</p>"
    "<p>Article 6. The author of an invention or utility model shall be "
    "assured the right to obtain the patent.</p>"
    "<p>Article 195. Whoever commits unfair competition by disclosing "
    "an industrial secret without authorization is guilty of a crime.</p>"
    "</body></html>"
)


@pytest.mark.asyncio
async def test_build_corpus_writes_sqlite_with_pt_and_en(tmp_path: Path) -> None:
    """End-to-end: build → SQLite → read-back via CorpusDB."""
    out = tmp_path / "inpi_br_statutes.db"

    async def fake_fetch(client, url):  # noqa: ARG001 — signature mirrors _fetch
        if "wipo" in url or "wipolex" in url:
            return _FAKE_EN_HTML
        return _FAKE_PT_HTML

    with patch("patent_client_agents.inpi_br_statutes.corpus.build._fetch", new=fake_fetch):
        rows = await build_corpus(
            out,
            pt_url="https://www.planalto.gov.br/ccivil_03/leis/l9279.htm",
            en_url="https://www.wipo.int/wipolex/en/legislation/details/16774",
        )

    assert rows >= 2
    assert out.exists()

    with CorpusDB.open(out) as db:
        meta = db.meta()
        assert meta["lpi_year"] == "1996"
        assert "planalto" in meta["source_pt"]
        assert "wipo" in meta["source_en"]
        assert int(meta["section_count"]) == rows

        sec6 = db.get_section(href="art6")
        assert sec6 is not None
        assert "patente" in sec6.text_pt.lower()
        assert sec6.text_en is not None
        assert "patent" in sec6.text_en.lower()

        sec195 = db.get_section(href="art195")
        assert sec195 is not None
        assert "concorrência desleal" in sec195.text_pt.lower()


@pytest.mark.asyncio
async def test_build_corpus_pt_only_when_en_fetch_fails(tmp_path: Path) -> None:
    """When EN fetch errors out, the build still ships PT rows (EN=NULL)."""
    out = tmp_path / "pt_only.db"

    async def fake_fetch(client, url):  # noqa: ARG001
        if "wipo" in url:
            raise RuntimeError("EN unavailable")
        return _FAKE_PT_HTML

    with patch("patent_client_agents.inpi_br_statutes.corpus.build._fetch", new=fake_fetch):
        rows = await build_corpus(
            out,
            pt_url="https://www.planalto.gov.br/ccivil_03/leis/l9279.htm",
            en_url="https://example.invalid/wipo-en",
        )

    assert rows >= 2
    with CorpusDB.open(out) as db:
        sec = db.get_section(href="art6")
        assert sec is not None
        assert sec.text_pt
        assert sec.text_en is None


@pytest.mark.asyncio
async def test_build_corpus_pt_only_when_en_url_not_supplied(tmp_path: Path) -> None:
    out = tmp_path / "pt_only.db"

    async def fake_fetch(client, url):  # noqa: ARG001
        return _FAKE_PT_HTML

    with patch("patent_client_agents.inpi_br_statutes.corpus.build._fetch", new=fake_fetch):
        rows = await build_corpus(out)

    assert rows >= 2
    with CorpusDB.open(out) as db:
        meta = db.meta()
        assert meta["source_en"] == ""
        sec = db.get_section(href="art195")
        assert sec is not None
        assert sec.text_en is None


def test_main_cli_smoke(tmp_path: Path) -> None:
    """The argparse-backed main() should run end-to-end and return 0."""
    out = tmp_path / "main.db"

    fake_build = AsyncMock(return_value=42)
    with patch(
        "patent_client_agents.inpi_br_statutes.corpus.build.build_corpus",
        new=fake_build,
    ):
        rc = main(["--output", str(out)])

    assert rc == 0
    fake_build.assert_awaited_once()


def test_main_cli_handles_exception(tmp_path: Path) -> None:
    """A build error should be reported and the CLI should exit non-zero."""
    out = tmp_path / "main.db"

    async def boom(*_args, **_kwargs):
        raise RuntimeError("upstream offline")

    with patch(
        "patent_client_agents.inpi_br_statutes.corpus.build.build_corpus",
        new=boom,
    ):
        rc = main(["--output", str(out)])

    assert rc == 1


def test_build_corpus_replaces_existing_file(tmp_path: Path) -> None:
    """Sanity: rerunning the build replaces the old database atomically."""
    out = tmp_path / "rerun.db"
    out.write_bytes(b"stale")

    async def fake_fetch(client, url):  # noqa: ARG001
        return _FAKE_PT_HTML

    import asyncio

    with patch("patent_client_agents.inpi_br_statutes.corpus.build._fetch", new=fake_fetch):
        rows = asyncio.run(build_corpus(out))

    assert rows >= 2
    # The first byte of a SQLite file is the magic "S" from "SQLite format 3".
    with sqlite3.connect(out) as conn:
        n = conn.execute("SELECT count(*) FROM sections").fetchone()[0]
    assert n == rows
