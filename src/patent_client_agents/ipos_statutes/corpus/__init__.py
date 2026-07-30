"""SQLite/FTS5 corpus subpackage for the IPOS Singapore statutes."""

from .db import (
    CorpusDB,
    CorpusHit,
    CorpusSection,
    CorpusUnavailable,
    default_corpus_path,
)

__all__ = [
    "CorpusDB",
    "CorpusUnavailable",
    "CorpusSection",
    "CorpusHit",
    "default_corpus_path",
]
