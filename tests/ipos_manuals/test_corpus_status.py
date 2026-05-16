"""Tests for ``ipos_manuals.get_corpus_status()``."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.ipos_manuals import get_corpus_status
from patent_client_agents.ipos_manuals.corpus.schema import DDL, SCHEMA_VERSION


def _seed_corpus(
    path: Path,
    *,
    snapshot_date: str | None,
    source_version: str | None = None,
) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)
        meta_rows: list[tuple[str, str]] = [
            ("schema_version", str(SCHEMA_VERSION)),
            ("section_count", "0"),
            ("manual_count", "0"),
        ]
        if snapshot_date is not None:
            meta_rows.append(("snapshot_date", snapshot_date))
        if source_version is not None:
            meta_rows.append(("source_version", source_version))
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            meta_rows,
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_corpus_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db = tmp_path / "ipos_manuals.db"
    _seed_corpus(db, snapshot_date="2026-05-16")
    monkeypatch.setenv("IPOS_MANUALS_CORPUS_PATH", str(db))
    return db


class TestGetCorpusStatusShape:
    def test_returns_dict_with_two_keys(self, seeded_corpus_env: Path) -> None:
        status = get_corpus_status()
        assert set(status.keys()) == {"corpus_synced_at", "corpus_version"}


class TestGetCorpusStatusFromBundledCorpus:
    def test_version_derives_from_snapshot_when_no_source_version(
        self, seeded_corpus_env: Path
    ) -> None:
        status = get_corpus_status()
        assert status["corpus_version"] == "snapshot 2026-05-16"

    def test_version_uses_source_version_when_stamped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        db = tmp_path / "ipos_manuals.db"
        _seed_corpus(db, snapshot_date="2026-05-16", source_version="Jan 2026 PEG release")
        monkeypatch.setenv("IPOS_MANUALS_CORPUS_PATH", str(db))
        status = get_corpus_status()
        assert status["corpus_version"] == "Jan 2026 PEG release"

    def test_synced_at_is_utc_midnight_datetime(self, seeded_corpus_env: Path) -> None:
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert (synced.year, synced.month, synced.day) == (2026, 5, 16)


class TestGetCorpusStatusMissingOrMalformed:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("IPOS_MANUALS_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_falls_back_when_snapshot_date_malformed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        db = tmp_path / "bad_meta.db"
        _seed_corpus(db, snapshot_date="not-a-date")
        monkeypatch.setenv("IPOS_MANUALS_CORPUS_PATH", str(db))
        status = get_corpus_status()
        assert status["corpus_version"] == "snapshot not-a-date"
        assert status["corpus_synced_at"] is None
