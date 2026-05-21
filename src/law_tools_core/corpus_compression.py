"""Build-time helper: compress a text column inside an outline corpus.

The corresponding read-side decompression lives on
:class:`law_tools_core.corpus_db.CorpusDBBase` and is transparent — callers of
``get_section`` see the original text. Compression metadata is stored in a
sidecar ``compression_dict`` table that the read client autodiscovers, so
adding compression to a corpus requires no client-side changes.

Usage from a corpus's build script (canonical pattern)::

    from law_tools_core.corpus_compression import compress_text_column

    # ... build the sections table and FTS5 index as usual ...
    raw, compressed = compress_text_column(conn, "sections", "html")
    # IMPORTANT: run FTS5 'optimize' AFTER the compression UPDATE pass.
    # The AU trigger fires on every UPDATE even though only the unindexed
    # html column changes; running optimize after collapses the resulting
    # segment churn.
    conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
    conn.commit()
    conn.isolation_level = None
    conn.execute("VACUUM")

Tuning rationale (defaults are tested on MPEP's 28.8 MB html column at
3,013 rows):

* ``level=19`` — build is offline and slow is fine; ratio matters more.
* ``dict_size=64 KiB`` — yields ~7.4× on legal HTML; larger sizes don't pay
  off for sub-100MB corpora and add measurable cold-start cost.
* ``min_sample_bytes=32 KiB`` — zstd dictionary training rejects tiny
  samples ("Src size is incorrect"). Test fixtures build mini-corpora with
  1-2 sections; under threshold we skip compression and the read side
  naturally falls through to the uncompressed path.
"""

from __future__ import annotations

import logging
import random
import sqlite3

import zstandard as zstd

_ZSTD_LEVEL = 19
_ZSTD_DICT_SIZE = 64 * 1024
_ZSTD_TRAIN_SAMPLE = 200
_ZSTD_MIN_SAMPLE_BYTES = 32 * 1024


def compress_text_column(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    *,
    level: int = _ZSTD_LEVEL,
    dict_size: int = _ZSTD_DICT_SIZE,
    train_sample: int = _ZSTD_TRAIN_SAMPLE,
    min_sample_bytes: int = _ZSTD_MIN_SAMPLE_BYTES,
) -> tuple[int, int]:
    """Compress ``table.column`` in place using a trained zstd dictionary.

    Creates the sidecar ``compression_dict`` table if missing, trains a
    dictionary on up to ``train_sample`` rows, then UPDATEs each row with
    its compressed bytes. Returns ``(raw_bytes, compressed_bytes)`` so
    callers can log the achieved ratio.

    Skips compression and returns ``(0, 0)`` when the corpus is too small
    to train a meaningful dictionary — small enough is corpus-specific
    but anything under ``min_sample_bytes`` of total sample text is rejected
    by zstd outright. The read-side decoder cache treats absence of the
    sidecar table as "no compression" and serves the values as TEXT.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS compression_dict ("
        "  column_name TEXT PRIMARY KEY,"
        "  dict_bytes  BLOB NOT NULL,"
        "  zstd_level  INTEGER NOT NULL"
        ")"
    )

    rows = conn.execute(f"SELECT rowid, {column} FROM {table}").fetchall()
    if not rows:
        return (0, 0)

    rng = random.Random(42)
    sample = rng.sample(rows, min(train_sample, len(rows)))
    sample_bytes = [row[1].encode("utf-8") for row in sample]
    if sum(len(b) for b in sample_bytes) < min_sample_bytes:
        return (0, 0)

    dict_data = zstd.train_dictionary(dict_size, sample_bytes)
    cctx = zstd.ZstdCompressor(level=level, dict_data=dict_data)

    raw_total = 0
    compressed_total = 0
    updates: list[tuple[bytes, int]] = []
    for rowid, value in rows:
        raw = value.encode("utf-8")
        compressed = cctx.compress(raw)
        raw_total += len(raw)
        compressed_total += len(compressed)
        updates.append((compressed, rowid))

    conn.executemany(
        f"UPDATE {table} SET {column} = ? WHERE rowid = ?",
        updates,
    )
    conn.execute(
        "INSERT OR REPLACE INTO compression_dict (column_name, dict_bytes, zstd_level) "
        "VALUES (?, ?, ?)",
        (column, dict_data.as_bytes(), level),
    )
    return raw_total, compressed_total


def finalize_outline_corpus(
    conn: sqlite3.Connection,
    *,
    logger: logging.Logger | None = None,
) -> tuple[int, int]:
    """Run the standard end-of-build sequence for an outline-shaped corpus.

    Three steps, in this order — order matters:

    1. Compress ``sections.html`` with a trained zstd dictionary.
    2. ``INSERT INTO sections_fts(sections_fts) VALUES ('optimize')``. The
       compression UPDATE pass fires the FTS5 ``AU`` trigger on every row
       even though it only touches the unindexed ``html`` column; the
       trigger's delete+reinsert churn inflates segment count until this
       optimize collapses them.
    3. ``VACUUM`` to reclaim the file pages freed by compression.

    Returns ``(raw_bytes, compressed_bytes)`` from the compression step so
    callers can record additional metrics. When ``logger`` is provided the
    helper logs the achieved ratio at INFO.

    Use only with corpora that follow the outline schema
    (``sections(href, section_number, title, breadcrumb, chapter, html,
    text)`` + ``sections_fts`` virtual table). For other shapes call
    :func:`compress_text_column` directly and run optimize/VACUUM yourself.
    """
    raw, compressed = compress_text_column(conn, "sections", "html")
    conn.commit()
    if raw and logger is not None:
        ratio = raw / compressed if compressed else 0.0
        logger.info(
            "Compressed sections.html: %.2f MB -> %.2f MB (%.2fx)",
            raw / 1024 / 1024,
            compressed / 1024 / 1024,
            ratio,
        )
    conn.execute("INSERT INTO sections_fts(sections_fts) VALUES ('optimize')")
    conn.commit()
    # VACUUM must run outside any open transaction.
    conn.isolation_level = None
    conn.execute("VACUUM")
    return raw, compressed


__all__ = ["compress_text_column", "finalize_outline_corpus"]
