"""TMEP ``get_corpus_status()`` against a corpus written by the real build.

The shared contract lives in ``tests/shared/test_corpus_status.py``.
"""

from __future__ import annotations

from pathlib import Path

from patent_client_agents.tmep import get_corpus_status


def test_build_current_label_reports_unknown(tmep_corpus_env: Path) -> None:
    """``write_corpus`` stamps ``source_version='current'``, the eTMEP query
    parameter rather than release evidence, so the status is ``'unknown'``.
    """
    status = get_corpus_status()
    assert status["corpus_version"] == "unknown"
    assert status["corpus_synced_at"] is not None
