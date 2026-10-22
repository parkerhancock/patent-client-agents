"""Offline smoke test for the EPO Case Law corpus build."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx2
import pytest

from patent_client_agents.epo_case_law.corpus.build import build_corpus
from tests.corpus_build_support import read_corpus, serve, today

_BASE = "/en/legal/case-law/2022"
_PAGES = {
    f"{_BASE}/index.html": (
        f'<a href="{_BASE}/clr_i_a_1.html">I.A.1</a><a href="{_BASE}/clr_ii_b.html">II.B</a>'
    ),
    f"{_BASE}/clr_i_a_1.html": "<main><h1>1. Patentable inventions</h1><p>Body.</p></main>",
    f"{_BASE}/clr_ii_b.html": "<main><h1>B. Claims</h1><p>Claims body.</p></main>",
}


def _pages(request: httpx2.Request) -> str | None:
    return _PAGES.get(request.url.path)


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "caselaw.db"

    count = asyncio.run(build_corpus(out, pause=0))

    assert count == 2
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title")
    assert [tuple(row) for row in rows] == [
        ("clr_i_a_1", "I.A.1", "Part I", "1. Patentable inventions"),
        ("clr_ii_b", "II.B", "Part II", "B. Claims"),
    ]
    assert meta["caselaw_year"] == "2022"
    assert meta["snapshot_date"] == today()
