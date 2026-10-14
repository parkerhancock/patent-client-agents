"""SQLite schema for the TMEP corpus: the shared outline schema."""

from __future__ import annotations

from patent_client_agents.shared.corpus.outline.schema import (
    OUTLINE_DDL,
    OUTLINE_SCHEMA_VERSION,
)

SCHEMA_VERSION = OUTLINE_SCHEMA_VERSION
DDL = OUTLINE_DDL
