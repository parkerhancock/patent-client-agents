"""Offline smoke test for the TMEP corpus build."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from patent_client_agents.tmep import get_corpus_status
from patent_client_agents.tmep.corpus.build import DEFAULT_BASE_URL, build_corpus
from tests.corpus_build_support import read_corpus, serve, today

_PAGES = {
    "TMEP-1200d1e1.html": (
        "<h2>Chapter 1200 Substantive Examination</h2>"
        '<div id="TMEP-1200d1e1"><h1>1207 Refusal on Basis of Likelihood of Confusion</h1>'
        '<p>Examiners refuse confusingly similar marks.</p><a href="TMEP-1200d1e2.html">next</a>'
        "</div>"
    ),
    "TMEP-1200d1e2.html": (
        '<div id="TMEP-1200d1e2"><h1>1207.01 Likelihood of Confusion [R-05.2024]</h1>'
        "<p>DuPont factors.</p></div>"
    ),
}


def _pages(request: httpx.Request) -> str | None:
    if request.url.path != "/RDMS/TMEP/content":
        return None
    return _PAGES.get(request.url.params["href"])


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    requested = serve(monkeypatch, _pages)
    out = tmp_path / "tmep.db"

    count = asyncio.run(
        build_corpus(
            out, seed_hrefs=["TMEP-1200d1e1.html"], max_pages=None, base_url=DEFAULT_BASE_URL
        )
    )

    assert count == 2
    assert len(requested) == 2
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title, text")
    assert [tuple(row)[:4] for row in rows] == [
        (
            "TMEP-1200d1e1.html",
            "1207",
            "1200",
            "Refusal on Basis of Likelihood of Confusion",
        ),
        ("TMEP-1200d1e2.html", "1207.01", "1200", "Likelihood of Confusion"),
    ]
    assert meta["source_version"] == "current"
    assert meta["section_count"] == "2"
    assert meta["snapshot_date"] == today()
    monkeypatch.setenv("TMEP_CORPUS_PATH", str(out))
    assert get_corpus_status()["corpus_version"] == "unknown"
