"""Offline smoke test for the EPC corpus build."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from patent_client_agents.epc import get_corpus_status
from patent_client_agents.epc.corpus import build as build_mod
from tests.corpus_build_support import read_corpus, serve, today

_PAGES = {
    "/en/legal/epc/2020/convention.html": (
        '<a href="/en/legal/epc/2020/a52.html">Art. 52</a>'
        '<a href="/en/legal/epc/2020/a54.html">Art. 54</a>'
    ),
    "/en/legal/epc/2020/regulations.html": '<a href="/en/legal/epc/2020/r43.html">Rule 43</a>',
    "/en/legal/epc/2020/a52.html": (
        "<main><nav>skip</nav><h1>Article 52 Patentable inventions</h1>"
        "<p>European patents shall be granted for any inventions.</p></main>"
    ),
    "/en/legal/epc/2020/a54.html": "<main><h1>Article 54 Novelty</h1><p>New.</p></main>",
    "/en/legal/epc/2020/r43.html": "<main><h1>Rule 43 Form of claims</h1><p>Claims.</p></main>",
}


def _pages(request: httpx.Request) -> str | None:
    return _PAGES.get(request.url.path)


def test_build_corpus_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "epc.db"

    count = asyncio.run(build_mod.build_corpus(out, pause=0))

    assert count == 3
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title, text")
    assert [tuple(row)[:4] for row in rows] == [
        ("a52", "Article 52", "Article", "Article 52 Patentable inventions"),
        ("a54", "Article 54", "Article", "Article 54 Novelty"),
        ("r43", "Rule 43", "Rule", "Rule 43 Form of claims"),
    ]
    assert "skip" not in rows[0]["text"]
    assert meta["epc_year"] == "2020"
    assert meta["snapshot_date"] == today()
    assert meta["source"] == "https://www.epo.org/en/legal/epc/2020"
    monkeypatch.setenv("EPC_CORPUS_PATH", str(out))
    assert get_corpus_status()["corpus_version"] == "2020"


def test_failed_build_keeps_previous_corpus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "epc.db"
    out.write_bytes(b"previous corpus")

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("finalize failed")

    monkeypatch.setattr(build_mod, "finalize_outline_corpus", boom)
    with pytest.raises(RuntimeError, match="finalize failed"):
        asyncio.run(build_mod.build_corpus(out, pause=0))
    assert out.read_bytes() == b"previous corpus"
    assert list(tmp_path.iterdir()) == [out]


def test_main_prints_row_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    serve(monkeypatch, _pages)
    out = tmp_path / "epc.db"
    assert build_mod.main(["--output", str(out), "--pause", "0"]) == 0
    assert capsys.readouterr().out == f"Wrote 3 sections to {out}\n"
