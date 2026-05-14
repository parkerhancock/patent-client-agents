"""SQLite schema for the GUIDELINES corpus.

One ``sections`` row per GUIDELINES section (or appendix sub-part). The FTS5
virtual table indexes only the searchable text columns and stays in sync
via the AI/AD/AU triggers below — this is the FTS5 "external content"
pattern, which lets the canonical row live in ``sections`` while the
inverted index stays slim.
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
    href           TEXT UNIQUE NOT NULL,
    section_number TEXT,
    title          TEXT,
    breadcrumb     TEXT,
    chapter        TEXT,
    html           TEXT NOT NULL,
    text           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sections_section_number
    ON sections(section_number);
CREATE INDEX IF NOT EXISTS idx_sections_chapter
    ON sections(chapter);

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    section_number,
    title,
    text,
    content='sections',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, section_number, title, text)
    VALUES (new.rowid, new.section_number, new.title, new.text);
END;

CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, section_number, title, text)
    VALUES ('delete', old.rowid, old.section_number, old.title, old.text);
END;

CREATE TRIGGER IF NOT EXISTS sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, section_number, title, text)
    VALUES ('delete', old.rowid, old.section_number, old.title, old.text);
    INSERT INTO sections_fts(rowid, section_number, title, text)
    VALUES (new.rowid, new.section_number, new.title, new.text);
END;
"""


META_KEYS = {
    "schema_version": "SQLite schema version (int)",
    "snapshot_date": "ISO-8601 date the corpus was scraped",
    "source_version": "GUIDELINES version label as reported by eGUIDELINES",
    "section_count": "Total rows in sections (int, for sanity checks)",
}
