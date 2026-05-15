"""Tests for the PCT-EPO Guidelines ``get_corpus_status()`` callable.

Row-18 sibling of the row-17 MPEP template. Asserts the shape (typed
dict with the two keys), that values come from the SQLite ``meta``
table when the corpus is present, and that a missing / unreadable
corpus degrades to the documented ``corpus_version='unknown'`` /
``corpus_synced_at=None`` fallback rather than raising.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.epo_pct_guidelines import get_corpus_status


class TestGetCorpusStatusShape:
    def test_returns_dict_with_two_keys(self, pct_corpus_env: Path) -> None:
        status = get_corpus_status()
        assert isinstance(status, dict)
        # The TypedDict surface is exactly these two keys, no more.
        assert set(status.keys()) == {"corpus_synced_at", "corpus_version"}


class TestGetCorpusStatusFromBundledCorpus:
    def test_version_falls_back_to_guidelines_year(self, pct_corpus_env: Path) -> None:
        """The PCT scraper stamps ``guidelines_year`` (no ``source_version``).
        The callable surfaces the year as the corpus_version so the
        Provenance helper can quote it directly when warning about
        staleness (§4 + §5.13).
        """
        status = get_corpus_status()
        assert status["corpus_version"] == "2024"

    def test_synced_at_is_utc_datetime_normalized_to_midnight(self, pct_corpus_env: Path) -> None:
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert synced.hour == 0
        assert synced.minute == 0
        assert synced.second == 0


class TestGetCorpusStatusMissingCorpus:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no corpus file exists at the resolved path, the callable
        degrades gracefully — does NOT raise.
        """
        monkeypatch.setenv("PCT_GUIDELINES_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_source_version_preferred_over_year(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """If a future build stamps an explicit ``source_version``, it
        wins over the ``guidelines_year`` fallback.
        """
        from patent_client_agents.epo_pct_guidelines.corpus.schema import DDL

        db_path = tmp_path / "with_version.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "2026-01-15"),
                    ("source_version", "2024-rev-1"),
                    ("guidelines_year", "2024"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setenv("PCT_GUIDELINES_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "2024-rev-1"
        assert status["corpus_synced_at"] == datetime(2026, 1, 15, tzinfo=UTC)
