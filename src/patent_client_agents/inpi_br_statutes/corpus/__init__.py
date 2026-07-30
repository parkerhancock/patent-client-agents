"""Static LPI corpus — a frozen, queryable SQLite snapshot.

The runtime never calls Planalto or WIPO Lex; it reads from a
SQLite/FTS5 database produced by
``patent-client-agents-build-inpi-br-statutes-corpus`` and located via:

1. ``INPI_BR_STATUTES_CORPUS_PATH`` environment variable (explicit path)
2. ``~/.cache/patent_client_agents/inpi_br_statutes.db`` (local-dev default)
3. ``CorpusUnavailable`` is raised with build instructions otherwise.

Bundles **both Portuguese (authoritative — Planalto) and English (WIPO
Lex translation)** per Article. The Portuguese text is the legal
authority; the English is a courtesy translation for cross-border work.
"""

from __future__ import annotations

from .db import CorpusDB, CorpusUnavailable, default_corpus_path

__all__ = ["CorpusDB", "CorpusUnavailable", "default_corpus_path"]
