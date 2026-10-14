"""Building blocks for the bundled SQLite/FTS5 corpus packages."""

from .build import atomic_output, fetch_text, load_jsonl_seed, run_build_cli
from .status import (
    CorpusStatus,
    corpus_status_from_meta,
    make_corpus_status,
    parse_snapshot_date,
)

__all__ = [
    "CorpusStatus",
    "atomic_output",
    "corpus_status_from_meta",
    "fetch_text",
    "load_jsonl_seed",
    "make_corpus_status",
    "parse_snapshot_date",
    "run_build_cli",
]
