"""SQLite schema for the LPI (Lei 9.279/1996) corpus.

One ``sections`` row per Article. Each row carries Portuguese
(authoritative — Planalto) and English (WIPO Lex translation) text so
the same record answers both PT and EN queries.

The FTS5 virtual table indexes the PT + EN text columns and stays in
sync via the AI/AD/AU triggers below — this is the FTS5 "external
content" pattern, which keeps the canonical row in ``sections`` while
the inverted index stays slim.
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
    article_number TEXT,
    title_pt       TEXT,
    title_en       TEXT,
    title_section  TEXT,
    text_pt        TEXT NOT NULL,
    text_en        TEXT,
    html_pt        TEXT NOT NULL,
    html_en        TEXT
);

CREATE INDEX IF NOT EXISTS idx_sections_article_number
    ON sections(article_number);
CREATE INDEX IF NOT EXISTS idx_sections_title_section
    ON sections(title_section);

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    article_number,
    title_pt,
    title_en,
    text_pt,
    text_en,
    content='sections',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES (new.rowid, new.article_number, new.title_pt, new.title_en, new.text_pt, new.text_en);
END;

CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES ('delete', old.rowid, old.article_number, old.title_pt, old.title_en, old.text_pt, old.text_en);
END;

CREATE TRIGGER IF NOT EXISTS sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES ('delete', old.rowid, old.article_number, old.title_pt, old.title_en, old.text_pt, old.text_en);
    INSERT INTO sections_fts(rowid, article_number, title_pt, title_en, text_pt, text_en)
    VALUES (new.rowid, new.article_number, new.title_pt, new.title_en, new.text_pt, new.text_en);
END;
"""


META_KEYS = {
    "schema_version": "SQLite schema version (int)",
    "snapshot_date": "ISO-8601 date the corpus was scraped",
    "lpi_year": "LPI consolidation year (used as corpus_version label)",
    "source_pt": "Planalto URL the PT text was scraped from",
    "source_en": "WIPO Lex URL the EN text was scraped from",
    "section_count": "Total rows in sections (int, for sanity checks)",
}
