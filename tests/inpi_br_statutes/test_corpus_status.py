"""Tests for the module-level ``get_corpus_status()`` callable.

Asserts the shape (typed dict with the two keys), that values come from
the SQLite ``meta`` table when the corpus is present, and that a
missing / unreadable corpus degrades to the documented
``corpus_version='unknown'`` / ``corpus_synced_at=None`` fallback rather
than raising.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.inpi_br_statutes import get_corpus_status


@pytest.fixture
def lpi_corpus_env(monkeypatch: pytest.MonkeyPatch, lpi_corpus_path: Path) -> Path:
    """Point ``INPI_BR_STATUTES_CORPUS_PATH`` at the fixture corpus."""
    monkeypatch.setenv("INPI_BR_STATUTES_CORPUS_PATH", str(lpi_corpus_path))
    return lpi_corpus_path


class TestGetCorpusStatusShape:
    def test_returns_dict_with_two_keys(self, lpi_corpus_env: Path) -> None:
        status = get_corpus_status()
        assert isinstance(status, dict)
        assert set(status.keys()) == {"corpus_synced_at", "corpus_version"}


class TestGetCorpusStatusFromBundledCorpus:
    def test_version_string_is_lpi_year_from_meta(self, lpi_corpus_env: Path) -> None:
        """The fixture corpus stamps ``lpi_year='1996'``."""
        status = get_corpus_status()
        assert status["corpus_version"] == "1996"

    def test_synced_at_is_utc_datetime_from_snapshot_date(self, lpi_corpus_env: Path) -> None:
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert synced.year >= 2024


class TestGetCorpusStatusMissingCorpus:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("INPI_BR_STATUTES_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_returns_none_synced_when_snapshot_date_malformed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import sqlite3

        db_path = tmp_path / "bad_meta.db"
        from patent_client_agents.inpi_br_statutes.corpus.schema import DDL

        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "not-a-date"),
                    ("lpi_year", "1996"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setenv("INPI_BR_STATUTES_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "1996"
        assert status["corpus_synced_at"] is None
