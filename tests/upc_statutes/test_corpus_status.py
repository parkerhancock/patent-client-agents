"""Tests for the module-level ``get_corpus_status()`` callable.

Mirrors ``tests/mpep/test_corpus_status.py`` and
``tests/tmep/test_corpus_status.py``. The UPC statutes corpus only
records ``snapshot_date`` in its ``meta`` table (consolidated PDFs do
not carry a discrete vendor version), so ``corpus_version`` is derived
from the snapshot date — ``"snapshot YYYY-MM-DD"``. Missing /
unreadable corpora fall back to ``corpus_version="unknown"`` /
``corpus_synced_at=None``.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.upc_statutes import get_corpus_status
from patent_client_agents.upc_statutes.corpus.schema import DDL, SCHEMA_VERSION


def _seed_corpus(path: Path, *, snapshot_date: str | None) -> None:
    """Seed a minimal UPC statutes corpus at ``path`` with the given snapshot date."""
    conn = sqlite3.connect(path)
    try:
        conn.executescript(DDL)
        meta_rows: list[tuple[str, str]] = [
            ("schema_version", str(SCHEMA_VERSION)),
            ("instrument_count", "0"),
        ]
        if snapshot_date is not None:
            meta_rows.append(("snapshot_date", snapshot_date))
        conn.executemany(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            meta_rows,
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_corpus_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point ``UPC_STATUTES_CORPUS_PATH`` at a freshly seeded corpus."""
    db = tmp_path / "upc_statutes.db"
    _seed_corpus(db, snapshot_date="2026-05-13")
    monkeypatch.setenv("UPC_STATUTES_CORPUS_PATH", str(db))
    return db


class TestGetCorpusStatusShape:
    def test_returns_dict_with_two_keys(self, seeded_corpus_env: Path) -> None:
        status = get_corpus_status()
        assert isinstance(status, dict)
        # The TypedDict surface is exactly these two keys, no more.
        assert set(status.keys()) == {"corpus_synced_at", "corpus_version"}


class TestGetCorpusStatusFromBundledCorpus:
    def test_version_derived_from_snapshot_date(self, seeded_corpus_env: Path) -> None:
        """The UPC statutes corpus has no upstream ``source_version`` —
        the consolidated PDFs aren't tagged with a discrete version
        label. The callable derives ``corpus_version`` from
        ``meta.snapshot_date`` so agents have a stable, citation-ready
        string to quote.
        """
        status = get_corpus_status()
        assert status["corpus_version"] == "snapshot 2026-05-13"

    def test_synced_at_is_utc_midnight_datetime(self, seeded_corpus_env: Path) -> None:
        """``meta.snapshot_date`` is ISO ``YYYY-MM-DD``; we lift it to a
        UTC midnight ``datetime`` so the Provenance helper can pass it
        through without further parsing.
        """
        status = get_corpus_status()
        synced = status["corpus_synced_at"]
        assert isinstance(synced, datetime)
        assert synced.tzinfo == UTC
        assert (synced.year, synced.month, synced.day) == (2026, 5, 13)
        assert synced.hour == 0
        assert synced.minute == 0
        assert synced.second == 0


class TestGetCorpusStatusMissingOrMalformed:
    def test_returns_unknown_when_corpus_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When no corpus file exists at the resolved path, the callable
        degrades gracefully — never raises. The validator and Provenance
        helper call this on every request.
        """
        monkeypatch.setenv("UPC_STATUTES_CORPUS_PATH", str(tmp_path / "missing.db"))
        status = get_corpus_status()
        assert status["corpus_version"] == "unknown"
        assert status["corpus_synced_at"] is None

    def test_returns_unknown_when_snapshot_date_malformed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """If ``meta.snapshot_date`` is not ISO ``YYYY-MM-DD``,
        ``corpus_synced_at`` falls back to ``None`` while
        ``corpus_version`` still surfaces the raw snapshot string —
        otherwise an agent would silently lose freshness signal.
        """
        db = tmp_path / "bad_meta.db"
        _seed_corpus(db, snapshot_date="not-a-date")
        monkeypatch.setenv("UPC_STATUTES_CORPUS_PATH", str(db))
        status = get_corpus_status()
        # Version still passes through the raw snapshot string — the
        # parser is defensive about the date, not the label.
        assert status["corpus_version"] == "snapshot not-a-date"
        assert status["corpus_synced_at"] is None
