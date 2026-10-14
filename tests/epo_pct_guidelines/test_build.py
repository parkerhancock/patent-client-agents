"""Offline smoke test for the PCT-EPO Guidelines corpus build."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from patent_client_agents.epo_pct_guidelines.corpus.build import build_corpus
from tests.corpus_build_support import read_corpus, serve, today

_BASE = "/en/legal/guidelines-pct/2024"
_PAGES = {
    f"{_BASE}/index.html": '<a href="g_ii.html">G-II</a><a href="/en/legal/other.html">x</a>',
    f"{_BASE}/g_ii.html": (
        '<main><h1>Chapter II Inventions</h1><p>Body.</p><a href="g_ii_3_1.html">3.1</a></main>'
    ),
    f"{_BASE}/g_ii_3_1.html": (
        '<main><div class="breadcrumb">crumbs</div><h1>3.1 Discoveries</h1><p>Text.</p></main>'
    ),
}


def _pages(request: httpx.Request) -> str | None:
    return _PAGES.get(request.url.path)


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "corpus.db"

    count = asyncio.run(build_corpus(out, pause=0))

    assert count == 2
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title, text")
    assert [tuple(row)[:4] for row in rows] == [
        ("g_ii", "G-II", "G", "Chapter II Inventions"),
        ("g_ii_3_1", "G-II, 3.1", "G", "3.1 Discoveries"),
    ]
    assert "crumbs" not in rows[1]["text"]
    assert meta["guidelines_year"] == "2024"
    assert meta["snapshot_date"] == today()
