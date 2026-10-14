"""Read side of the corpus: ``CASELAW_CORPUS_PATH``, else ``~/.cache/patent_client_agents/caselaw.db``.

A missing file raises :class:`CorpusUnavailable` with build instructions.
Lifecycle and the outline queries live in :mod:`mcp_data_core.corpus_db`.
"""

from __future__ import annotations

from pathlib import Path

from mcp_data_core.corpus_db import CorpusUnavailable, OutlineCorpusDB
from mcp_data_core.corpus_db import OutlineCorpusHit as CorpusHit
from mcp_data_core.corpus_db import OutlineCorpusSection as CorpusSection


class CorpusDB(OutlineCorpusDB):
    """EPO Case Law corpus client — outline row schema."""

    LABEL = "CASELAW"
    ENV_VAR = "CASELAW_CORPUS_PATH"
    DEFAULT_FILENAME = "caselaw.db"
    BUILD_COMMAND = "patent-client-agents-build-caselaw-corpus"


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return CorpusDB.default_path()


__all__ = [
    "CorpusDB",
    "CorpusHit",
    "CorpusSection",
    "CorpusUnavailable",
    "default_corpus_path",
]
