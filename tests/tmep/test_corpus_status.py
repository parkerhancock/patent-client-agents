"""Tests for the module-level ``get_corpus_status()`` callable.

Sister to ``tests/mpep/test_corpus_status.py`` — same template applied
to the TMEP corpus. Asserts the shape, that values come from the SQLite
``meta`` table when the corpus is present, and that a missing /
unreadable corpus degrades to the documented
``corpus_version='unknown'`` / ``corpus_synced_at=None`` fallback rather
than raising.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.tmep import get_corpus_status


class TestGetCorpusStatusShape:
    def test_returns_dict_with_two_keys(self, tmep_corpus_env: Path) -> None:
        status = get_corpus_status()
        assert isinstance(status, dict)
        # The TypedDict surface is exactly these two keys, no more.
        assert set(status.keys()) == {"corpus_synced_at", "corpus_version"}


class TestGetCorpusStatusFromBundledCorpus:
    def test_version_string_is_source_version_from_meta(self, tmep_corpus_env: Path) -> None:
        """``write_corpus`` stamps ``source_version='current'`` (see
        ``corpus/build.py``). The callable surfaces it verbatim.
        """
        status = get_corpus_status()
        assert status["corpus_version"] == "current"

    def test_synced_at_is_utc_datetime_from_snapshot_date(self, tmep_corpus_env: Path) -> None:
        """``meta.snapshot_date`` is ISO ``YYYY-MM-DD``; we lift it to a
        UTC ``datetime`` so the Provenance helper can pass it through
        without further parsing.
        """
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        # The fixture corpus was built at session start, so the date
        # is today's date — just assert the year is reasonable.
        assert synced.year >= 2024
        # Snapshot_date carries no time component; lift normalizes to
        # UTC midnight so downstream consumers get a stable value.
        assert synced.hour == 0
        assert synced.minute == 0
        assert synced.second == 0


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
        monkeypatch.setenv("TMEP_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_returns_unknown_when_snapshot_date_malformed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """If the meta table carries a non-ISO ``snapshot_date``,
        ``corpus_synced_at`` falls back to ``None`` while
        ``corpus_version`` still surfaces from ``source_version``.
        Tests the parser is defensive — the corpus may be hand-edited or
        carry an older snapshot format.
        """
        import sqlite3

        db_path = tmp_path / "bad_meta.db"
        from patent_client_agents.tmep.corpus.schema import DDL

        conn = sqlite3.connect(db_path)
        try:
            conn.executescript(DDL)
            conn.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    ("schema_version", "1"),
                    ("snapshot_date", "not-a-date"),
                    ("source_version", "R-07.2022"),
                    ("section_count", "0"),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setenv("TMEP_CORPUS_PATH", str(db_path))
        status = get_corpus_status()
        assert status["corpus_version"] == "R-07.2022"
        assert status["corpus_synced_at"] is None
