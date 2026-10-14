"""Read side of the corpus: ``GUIDELINES_CORPUS_PATH``, else ``~/.cache/patent_client_agents/guidelines.db``.

A missing file raises :class:`CorpusUnavailable` with build instructions.
Lifecycle and the outline queries live in :mod:`mcp_data_core.corpus_db`.
"""

from __future__ import annotations

from pathlib import Path

from mcp_data_core.corpus_db import CorpusUnavailable, OutlineCorpusDB
from mcp_data_core.corpus_db import OutlineCorpusHit as CorpusHit
from mcp_data_core.corpus_db import OutlineCorpusSection as CorpusSection


class CorpusDB(OutlineCorpusDB):
    """EPO Guidelines for Examination corpus client — outline row schema."""

    LABEL = "GUIDELINES"
    ENV_VAR = "GUIDELINES_CORPUS_PATH"
    DEFAULT_FILENAME = "guidelines.db"
    BUILD_COMMAND = "patent-client-agents-build-guidelines-corpus"


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
