"""SQLite schema for the TMEP corpus.

Identical structure to the MPEP corpus schema — same sections table,
same FTS5 external-content index, same triggers. Kept as a separate
module so each corpus's DDL is colocated with its module.
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
