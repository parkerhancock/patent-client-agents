"""Static MPEP corpus — a frozen, queryable SQLite snapshot.

The runtime never calls USPTO's eMPEP system; it reads from a SQLite/FTS5
database produced by ``patent-client-agents-build-mpep-corpus``. The
database is not bundled with the wheel — deployments materialize it via
the build CLI and the runtime locates it through:

1. ``MPEP_CORPUS_PATH`` environment variable (explicit path)
2. ``~/.cache/patent_client_agents/mpep.db`` (local-dev default)
3. ``CorpusUnavailable`` is raised with build instructions otherwise.
"""

from __future__ import annotations

from .db import CorpusDB, CorpusUnavailable, default_corpus_path

__all__ = ["CorpusDB", "CorpusUnavailable", "default_corpus_path"]
