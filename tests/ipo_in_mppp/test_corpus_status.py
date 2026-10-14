"""IPO India MPPP ``get_corpus_status()`` against the bundled-seed build.

The shared contract lives in ``tests/shared/test_corpus_status.py``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from patent_client_agents.ipo_in_mppp import get_corpus_status


def test_build_stamps_v3_source_version(ipo_in_mppp_corpus_env: Path) -> None:
    """The build stamps 'v3.0 (2019)' by default, which wins over the snapshot label."""
    status = get_corpus_status()
    assert status["corpus_version"] == "v3.0 (2019)"
    assert isinstance(status["corpus_synced_at"], datetime)
