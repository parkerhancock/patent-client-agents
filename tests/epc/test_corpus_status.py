"""Tests for the module-level ``get_corpus_status()`` callable.

This is the row-18 application of the row-17 MPEP template. Asserts the
shape (typed dict with the two keys), that values come from the SQLite
``meta`` table when the corpus is present, and that a missing /
unreadable corpus degrades to the documented
``corpus_version='unknown'`` / ``corpus_synced_at=None`` fallback rather
than raising.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.epc import get_corpus_status


@pytest.fixture
def epc_corpus_env(monkeypatch: pytest.MonkeyPatch, epc_corpus_path: Path) -> Path:
    """Point ``EPC_CORPUS_PATH`` at the fixture corpus for one test."""
    monkeypatch.setenv("EPC_CORPUS_PATH", str(epc_corpus_path))
    return epc_corpus_path


class TestGetCorpusStatusShape:
    def test_returns_dict_with_two_keys(self, epc_corpus_env: Path) -> None:
        status = get_corpus_status()
        assert isinstance(status, dict)
        # The TypedDict surface is exactly these two keys, no more.
        assert set(status.keys()) == {"corpus_synced_at", "corpus_version"}


class TestGetCorpusStatusFromBundledCorpus:
    def test_version_string_is_epc_year_from_meta(self, epc_corpus_env: Path) -> None:
        """The fixture corpus stamps ``epc_year='2020'``. The callable
        surfaces it verbatim as the corpus version.
        """
        status = get_corpus_status()
        assert status["corpus_version"] == "2020"

    def test_synced_at_is_utc_datetime_from_snapshot_date(self, epc_corpus_env: Path) -> None:
        """``meta.snapshot_date`` is ISO ``YYYY-MM-DD``; we lift it to a
        UTC ``datetime`` so the Provenance helper can pass it through
        without further parsing.
        """
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert synced.year >= 2024


class TestGetCorpusStatusMissingCorpus:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no corpus file exists at the resolved path, the callable
        degrades gracefully: ``corpus_version='unknown'`` /
        ``corpus_synced_at=None``. Importantly, it does NOT raise — the
        validator and Provenance helper call this on every request and
        must never crash on a missing bundle.
        """
        monkeypatch.setenv("EPC_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_returns_none_synced_when_snapshot_date_malformed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """If the meta table carries a non-ISO ``snapshot_date``,
        ``corpus_synced_at`` falls back to ``None`` while
        ``corpus_version`` still surfaces from ``epc_year``.
        """
        import sqlite3

        db_path = tmp_path / "bad_meta.db"
        from patent_client_agents.epc.corpus.schema import DDL

        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "not-a-date"),
                    ("epc_year", "2020"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setenv("EPC_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "2020"
        assert status["corpus_synced_at"] is None
