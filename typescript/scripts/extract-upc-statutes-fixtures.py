"""Copy a few real rows from the UPC statutes corpus into a small test fixture.

Maintenance only; tests never run this. The source opens read-only and
immutable, so its main file, WAL sidecars and metadata are never changed.
Rows and ``meta`` are copied as stored, with their original rowids; the
full-text index is rebuilt over the subset. The default source is the
pre-built corpus the deploy image copies in
(``patent-client-agents-deploy/corpora/upc_statutes.db``).
"""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

ROWS = [("upca", "en"), ("fees", "en"), ("fees", "fr"), ("fees", "de")]
COLUMNS = "rowid, instrument, language, short_name, title, source_url, source_version, pdf_pages, text"
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE instruments (
    rowid INTEGER PRIMARY KEY, instrument TEXT NOT NULL, language TEXT NOT NULL,
    short_name TEXT NOT NULL, title TEXT NOT NULL, source_url TEXT NOT NULL,
    source_version TEXT, pdf_pages INTEGER, text TEXT NOT NULL,
    UNIQUE(instrument, language)
);
CREATE VIRTUAL TABLE instruments_fts USING fts5(
    short_name, title, text, content='instruments', content_rowid='rowid',
    tokenize='porter unicode61'
);
"""


def extract(source: Path, output: Path) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; fixtures are never overwritten.")
    with closing(
        sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    ) as src:
        meta = src.execute("SELECT key, value FROM meta").fetchall()
        rows = [
            src.execute(
                f"SELECT {COLUMNS} FROM instruments WHERE instrument = ? AND language = ?",
                key,
            ).fetchone()
            for key in ROWS
        ]
    if any(row is None for row in rows):
        raise ValueError(f"{source.name}: expected rows {ROWS} are not all present.")
    with closing(sqlite3.connect(output)) as out:
        out.executescript(SCHEMA)
        out.executemany("INSERT INTO meta VALUES (?, ?)", meta)
        out.executemany(f"INSERT INTO instruments ({COLUMNS}) VALUES ({', '.join('?' * 9)})", rows)
        out.execute("INSERT INTO instruments_fts(instruments_fts) VALUES ('rebuild')")
        out.commit()
        out.execute("VACUUM")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent
        / "tests"
        / "fixtures"
        / "upc-statutes"
        / "upc_statutes.db",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    extract(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
