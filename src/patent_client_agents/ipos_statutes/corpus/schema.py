"""SQLite schema for the IPOS Singapore statutes corpus.

The corpus stores one row per **section** of each Singapore IP Act —
Patents Act 1994, Trade Marks Act 1998, Registered Designs Act 2000,
and Copyright Act 2021. A section is the smallest cite-bearing
subdivision the corpus tracks (e.g. ``Section 13 Patents Act``); when
upstream HTML doesn't expose a stable section anchor the entire Act is
collapsed into a single ``00`` synthetic section so the schema invariant
(every Act has ≥1 section row) holds.

The FTS5 virtual table indexes ``section_label`` + ``title`` + ``text``
under ``porter unicode61`` so callers can quote citation strings like
``"Section 13"`` directly and still rank by topical match.

Statute keys are stable lowercase short names — ``patents``, ``tm``,
``designs``, ``copyright`` — and the per-statute ``short_name`` /
``title`` columns hold the citation-ready labels (``Patents Act``, etc).
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
    statute        TEXT NOT NULL,    -- e.g. 'patents', 'tm', 'designs', 'copyright'
    short_name     TEXT NOT NULL,    -- citation-ready short ('Patents Act')
    statute_title  TEXT NOT NULL,    -- full Act title
    section_label  TEXT NOT NULL,    -- e.g. '13', '13A', '27(1)'
    title          TEXT,             -- section heading (nullable when upstream omits)
    breadcrumb     TEXT,             -- 'Patents Act › Part III › Section 13' (informational)
    source_url     TEXT NOT NULL,    -- canonical SSO URL for the section
    source_version TEXT,             -- version label ('2020 Revised Edition'); nullable
    text           TEXT NOT NULL,
    UNIQUE(statute, section_label)
);

CREATE INDEX IF NOT EXISTS idx_sections_statute
    ON sections(statute);
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
    "source_version": "Vendor-style version label (e.g. '2020 Revised Edition'); optional",
    "section_count": "Number of section rows across all statutes",
    "statute_count": "Number of distinct statutes",
}
