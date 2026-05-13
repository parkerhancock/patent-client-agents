"""Static TMEP corpus — frozen SQLite snapshot of eTMEP.

Parallels :mod:`patent_client_agents.mpep.corpus`. The runtime never
calls ``tmep.uspto.gov``; it reads from a SQLite/FTS5 database produced
by ``patent-client-agents-build-tmep-corpus`` and resolved at runtime
via:

1. ``TMEP_CORPUS_PATH`` env var (explicit, used in cloud deploys).
2. ``~/.cache/patent_client_agents/tmep.db`` (local-dev default).
3. ``CorpusUnavailable`` raised otherwise with build instructions.
"""

from __future__ import annotations

from .db import CorpusDB, CorpusUnavailable, default_corpus_path

__all__ = ["CorpusDB", "CorpusUnavailable", "default_corpus_path"]
