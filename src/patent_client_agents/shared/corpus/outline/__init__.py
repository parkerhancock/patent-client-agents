"""Generic layer for the outline corpora: MPEP, TMEP, EPC, the EPO books, MoPP.

They share one SQLite schema (:mod:`.schema`), one row-model shape
(:mod:`.models`), one client (:mod:`.client`), and the same one-shot API
helpers (:mod:`.api`). Each package configures these and keeps only its
citation parsing, href normalization, result URLs, and labels.
"""

from __future__ import annotations

from .build import init_outline_corpus, insert_outline_section
from .client import OutlineCorpusClient
from .models import OutlineSearchHit, OutlineSearchResponse, OutlineSection, OutlineVersion
from .schema import OUTLINE_DDL, OUTLINE_SCHEMA_VERSION, outline_meta_keys

__all__ = [
    "OUTLINE_DDL",
    "OUTLINE_SCHEMA_VERSION",
    "OutlineCorpusClient",
    "OutlineSearchHit",
    "OutlineSearchResponse",
    "OutlineSection",
    "OutlineVersion",
    "init_outline_corpus",
    "insert_outline_section",
    "outline_meta_keys",
]
