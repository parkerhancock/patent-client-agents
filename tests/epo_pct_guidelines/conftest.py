"""Shared fixtures for PCT-EPO Guidelines tests.

Builds a tiny on-disk corpus from hand-authored rows so the read path
is exercised end-to-end without a full EPO website scrape.

The ``pct_corpus_path`` session fixture provides the on-disk path; the
``pct_corpus_env`` fixture additionally monkeypatches
``PCT_GUIDELINES_CORPUS_PATH`` so a single fixture covers both setup
steps for the row-18 envelope/corpus_status tests.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.epo_pct_guidelines.corpus.schema import DDL, SCHEMA_VERSION


@pytest.fixture(scope="session")
def pct_corpus_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("pct-corpus") / "pct.db"
    conn = sqlite3.connect(out)
    try:
        conn.executescript(DDL)
        for key, val in (
            ("schema_version", str(SCHEMA_VERSION)),
            ("source", "fixture"),
            ("snapshot_date", datetime.now(UTC).strftime("%Y-%m-%d")),
            ("guidelines_year", "2024"),
        ):
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, val))
        conn.executemany(
            "INSERT INTO sections (href, section_number, title, breadcrumb, chapter, html, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "g_ii_3_1",
                    "G-II, 3.1",
                    "3.1 Subject matter excluded from international search",
                    "Part G > Chapter II > 3.1",
                    "G",
                    "<div><h1>Excluded subject matter</h1><p>Discoveries.</p></div>",
                    "3.1 Subject matter excluded from international search. Discoveries.",
                ),
                (
                    "g_iii_1",
                    "G-III, 1",
                    "1 Unity of invention in the international phase",
                    "Part G > Chapter III > 1",
                    "G",
                    "<div><h1>Unity</h1><p>Unity of invention discussion.</p></div>",
                    "1 Unity of invention in the international phase.",
                ),
                (
                    "b_iv_1_1",
                    "B-IV, 1.1",
                    "1.1 Amendments under Article 19",
                    "Part B > Chapter IV > 1.1",
                    "B",
                    "<div><h1>Amendments</h1><p>Article 19 amendments.</p></div>",
                    "1.1 Amendments under Article 19.",
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    return out


@pytest.fixture
def pct_corpus_env(monkeypatch: pytest.MonkeyPatch, pct_corpus_path: Path) -> Path:
    """Point ``PCT_GUIDELINES_CORPUS_PATH`` at the fixture corpus for one test."""
    monkeypatch.setenv("PCT_GUIDELINES_CORPUS_PATH", str(pct_corpus_path))
    return pct_corpus_path
