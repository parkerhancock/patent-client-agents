"""Read-side API for the EPO Boards of Appeal Case Law SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-caselaw-corpus`` and serves
queries against it. Locator precedence:

1. ``CASELAW_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/caselaw.db`` (local-dev convenience).

Misses raise :class:`CorpusUnavailable` with a message that tells the
caller how to materialize the database — never a silent fallback.

Lifecycle, FTS5 query plumbing, and the outline row schema live in
:mod:`law_tools_core.corpus_db`; this module only declares the Case Law
specifics.
"""

from __future__ import annotations

from pathlib import Path

from law_tools_core.corpus_db import (
    CorpusUnavailable,
    OutlineCorpusDB,
)
from law_tools_core.corpus_db import (
    OutlineCorpusHit as CorpusHit,
)
from law_tools_core.corpus_db import (
    OutlineCorpusSection as CorpusSection,
)


def default_corpus_path() -> Path:
    """Return the local-dev default location (~/.cache/...)."""
    return Path.home() / ".cache" / "patent_client_agents" / "caselaw.db"


class CorpusDB(OutlineCorpusDB):
    """EPO Case Law corpus client — outline row schema."""

    LABEL = "CASELAW"
    ENV_VAR = "CASELAW_CORPUS_PATH"
    DEFAULT_FILENAME = "caselaw.db"
    BUILD_COMMAND = "patent-client-agents-build-caselaw-corpus"


__all__ = [
    "CorpusDB",
    "CorpusHit",
    "CorpusSection",
    "CorpusUnavailable",
    "default_corpus_path",
]
