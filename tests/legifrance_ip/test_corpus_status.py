"""Tests for the Légifrance IP ``get_corpus_status()`` callable."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.legifrance_ip import get_corpus_status
from patent_client_agents.legifrance_ip.corpus.build import CORPUS_VERSION


class TestFromBundledCorpus:
    def test_version_matches_corpus_version(self, legifrance_ip_corpus_env: Path) -> None:
        status = get_corpus_status()
        # build.py stamps `source_version=CORPUS_VERSION` so get_corpus_status
        # surfaces that value verbatim — no snapshot fallback.
        assert status["corpus_version"] == CORPUS_VERSION
        assert status["corpus_synced_at"] is not None

    def test_synced_at_utc_normalized_to_midnight(self, legifrance_ip_corpus_env: Path) -> None:
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert synced.hour == 0


class TestMissing:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_explicit_source_version_wins(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.legifrance_ip.corpus.schema import DDL

        db_path = tmp_path / "with_version.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "2026-03-10"),
                    ("source_version", "CPI-as-of-2024-08-01"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "CPI-as-of-2024-08-01"
        assert status["corpus_synced_at"] == datetime(2026, 3, 10, tzinfo=UTC)

    def test_invalid_snapshot_date_does_not_crash(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.legifrance_ip.corpus.schema import DDL

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
        monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_synced_at"] is None

    def test_no_source_version_returns_unknown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from patent_client_agents.legifrance_ip.corpus.schema import DDL

        db_path = tmp_path / "no_version.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "2026-03-10"),
                ],
            )
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv("LEGIFRANCE_IP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
