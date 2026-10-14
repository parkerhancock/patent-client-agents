"""Tests for IPO India MPPP ``get_corpus_status()``."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.ipo_in_mppp import get_corpus_status


class TestFromBundledCorpus:
    def test_source_version_is_v3(self, ipo_in_mppp_corpus_env: Path) -> None:
        """Build script stamps 'v3.0 (2019)' by default — it should win
        over the snapshot fallback.
        """
        status = get_corpus_status()
        assert status["corpus_version"] == "v3.0 (2019)"
        assert isinstance(status["corpus_synced_at"], datetime)


class TestMissing:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("IPO_IN_MPPP_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_invalid_date_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.ipo_in_mppp.corpus.schema import DDL

        db_path = tmp_path / "bad.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [("schema_version", "1"), ("snapshot_date", "weeble")],
            )
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv("IPO_IN_MPPP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_synced_at"] is None

    def test_snapshot_only_falls_back_to_snapshot_label(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.ipo_in_mppp.corpus.schema import DDL

        db_path = tmp_path / "snap.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [("schema_version", "1"), ("snapshot_date", "2026-02-15")],
            )
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv("IPO_IN_MPPP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "snapshot-2026-02-15"
        assert status["corpus_synced_at"] == datetime(2026, 2, 15, tzinfo=UTC)

    def test_no_meta_returns_unknown_version(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.ipo_in_mppp.corpus.schema import DDL

        db_path = tmp_path / "empty.db"
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
        monkeypatch.setenv("IPO_IN_MPPP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
