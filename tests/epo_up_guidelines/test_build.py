"""Offline smoke test for the EPO Unitary Patent Guidelines corpus build."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from patent_client_agents.epo_up_guidelines.corpus.build import build_corpus
from tests.corpus_build_support import read_corpus, serve, today

_BASE = "/en/legal/guidelines-up/2026"


def _page(title: str, body: str) -> str:
    return (
        '<div class="content-wrapper"><div class="col-12 col-lg-8">'
        f"<h1>{title}</h1></div><p>{body}</p><script>x()</script></div>"
    )


_PAGES = {
    "/en/legal/sitemap/sitemap-en-1.xml": (
        f"<urlset><url><loc>https://www.epo.org{_BASE}/section_1_2</loc></url>"
        f"<url><loc>https://www.epo.org{_BASE}/section_2</loc></url>"
        "<url><loc>https://www.epo.org/en/legal/guidelines-epc/2024/a.html</loc></url></urlset>"
    ),
    f"{_BASE}/section_1_2": _page("1.2 Request for unitary effect", "Filed within one month."),
    f"{_BASE}/section_2": _page("2. Compensation scheme", "Translations."),
}


def _pages(request: httpx.Request) -> str | None:
    return _PAGES.get(request.url.path)


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "up_guidelines.db"

    count = asyncio.run(build_corpus(out, pause=0))

    assert count == 2
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title, text")
    assert [tuple(row)[:4] for row in rows] == [
        ("section_1_2", "1.2", "1", "1.2 Request for unitary effect"),
        ("section_2", "2", "2", "2. Compensation scheme"),
    ]
    assert "Filed within one month." in rows[0]["text"]
    assert "x()" not in rows[0]["text"]
    assert meta["up_guidelines_year"] == "2026"
    assert meta["snapshot_date"] == today()
