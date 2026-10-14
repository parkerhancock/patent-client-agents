"""Légifrance IP ``get_corpus_status()`` against the bundled-seed build.

The shared contract lives in ``tests/shared/test_corpus_status.py``.
"""

from __future__ import annotations

from pathlib import Path

from patent_client_agents.legifrance_ip import get_corpus_status
from patent_client_agents.legifrance_ip.corpus.build import CORPUS_VERSION


def test_build_stamps_corpus_version(legifrance_ip_corpus_env: Path) -> None:
    status = get_corpus_status()
    assert status["corpus_version"] == CORPUS_VERSION
    assert status["corpus_synced_at"] is not None
