"""SQLite schema for the IPOS Singapore examination/work-manual corpus.

The corpus stores one row per **section** of three manuals:

- IPOS Patent Examination Guidelines (``peg``)
- IPOS Trade Marks Work Manual (``tm``)
- IPOS Industrial Designs Work Manual (``designs``)

A *section* is the smallest cite-bearing subdivision in the manual
(e.g. ``IPOS PEG 1.5.3``). When upstream PDFs don't expose stable
section labels, the entire manual is collapsed into a single ``0.0``
synthetic section so the schema invariant (every manual has ≥1 section
row) still holds.

The FTS5 virtual table indexes ``section_label`` + ``title`` + ``text``
under ``porter unicode61`` so callers can quote citation strings like
``"1.5.3"`` directly and still rank by topical match.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

DDL = """
PRAGMA foreign_keys = OFF;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sections (
    rowid          INTEGER PRIMARY KEY,
    manual         TEXT NOT NULL,    -- 'peg', 'tm', 'designs'
    short_name     TEXT NOT NULL,    -- e.g. 'PEG', 'TM Work Manual'
    manual_title   TEXT NOT NULL,    -- full manual title
    section_label  TEXT NOT NULL,    -- e.g. '1.5.3', 'Ch. 4', '4.A.2'
    title          TEXT,             -- heading (nullable when upstream omits)
    breadcrumb     TEXT,             -- 'PEG › Ch. 1 › 1.5 › 1.5.3'
    source_url     TEXT NOT NULL,    -- canonical IPOS URL for the manual / section
    source_version TEXT,             -- version label (release date) when known
    text           TEXT NOT NULL,
    UNIQUE(manual, section_label)
);

CREATE INDEX IF NOT EXISTS idx_sections_manual
    ON sections(manual);
CREATE INDEX IF NOT EXISTS idx_sections_short_name
    ON sections(short_name);

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    section_label,
    title,
    text,
    content='sections',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, section_label, title, text)
    VALUES (new.rowid, new.section_label, new.title, new.text);
END;

CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, section_label, title, text)
    VALUES ('delete', old.rowid, old.section_label, old.title, old.text);
END;

CREATE TRIGGER IF NOT EXISTS sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, section_label, title, text)
    VALUES ('delete', old.rowid, old.section_label, old.title, old.text);
    INSERT INTO sections_fts(rowid, section_label, title, text)
    VALUES (new.rowid, new.section_label, new.title, new.text);
END;
"""


META_KEYS = {
    "schema_version": "SQLite schema version (int)",
    "snapshot_date": "ISO-8601 date the corpus was built",
    "source_version": "Vendor-style version label (release date); optional",
    "section_count": "Number of section rows across all manuals",
    "manual_count": "Number of distinct manuals",
}
