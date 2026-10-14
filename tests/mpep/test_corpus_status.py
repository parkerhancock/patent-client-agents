"""MPEP ``get_corpus_status()`` against a corpus written by the real build.

MPEP reads the build's precise ``synced_at`` timestamp before
``snapshot_date``. The shared contract lives in
``tests/shared/test_corpus_status.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from patent_client_agents.mpep import get_corpus_status


class TestGetCorpusStatusFromBundledCorpus:
    @staticmethod
    def _corpus_with_source_version(
        monkeypatch: pytest.MonkeyPatch, src: Path, dest: Path, source_version: str
    ) -> None:
        import shutil
        import sqlite3

        shutil.copyfile(src, dest)
        conn = sqlite3.connect(dest)
        try:
            conn.execute(
                "UPDATE meta SET value = ? WHERE key = 'source_version'", (source_version,)
            )
            conn.commit()
        finally:
            conn.close()
        monkeypatch.setenv("MPEP_CORPUS_PATH", str(dest))

    def test_version_string_is_source_version_from_meta(
        self, monkeypatch: pytest.MonkeyPatch, mpep_corpus_path: Path, tmp_path: Path
    ) -> None:
        self._corpus_with_source_version(
            monkeypatch, mpep_corpus_path, tmp_path / "mpep.db", "R-01.2024"
        )
        assert get_corpus_status()["corpus_version"] == "R-01.2024"

    def test_current_source_version_reports_unknown(
        self, monkeypatch: pytest.MonkeyPatch, mpep_corpus_path: Path, tmp_path: Path
    ) -> None:
        """Absent release evidence remains unknown, rather than claiming current."""
        self._corpus_with_source_version(
            monkeypatch, mpep_corpus_path, tmp_path / "mpep.db", "current"
        )
        assert get_corpus_status()["corpus_version"] == "unknown"

    def test_synced_at_is_utc_datetime_from_snapshot_date(self, mpep_corpus_env: Path) -> None:
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

    def test_synced_at_preserves_build_timestamp(self, mpep_corpus_env: Path) -> None:
        from patent_client_agents.mpep.corpus.db import CorpusDB

        with CorpusDB.open() as db:
            expected = datetime.fromisoformat(db.meta()["synced_at"])
        assert get_corpus_status()["corpus_synced_at"] == expected
