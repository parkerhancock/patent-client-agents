"""Copy a few real rows from local EPO legal corpora into small test fixtures.

Maintenance only; tests never run this. Sources open read-only and immutable,
so their main files, WAL sidecars and metadata are never changed. Compressed
HTML BLOBs and the matching dictionary are copied byte for byte; plaintext rows
are copied as stored. The full-text index is rebuilt over the subset.
"""

from __future__ import annotations

import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

ROWS = {
    "epc": ["a52", "a54", "r1", "r71"],
    "caselaw": ["clr_foreword", "clr_i_a_1", "clr_i_c_5_2", "clr_i_d_9_1"],
    "guidelines": ["a_i", "g_ii_3", "g_ii_3_1", "g_vii_5_4"],
    "pct_guidelines": ["b_iii", "b_iii_1", "b_iii_2", "b_iii_2_3_3"],
    "up_guidelines": ["section_1", "section_1_2_1", "section_2_4"],
}
SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sections (
    rowid INTEGER PRIMARY KEY, href TEXT UNIQUE NOT NULL, section_number TEXT,
    title TEXT, breadcrumb TEXT, chapter TEXT, html TEXT NOT NULL, text TEXT NOT NULL
);
CREATE TABLE compression_dict (
    column_name TEXT PRIMARY KEY, dict_bytes BLOB NOT NULL, zstd_level INTEGER NOT NULL
);
CREATE VIRTUAL TABLE sections_fts USING fts5(
    section_number, title, text, content='sections', content_rowid='rowid',
    tokenize='porter unicode61'
);
"""


def extract(source: Path, output: Path, hrefs: list[str]) -> None:
    if output.exists():
        raise ValueError(f"{output} exists; fixtures are never overwritten.")
    with closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro&immutable=1", uri=True)) as src:
        meta = src.execute("SELECT key, value FROM meta").fetchall()
        dictionaries = src.execute(
            "SELECT column_name, dict_bytes, zstd_level FROM compression_dict"
        ).fetchall()
        marks = ",".join("?" * len(hrefs))
        rows = src.execute(
            "SELECT href, section_number, title, breadcrumb, chapter, html, text "
            f"FROM sections WHERE href IN ({marks}) ORDER BY href",
            hrefs,
        ).fetchall()
    if len(rows) != len(hrefs):
        raise ValueError(f"{source.name}: expected {len(hrefs)} rows, found {len(rows)}.")
    with closing(sqlite3.connect(output)) as out:
        out.executescript(SCHEMA)
        out.executemany("INSERT INTO meta VALUES (?, ?)", meta)
        out.executemany("INSERT INTO compression_dict VALUES (?, ?, ?)", dictionaries)
        out.executemany(
            "INSERT INTO sections (href, section_number, title, breadcrumb, chapter, html, text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        out.execute("INSERT INTO sections_fts(sections_fts) VALUES ('rebuild')")
        out.commit()
        out.execute("VACUUM")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir", type=Path, default=Path.home() / ".cache" / "patent_client_agents"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "epo-legal",
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, hrefs in ROWS.items():
        extract(args.source_dir / f"{name}.db", args.output_dir / f"{name}.db", hrefs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
