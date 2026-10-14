"""Read side of the corpus: ``MOPP_CORPUS_PATH``, else ``~/.cache/patent_client_agents/mopp.db``.

A missing file raises :class:`CorpusUnavailable` with build instructions.
Lifecycle and the outline queries live in :mod:`mcp_data_core.corpus_db`.
"""

from __future__ import annotations

from pathlib import Path

from mcp_data_core.corpus_db import CorpusUnavailable, OutlineCorpusDB
from mcp_data_core.corpus_db import OutlineCorpusHit as CorpusHit
from mcp_data_core.corpus_db import OutlineCorpusSection as CorpusSection


class CorpusDB(OutlineCorpusDB):
    """UKIPO MoPP corpus client — outline row schema served from the bundled SQLite."""

    LABEL = "MOPP"
    ENV_VAR = "MOPP_CORPUS_PATH"
    DEFAULT_FILENAME = "mopp.db"
    BUILD_COMMAND = "patent-client-agents-build-mopp-corpus"


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
