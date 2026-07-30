"""SQLite schema for the ILPO Israel statutes corpus.

One ``sections`` row per (statute, section_number) pair across the five
in-scope Israeli IP statutes:

* Patents Law, 5727-1967 (``patents``)
* Trade Marks Ordinance [New Version], 5732-1972 (``trademarks``)
* Designs Law, 5777-2017 (``designs``)
* Copyright Act, 5768-2007 (``copyright``)
* Commercial Torts Law, 5759-1999 (``commercial_torts`` — Israel's
  standalone trade-secret + unregistered-mark statute; Articles 6-9
  cover trade secrets and Article 13 carries the statutory-damages
  remedy)

The FTS5 virtual table indexes the searchable text columns and stays in
sync via the AI/AD/AU triggers below (the "external content" pattern
keeps the inverted index slim while the canonical row lives in
``sections``).
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
    statute        TEXT NOT NULL,
    section_number TEXT NOT NULL,
    section_label  TEXT NOT NULL,
    title          TEXT,
    text           TEXT NOT NULL,
    source_url     TEXT,
    UNIQUE(statute, section_number)
);

CREATE INDEX IF NOT EXISTS idx_sections_statute
    ON sections(statute);
CREATE INDEX IF NOT EXISTS idx_sections_section_number
    ON sections(section_number);

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    statute,
    section_label,
    title,
    text,
    content='sections',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, statute, section_label, title, text)
    VALUES (new.rowid, new.statute, new.section_label, new.title, new.text);
END;

CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, statute, section_label, title, text)
    VALUES ('delete', old.rowid, old.statute, old.section_label, old.title, old.text);
END;

CREATE TRIGGER IF NOT EXISTS sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, statute, section_label, title, text)
    VALUES ('delete', old.rowid, old.statute, old.section_label, old.title, old.text);
    INSERT INTO sections_fts(rowid, statute, section_label, title, text)
    VALUES (new.rowid, new.statute, new.section_label, new.title, new.text);
END;
"""


META_KEYS = {
    "schema_version": "SQLite schema version (int)",
    "snapshot_date": "ISO-8601 date the corpus was built",
    "source_version": "Free-text version label (typically the WIPO Lex revision date)",
    "section_count": "Total rows in sections (int, for sanity checks)",
}
