"""Offline smoke test for the MPEP corpus build."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from patent_client_agents.mpep import get_corpus_status
from patent_client_agents.mpep.corpus import build as build_mod
from tests.corpus_build_support import read_corpus, serve, today

_SELECT = (
    '<select id="edition-select"><option class="E9_R-07.2022">Old</option>'
    '<option class="E9_R-01.2024" selected="selected">Current</option></select>'
)
_PAGES = {
    "d0e100.html": (
        _SELECT + "<h2>Chapter 2100 Patentability</h2>"
        '<div id="d0e100"><h1>2106 Patent Subject Matter Eligibility [R-07.2022]</h1>'
        '<p>Eligibility guidance.</p><a href="#/E9_R-01.2024/d0e200.html">next</a></div>'
    ),
    "d0e200.html": (
        _SELECT + '<div id="d0e200"><h1>2106.04 Judicial Exceptions</h1><p>Exceptions.</p></div>'
    ),
}


def _pages(request: httpx.Request) -> str | None:
    if request.url.path != "/RDMS/MPEP/content":
        return None
    return _PAGES.get(request.url.params["href"])


def test_main_builds_corpus_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    requested = serve(monkeypatch, _pages)
    out = tmp_path / "mpep.db"

    assert build_mod.main(["--output", str(out), "--seed", "d0e100.html"]) == 0

    assert "version=E9_R-01.2024" in requested[1]  # the crawl pins the selected release
    assert capsys.readouterr().err.startswith(f"Wrote 2 sections to {out} in ")
    rows, meta = read_corpus(out, columns="href, section_number, chapter, title")
    assert [tuple(row) for row in rows] == [
        ("d0e100.html", "2106", "2100", "Patent Subject Matter Eligibility"),
        ("d0e200.html", "2106.04", "2100", "Judicial Exceptions"),
    ]
    assert meta["source_version"] == "E9_R-01.2024"
    assert meta["section_count"] == "2"
    assert meta["snapshot_date"] == today()
    assert meta["synced_at"].startswith(today())
    monkeypatch.setenv("MPEP_CORPUS_PATH", str(out))
    assert get_corpus_status()["corpus_version"] == "E9_R-01.2024"


def test_main_lets_build_errors_propagate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The MPEP CLI has always surfaced a traceback rather than exit code 1."""
    serve(monkeypatch, _pages)
    out = tmp_path / "mpep.db"
    out.write_bytes(b"previous corpus")
    monkeypatch.setattr(build_mod, "DDL", "NOT VALID SQL")

    with pytest.raises(Exception, match="syntax error"):
        build_mod.main(["--output", str(out), "--seed", "d0e100.html"])
    assert out.read_bytes() == b"previous corpus"
