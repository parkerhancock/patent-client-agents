"""Tests for the IPO India statutes ``get_corpus_status()`` callable."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.ipo_in_statutes import get_corpus_status


class TestFromBundledCorpus:
    def test_version_falls_back_to_snapshot_label(self, ipo_in_statutes_corpus_env: Path) -> None:
        status = get_corpus_status()
        # No explicit source_version → snapshot-<date> fallback
        assert status["corpus_version"].startswith("snapshot-")
        assert status["corpus_synced_at"] is not None

    def test_synced_at_utc_normalized_to_midnight(self, ipo_in_statutes_corpus_env: Path) -> None:
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert synced.hour == 0


class TestMissing:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("IPO_IN_STATUTES_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_source_version_preferred_when_present(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.ipo_in_statutes.corpus.schema import DDL

        db_path = tmp_path / "with_version.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "2026-03-10"),
                    ("source_version", "Patents-Act-1970-as-of-2024-08-01"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setenv("IPO_IN_STATUTES_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "Patents-Act-1970-as-of-2024-08-01"
        assert status["corpus_synced_at"] == datetime(2026, 3, 10, tzinfo=UTC)

    def test_invalid_snapshot_date_does_not_crash(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.ipo_in_statutes.corpus.schema import DDL

        db_path = tmp_path / "bad_date.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "not-an-iso-date"),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv("IPO_IN_STATUTES_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_synced_at"] is None

    def test_no_snapshot_date_returns_unknown_version(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.ipo_in_statutes.corpus.schema import DDL

        db_path = tmp_path / "no_meta.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                ("schema_version", "1"),
            )
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv("IPO_IN_STATUTES_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None
