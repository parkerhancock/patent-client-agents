"""Offline smoke test for the UPC statutes corpus build."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from patent_client_agents.upc_statutes import get_corpus_status
from patent_client_agents.upc_statutes.corpus import build as build_mod
from tests.corpus_build_support import read_corpus, serve, today

_SOURCES = build_mod.SOURCES[:2]
_BODIES = {
    _SOURCES[
        0
    ].path: "Article 1 Unified Patent Court. A Unified Patent Court is hereby established.",
    _SOURCES[1].path: "Article premier Juridiction unifiée du brevet.",
}


def _pages(request: httpx.Request) -> str | None:
    return _BODIES.get(request.url.path)


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, _pages)
    # The fixture serves the extracted text directly; PDF parsing has its own tests.
    monkeypatch.setattr(build_mod, "extract_pdf_text", lambda content: (3, content.decode()))
    out = tmp_path / "upc_statutes.db"

    count = asyncio.run(build_mod.build_corpus(out, sources=_SOURCES))

    assert count == 2
    rows, meta = read_corpus(
        out,
        table="instruments",
        columns="instrument, language, short_name, source_url, pdf_pages, text",
    )
    assert [tuple(row)[:3] for row in rows] == [("upca", "en", "UPCA"), ("upca", "fr", "UPCA")]
    assert rows[0]["source_url"] == f"{build_mod.DEFAULT_BASE_URL}{_SOURCES[0].path}"
    assert rows[0]["pdf_pages"] == 3
    assert rows[1]["text"] == _BODIES[_SOURCES[1].path]
    assert meta["instrument_count"] == "2"
    assert meta["snapshot_date"] == today()
    monkeypatch.setenv("UPC_STATUTES_CORPUS_PATH", str(out))
    assert get_corpus_status()["corpus_version"] == f"snapshot {today()}"
