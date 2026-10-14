"""SQLite schema for the CASELAW corpus: the shared outline schema."""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline.schema import (
    OUTLINE_DDL,
    OUTLINE_SCHEMA_VERSION,
    outline_meta_keys,
)

SCHEMA_VERSION = OUTLINE_SCHEMA_VERSION
DDL = OUTLINE_DDL
META_KEYS = outline_meta_keys("CASELAW")
