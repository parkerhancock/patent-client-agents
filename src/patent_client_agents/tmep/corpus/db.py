"""Read-side API for the TMEP SQLite corpus.

The runtime never builds the corpus — it opens an already-built ``.db``
file produced by ``patent-client-agents-build-tmep-corpus`` and serves
queries against it. Locator precedence:

1. ``TMEP_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/tmep.db`` (local-dev convenience).

Misses raise :class:`CorpusUnavailable` with a message that tells the
caller how to materialize the database — never a silent fallback.

Lifecycle, FTS5 query plumbing, and the outline row schema live in
:mod:`law_tools_core.corpus_db`; this module only declares the TMEP
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
    return Path.home() / ".cache" / "patent_client_agents" / "tmep.db"


class CorpusDB(OutlineCorpusDB):
    """TMEP corpus client — outline row schema served from the bundled SQLite."""

    LABEL = "TMEP"
    ENV_VAR = "TMEP_CORPUS_PATH"
    DEFAULT_FILENAME = "tmep.db"
    BUILD_COMMAND = "patent-client-agents-build-tmep-corpus"


__all__ = [
    "CorpusDB",
    "CorpusHit",
    "CorpusSection",
    "CorpusUnavailable",
    "default_corpus_path",
]
